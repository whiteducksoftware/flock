"""Engine that asks a decision model and publishes a Decision artifact."""

from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING, Any

from pydantic import ConfigDict, Field

from flock.components.agent import EngineComponent
from flock.core.artifacts import Artifact
from flock.core.image import Image
from flock.core.visibility import Visibility, ensure_visibility
from flock.decisions.choice import FAILED, PASSED, UNSURE, Question
from flock.decisions.models import Decision
from flock.decisions.providers import (
    DecisionAnswer,
    DecisionProvider,
    DecisionQuestion,
)
from flock.decisions.tournament import Tournament
from flock.registry import RegistryError, type_registry
from flock.utils.runtime import EvalResult


if TYPE_CHECKING:
    from flock.core.agent import Agent, OutputGroup
    from flock.utils.runtime import Context, EvalInputs


def _extract_images(value: Any, images: list[Image]) -> Any:
    """Replace image data in a payload with ``<image N>`` and collect the images."""
    if isinstance(value, dict):
        url = value.get("url")
        if len(value) == 1 and isinstance(url, str) and url.startswith("data:image/"):
            images.append(Image(url=url))
            return f"<image {len(images)}>"
        return {key: _extract_images(item, images) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_extract_images(item, images) for item in value]
    return value


def prepare_state(artifacts: list[Artifact]) -> tuple[str, list[Image]]:
    """The text state, one line per input (``<TypeName>: <payload as JSON>``),
    and the images found in the inputs, in order of appearance."""
    lines = []
    images: list[Image] = []
    for artifact in artifacts:
        try:
            name = type_registry.resolve(artifact.type).__name__
        except RegistryError:
            name = artifact.type
        payload = _extract_images(artifact.payload, images)
        lines.append(f"{name}: {json.dumps(payload, ensure_ascii=False, default=str)}")
    return "\n".join(lines), images


def render_state(artifacts: list[Artifact]) -> str:
    """The text state of ``artifacts`` (images replaced by placeholders)."""
    return prepare_state(artifacts)[0]


def inherited_visibility(artifacts: list[Artifact]) -> Visibility:
    """The inputs' common visibility; refuses to pick one when they differ."""
    if not artifacts:
        return ensure_visibility(None)
    first = artifacts[0].visibility
    reference = first.model_dump(mode="json")
    if any(a.visibility.model_dump(mode="json") != reference for a in artifacts[1:]):
        raise ValueError(
            "Decision inputs carry different visibilities; pass visibility= to "
            ".decides() to choose the decision's readership explicitly."
        )
    return first.model_copy(deep=True)


class DecisionEngine(EngineComponent):
    """Answers :class:`Choice`, :class:`YesNo`, :class:`Scale` and
    :class:`Checklist` questions about the agent's inputs.

    All questions go to the provider together, split into concurrent requests
    of at most ``questions_per_request`` questions (a checklist counts one
    question per item). Publishes one ``Decision.of(question)`` artifact per
    question and execution. Below ``threshold`` a decision's ``choice`` is
    ``UNSURE``; ``best_guess`` keeps the model's pick either way. A refused
    question is ``UNSURE`` with ``refused=True``. Decisions inherit their
    inputs' visibility unless ``visibility`` is set. ``instructions`` replaces
    the docstring of a single question. With ``tournament`` set, the single
    Choice question is asked in rounds of groups (see :class:`Tournament`);
    the decision's ``rounds`` records them.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    questions: list[type[Question]]
    provider: DecisionProvider
    threshold: float | None = None
    instructions: str | None = None
    visibility: Visibility | None = None
    questions_per_request: int = Field(default=100, ge=1)
    tournament: Tournament | None = None
    enable_context: bool = Field(
        default=False, description="Decisions are made on the inputs only"
    )

    async def evaluate(
        self, agent: Agent, ctx: Context, inputs: EvalInputs, output_group: OutputGroup
    ) -> EvalResult:
        if ctx.is_batch:
            raise ValueError(
                f"Decision agent '{agent.name}' decides one execution at a time; "
                "batch subscriptions are not supported."
            )
        visibility = (
            self.visibility.model_copy(deep=True)
            if self.visibility is not None
            else inherited_visibility(inputs.artifacts)
        )
        wire = self._wire_questions()

        state, images = prepare_state(inputs.artifacts)
        if images and not self.provider.supports_images:
            raise ValueError(
                f"Decision model '{self.provider.label}' does not accept images; "
                "use a provider with image support (openai/, local/ with a vision "
                "model) for inputs with Image fields."
            )

        started = time.perf_counter()
        rounds: list[dict[str, Any]] = []
        if self.tournament is not None:
            answer, rounds = await self._run_tournament(state, images)
            answers = {self.questions[0].__name__: answer}
        else:
            answers = await self._ask(state, wire, images)
        latency_ms = round((time.perf_counter() - started) * 1000, 3)

        subject_ids = [str(a.id) for a in inputs.artifacts]
        artifacts = []
        for question in self.questions:
            model = Decision.of(question)
            if question.__kind__ == "checklist":
                decision = self._checklist_decision(
                    question, wire, answers, subject_ids, latency_ms
                )
                artifacts.append(
                    Artifact(
                        type=type_registry.name_for(model),
                        payload=decision.model_dump(mode="json"),
                        produced_by=agent.name,
                        visibility=visibility.model_copy(deep=True),
                    )
                )
                continue
            answer = answers[question.__name__]
            decision = model(
                choice=answer.choice if self._firm(answer) else UNSURE,
                best_guess=answer.choice,
                probabilities=answer.probabilities,
                confidence=answer.confidence,
                threshold=self.threshold,
                score=answer.score,
                refused=answer.refused,
                subject_ids=subject_ids,
                rounds=rounds,
                model=answer.model or self.provider.label,
                latency_ms=latency_ms,
            )
            artifacts.append(
                Artifact(
                    type=type_registry.name_for(model),
                    payload=decision.model_dump(mode="json"),
                    produced_by=agent.name,
                    visibility=visibility.model_copy(deep=True),
                )
            )
        return EvalResult(artifacts=artifacts)

    async def _ask(
        self, state: str, wire: list[DecisionQuestion], images: list[Image]
    ) -> dict[str, DecisionAnswer]:
        """Ask ``wire`` in concurrent requests of at most ``questions_per_request``."""
        size = self.questions_per_request
        chunks = [wire[i : i + size] for i in range(0, len(wire), size)]
        replies = await asyncio.gather(
            *(self.provider.decide_many(state, chunk, images) for chunk in chunks)
        )
        return {name: answer for reply in replies for name, answer in reply.items()}

    async def _run_tournament(
        self, state: str, images: list[Image]
    ) -> tuple[DecisionAnswer, list[dict[str, Any]]]:
        """Narrow a large Choice down in rounds of groups, then ask the final question."""
        question = self.questions[0]
        name = question.__name__
        prompt = self.instructions or question.__question__
        options = question.__options__
        group_size, keep = self.tournament.group_size, self.tournament.keep

        def ask_about(label: str, candidates: list[str]) -> DecisionQuestion:
            return DecisionQuestion(
                name=label,
                instructions=prompt,
                options={option: options[option] for option in candidates},
                group=name,
            )

        candidates = list(options)
        rounds: list[dict[str, Any]] = []
        while len(candidates) > group_size:
            groups = [
                candidates[i : i + group_size]
                for i in range(0, len(candidates), group_size)
            ]
            wire = [
                ask_about(f"{name}_r{len(rounds)}_g{index}", group)
                for index, group in enumerate(groups)
            ]
            answers = await self._ask(state, wire, images)
            survivors: list[str] = []
            refused = 0
            for group, group_question in zip(groups, wire, strict=True):
                answer = answers[group_question.name]
                if answer.refused or answer.choice is None:
                    refused += 1  # no option of the group fits
                    continue
                ranked = sorted(group, key=lambda o: -answer.probabilities.get(o, 0.0))
                survivors.extend(ranked[:keep])
            rounds.append({
                "candidates": len(candidates),
                "groups": len(groups),
                "refused_groups": refused,
                "survivors": survivors,
            })
            candidates = survivors

        if not candidates:  # every group was refused
            return DecisionAnswer(choice=None, probabilities={}, refused=True), rounds
        if len(candidates) == 1:
            only = candidates[0]
            return DecisionAnswer(only, {only: 1.0}, confidence=1.0), rounds
        final = ask_about(name, candidates)
        return (await self._ask(state, [final], images))[name], rounds

    def _wire_questions(self) -> list[DecisionQuestion]:
        """The questions sent to the provider; a checklist becomes one yes/no
        question per item."""
        wire = []
        for question in self.questions:
            prompt = self.instructions or question.__question__
            if question.__kind__ != "checklist":
                wire.append(
                    DecisionQuestion(
                        name=question.__name__,
                        instructions=prompt,
                        options=question.__options__,
                        kind=question.__kind__,
                    )
                )
                continue
            for index, (item, text) in enumerate(question.__options__.items()):
                wire.append(
                    DecisionQuestion(
                        name=f"{question.__name__}_{index}",
                        instructions=f"{prompt}\n{text}" if text else prompt,
                        options={"yes": "", "no": ""},
                        kind="yesno",
                        group=question.__name__,
                        item=item,
                    )
                )
        return wire

    def _item_result(self, p_yes: float) -> str:
        if self.threshold is None:
            return "yes" if p_yes >= 0.5 else "no"
        if p_yes >= self.threshold:
            return "yes"
        if p_yes <= 1.0 - self.threshold:
            return "no"
        return UNSURE

    def _checklist_decision(
        self,
        question: type[Question],
        wire: list[DecisionQuestion],
        answers: dict[str, DecisionAnswer],
        subject_ids: list[str],
        latency_ms: float,
    ) -> Decision:
        results: dict[str, str] = {}
        probabilities: dict[str, float] = {}
        refused: list[str] = []
        models: list[str] = []
        for item_question in wire:
            if item_question.group != question.__name__:
                continue
            item = item_question.item
            answer = answers[item_question.name]
            if answer.model:
                models.append(answer.model)
            if answer.refused or answer.choice is None:
                results[item] = UNSURE
                refused.append(item)
                continue
            probabilities[item] = answer.probabilities.get("yes", 0.0)
            results[item] = self._item_result(probabilities[item])

        if "no" in results.values():
            outcome = FAILED
        elif UNSURE in results.values():
            outcome = UNSURE
        else:
            outcome = PASSED
        best_guess = None
        if probabilities:
            best_guess = (
                FAILED if any(p < 0.5 for p in probabilities.values()) else PASSED
            )
        return Decision.of(question)(
            choice=outcome,
            best_guess=best_guess,
            probabilities=probabilities,
            results=results,
            refused_items=refused,
            refused=len(refused) == len(results),
            threshold=self.threshold,
            subject_ids=subject_ids,
            model=models[0] if models else self.provider.label,
            latency_ms=latency_ms,
        )

    def _firm(self, answer: DecisionAnswer) -> bool:
        if answer.refused or answer.choice is None:
            return False
        if self.threshold is None:
            return True
        top = answer.probabilities.get(answer.choice, answer.confidence)
        return top is not None and top >= self.threshold


__all__ = ["DecisionEngine", "inherited_visibility", "prepare_state", "render_state"]

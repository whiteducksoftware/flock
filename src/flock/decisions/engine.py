"""Engine that asks a decision model and publishes a Decision artifact."""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import replace
from typing import TYPE_CHECKING, Any, Literal

from pydantic import ConfigDict, Field

from flock.components.agent import EngineComponent
from flock.core.artifacts import Artifact
from flock.core.image import Image
from flock.core.visibility import Visibility, ensure_visibility
from flock.decisions.choice import FAILED, MAX_OPTIONS, PASSED, UNSURE, Question
from flock.decisions.models import Decision
from flock.decisions.providers import (
    DecisionAnswer,
    DecisionProvider,
    DecisionQuestion,
)
from flock.decisions.tournament import Tournament
from flock.logging.logging import get_logger
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


# Eliminated options recorded per tournament group, next to the survivors
TOP_ELIMINATED = 2


def _trivial_answer(candidates: dict[str, str]) -> DecisionAnswer:
    if not candidates:
        return DecisionAnswer(choice=None, probabilities={})
    (only,) = candidates
    return DecisionAnswer(only, {only: 1.0}, confidence=1.0)


logger = get_logger(__name__)

VOTES = ("majority", "unanimous", "mean")


class _Trail:
    """How each wire question was answered: the escalation tier and the
    answers before it, or an ensemble's votes and their verdict."""

    def __init__(self) -> None:
        self.tiers: dict[str, int] = {}
        self.labels: dict[str, str] = {}
        self.attempts: dict[str, list[tuple[str, DecisionAnswer]]] = {}
        self.votes: dict[str, list[tuple[str, DecisionAnswer]]] = {}
        # The firm answer the vote reached, None when it did not
        self.verdicts: dict[str, str | None] = {}

    def label(self, name: str, default: str) -> str:
        return self.labels.get(name, default)


def _mean_answer(answers: list[DecisionAnswer], label: str) -> DecisionAnswer:
    """The answers of an ensemble averaged; refusals are left out."""
    valid = [a for a in answers if not a.refused and a.choice is not None]
    if not valid:
        return DecisionAnswer(choice=None, probabilities={}, model=label, refused=True)
    options = dict.fromkeys(option for a in valid for option in a.probabilities)
    probabilities = {
        option: sum(a.probabilities.get(option, 0.0) for a in valid) / len(valid)
        for option in options
    }
    choice = max(probabilities, key=probabilities.__getitem__)
    scores = [a.score for a in valid if a.score is not None]
    return DecisionAnswer(
        choice=choice,
        probabilities=probabilities,
        confidence=probabilities[choice],
        model=label,
        score=sum(scores) / len(scores) if scores else None,
    )


def _attempt(label: str, answer: DecisionAnswer) -> dict[str, Any]:
    """An earlier tier's answer, as a decision records it."""
    return {
        "model": label,
        "choice": answer.choice,
        "probabilities": dict(answer.probabilities),
        "confidence": answer.confidence,
        "refused": answer.refused,
    }


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
    the decision's ``rounds`` records them. With ``escalation``, questions (and
    checklist items) that are not firm are asked again by the next provider;
    a decision records the ``tier`` that answered and the earlier ``attempts``.
    With ``ensemble``, every provider answers every question and ``vote``
    decides; a decision records the ``votes``. A ``shadow`` provider answers
    every question too; its answer is recorded in the decision's ``shadow``
    and never routes.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    questions: list[type[Question]]
    provider: DecisionProvider
    threshold: float | None = None
    instructions: str | None = None
    visibility: Visibility | None = None
    questions_per_request: int = Field(default=100, ge=1)
    tournament: Tournament | None = None
    options: Callable[[Any], Iterable[str]] | None = Field(
        default=None,
        description="Restricts the single Choice or Checklist to these options "
        "for each execution",
    )
    escalation: list[DecisionProvider] = Field(
        default_factory=list,
        description="Providers asked in order about what the previous one was "
        "not sure about",
    )
    ensemble: list[DecisionProvider] = Field(
        default_factory=list,
        description="Providers that all answer every question (instead of "
        "provider); vote combines their answers",
    )
    vote: Literal["majority", "unanimous", "mean"] = Field(
        default="majority",
        description="majority: more than half of the ensemble gives the same firm "
        "answer; unanimous: all of it; mean: the threshold applies to the mean",
    )
    shadow: DecisionProvider | None = Field(
        default=None,
        description="Answers every question too; recorded, never routed",
    )
    shadow_timeout: float = Field(
        default=10.0,
        gt=0,
        description="Seconds the decision waits for the shadow after its own "
        "answer; a slower shadow is cancelled and recorded as an error",
    )
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
        candidates = self._candidates(ctx)
        wire = self._wire_questions(candidates)

        state, images = prepare_state(inputs.artifacts)
        if images:
            for provider in (self.provider, *self.escalation, *self.ensemble):
                if not provider.supports_images:
                    raise ValueError(
                        f"Decision model '{provider.label}' does not accept images; "
                        "use providers with image support (openai/, local/ with a "
                        "vision model) for inputs with Image fields, also in "
                        "escalate= and models=."
                    )

        started = time.perf_counter()
        trail = _Trail()
        shadowed = None
        if self.shadow is not None and wire and self.tournament is None:
            # Concurrently with the decision; it never fails the decision
            shadowed = asyncio.create_task(self._shadow_answers(state, wire, images))
        try:
            answers, rounds = await self._answers(
                state, wire, images, candidates, trail
            )
        except BaseException:
            if shadowed is not None:
                shadowed.cancel()
                # Wait until the shadow has stopped, not only asked it to
                with contextlib.suppress(asyncio.CancelledError):
                    await shadowed
            raise
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        shadow = None
        if shadowed is not None:
            try:
                shadow = await asyncio.wait_for(shadowed, self.shadow_timeout)
            except TimeoutError:  # wait_for has cancelled the shadow
                shadow = f"TimeoutError: no answer within {self.shadow_timeout:g} s"
                logger.warning(f"Shadow decision model '{self.shadow.label}': {shadow}")

        subject_ids = [str(a.id) for a in inputs.artifacts]
        artifacts = []
        for question in self.questions:
            model = Decision.of(question)
            shadow_record = self._shadow_record(question, wire, shadow)
            if question.__kind__ == "checklist":
                decision = self._checklist_decision(
                    question, wire, answers, subject_ids, latency_ms, trail
                )
                decision.shadow = shadow_record
                if candidates is not None:
                    decision.candidates = list(candidates)
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
            name = question.__name__
            if name in trail.verdicts:
                choice = trail.verdicts[name] or UNSURE
            else:
                choice = answer.choice if self._firm(answer) else UNSURE
            decision = model(
                choice=choice,
                best_guess=answer.choice,
                probabilities=answer.probabilities,
                confidence=answer.confidence,
                threshold=self.threshold,
                score=None if answer.refused else answer.score,
                refused=answer.refused,
                subject_ids=subject_ids,
                candidates=None if candidates is None else list(candidates),
                rounds=rounds,
                model=answer.model or trail.label(name, self.provider.label),
                tier=trail.tiers.get(name, 0),
                attempts=[
                    _attempt(label, earlier)
                    for label, earlier in trail.attempts.get(name, [])
                ],
                votes=[
                    _attempt(label, vote) for label, vote in trail.votes.get(name, [])
                ],
                shadow=shadow_record,
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

    async def _answers(
        self,
        state: str,
        wire: list[DecisionQuestion],
        images: list[Image],
        candidates: dict[str, str] | None,
        trail: _Trail,
    ) -> tuple[dict[str, DecisionAnswer], list[dict[str, Any]]]:
        """The answers and tournament rounds, escalated or voted as
        configured; ``trail`` records how."""
        if (
            candidates is not None
            and self.questions[0].__kind__ == "choice"
            and (len(candidates) < 2)
        ):
            # Nothing to rank: no candidates is UNSURE, a single one wins
            # No model was asked, so an ensemble has no votes
            answer = replace(_trivial_answer(candidates), model=self._label)
            return {self.questions[0].__name__: answer}, []
        if self.tournament is not None:
            answer, rounds = await self._run_tournament(state, images, candidates)
            return {self.questions[0].__name__: answer}, rounds
        if not wire:
            return {}, []
        if self.ensemble:
            return await self._vote(state, wire, images, trail), []
        answers = await self._ask(state, wire, images)
        await self._escalate(state, wire, answers, images, trail)
        return answers, []

    async def _shadow_answers(
        self, state: str, wire: list[DecisionQuestion], images: list[Image]
    ) -> tuple[dict[str, DecisionAnswer], float] | str:
        """The shadow's answers and latency, or the error that stopped it."""
        assert self.shadow is not None
        started = time.perf_counter()
        try:
            if images and not self.shadow.supports_images:
                raise ValueError(
                    f"Decision model '{self.shadow.label}' does not accept images"
                )
            answers = await self._ask(state, wire, images, provider=self.shadow)
        except Exception as exc:  # a shadow must never fail the decision
            logger.warning(f"Shadow decision model '{self.shadow.label}' failed: {exc}")
            return f"{type(exc).__name__}: {exc}"
        return answers, round((time.perf_counter() - started) * 1000, 3)

    def _shadow_record(
        self,
        question: type[Question],
        wire: list[DecisionQuestion],
        shadow: tuple[dict[str, DecisionAnswer], float] | str | None,
    ) -> dict[str, Any] | None:
        """The shadow's answer to ``question``, as a decision records it."""
        if shadow is None or self.shadow is None:
            return None
        if isinstance(shadow, str):
            return {"model": self.shadow.label, "error": shadow}
        answers, latency_ms = shadow
        if question.__kind__ == "checklist":
            items = [q for q in wire if q.group == question.__name__]
            outcome = self._checklist_decision(question, items, answers, [], latency_ms)
            return {
                "model": next(
                    (answers[q.name].model for q in items if answers[q.name].model),
                    self.shadow.label,
                ),
                "choice": outcome.choice,
                "best_guess": outcome.best_guess,
                "results": dict(outcome.results),
                "refused_items": list(outcome.refused_items),
                "latency_ms": latency_ms,
            }
        answer = answers[question.__name__]
        return {
            "model": answer.model or self.shadow.label,
            "choice": answer.choice if self._firm(answer) else UNSURE,
            "best_guess": answer.choice,
            "probabilities": dict(answer.probabilities),
            "confidence": answer.confidence,
            "refused": answer.refused,
            "latency_ms": latency_ms,
        }

    async def _ask(
        self,
        state: str,
        wire: list[DecisionQuestion],
        images: list[Image],
        provider: DecisionProvider | None = None,
    ) -> dict[str, DecisionAnswer]:
        """Ask ``wire`` in concurrent requests of at most ``questions_per_request``."""
        provider = provider or self.provider
        size = self.questions_per_request
        chunks = [wire[i : i + size] for i in range(0, len(wire), size)]
        replies = await asyncio.gather(
            *(provider.decide_many(state, chunk, images) for chunk in chunks)
        )
        return {name: answer for reply in replies for name, answer in reply.items()}

    async def _escalate(
        self,
        state: str,
        wire: list[DecisionQuestion],
        answers: dict[str, DecisionAnswer],
        images: list[Image],
        trail: _Trail,
    ) -> None:
        """Ask what is not firm again, one tier up; ``answers`` and ``trail``
        are updated."""
        for tier, provider in enumerate(self.escalation, start=1):
            unsure = [q for q in wire if not self._settled(q, answers[q.name])]
            if not unsure:
                break
            replies = await self._ask(state, unsure, images, provider=provider)
            for question in unsure:
                earlier = answers[question.name]
                label = earlier.model or trail.label(question.name, self.provider.label)
                trail.attempts.setdefault(question.name, []).append((label, earlier))
                answers[question.name] = replies[question.name]
                trail.tiers[question.name] = tier
                trail.labels[question.name] = provider.label

    async def _vote(
        self,
        state: str,
        wire: list[DecisionQuestion],
        images: list[Image],
        trail: _Trail,
    ) -> dict[str, DecisionAnswer]:
        """Ask every provider of the ensemble; the mean answers, with the
        votes and verdicts in ``trail``."""
        replies = await asyncio.gather(
            *(self._ask(state, wire, images, provider=p) for p in self.ensemble)
        )
        label = " + ".join(
            next((r[q.name].model for q in wire if r[q.name].model), p.label)
            for p, r in zip(self.ensemble, replies, strict=True)
        )
        answers: dict[str, DecisionAnswer] = {}
        for question in wire:
            ballot = [
                (reply[question.name].model or provider.label, reply[question.name])
                for provider, reply in zip(self.ensemble, replies, strict=True)
            ]
            combined = _mean_answer([answer for _, answer in ballot], label)
            verdict = self._verdict(question, combined, [a for _, a in ballot])
            if verdict is not None and question.item is None:
                # The best guess is the option voted for
                combined = replace(
                    combined,
                    choice=verdict,
                    confidence=combined.probabilities.get(verdict),
                )
            trail.votes[question.name] = ballot
            trail.verdicts[question.name] = verdict
            answers[question.name] = combined
        return answers

    def _verdict(
        self,
        question: DecisionQuestion,
        combined: DecisionAnswer,
        ballot: list[DecisionAnswer],
    ) -> str | None:
        """The firm answer of the vote, None when the vote reached none."""
        if self.vote == "mean":
            return self._firm_value(question, combined)
        votes = Counter(
            value
            for value in (self._firm_value(question, answer) for answer in ballot)
            if value is not None
        )
        if not votes:
            return None
        value, count = votes.most_common(1)[0]
        needed = len(ballot) if self.vote == "unanimous" else len(ballot) // 2 + 1
        return value if count >= needed else None

    def _firm_value(
        self, question: DecisionQuestion, answer: DecisionAnswer
    ) -> str | None:
        """One answer's firm value: the choice, or a checklist item's yes or no."""
        if not self._settled(question, answer):
            return None
        if question.item is None:
            return answer.choice
        return self._item_result(answer.probabilities.get("yes", 0.0))

    def _settled(self, question: DecisionQuestion, answer: DecisionAnswer) -> bool:
        """A firm answer: a checklist item's result, else the threshold."""
        if question.item is None:
            return self._firm(answer)
        if answer.refused or answer.choice is None:
            return False
        return self._item_result(answer.probabilities.get("yes", 0.0)) != UNSURE

    def _candidates(self, ctx: Context) -> dict[str, str] | None:
        """The options of the single question for this execution (options=)."""
        if self.options is None:
            return None
        question = self.questions[0]
        names = list(dict.fromkeys(self.options(ctx)))
        unknown = [name for name in names if name not in question.__options__]
        if unknown:
            raise ValueError(
                f"options= returned names that are not options of "
                f"{question.__name__}: {', '.join(map(str, unknown))}"
            )
        if (
            question.__kind__ == "choice"
            and self.tournament is None
            and len(names) > MAX_OPTIONS
        ):
            raise ValueError(
                f"options= returned {len(names)} options of {question.__name__}; "
                f"decision models accept at most {MAX_OPTIONS} options per question. "
                "Pass tournament=Tournament(...) to ask them in rounds."
            )
        # In declared order, so a decision does not depend on arrival order
        chosen = set(names)
        return {
            name: text for name, text in question.__options__.items() if name in chosen
        }

    async def _run_tournament(
        self,
        state: str,
        images: list[Image],
        candidates: dict[str, str] | None = None,
    ) -> tuple[DecisionAnswer, list[dict[str, Any]]]:
        """Narrow a large Choice down in rounds of groups, then ask the final question."""
        question = self.questions[0]
        name = question.__name__
        prompt = self.instructions or question.__question__
        options = candidates if candidates is not None else question.__options__
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
            # A group of one (a leftover) cannot be asked as a choice: it is a bye
            wire = {
                index: ask_about(f"{name}_r{len(rounds)}_g{index}", group)
                for index, group in enumerate(groups)
                if len(group) > 1
            }
            answers = await self._ask(state, list(wire.values()), images)
            survivors: list[str] = []
            refused = 0
            group_results: list[dict[str, Any]] = []
            for index, group in enumerate(groups):
                if index not in wire:
                    survivors.extend(group)
                    group_results.append({
                        "size": 1,
                        "refused": False,
                        "top": [[group[0], 1.0]],
                    })
                    continue
                answer = answers[wire[index].name]
                if answer.refused or answer.choice is None:
                    refused += 1  # no option of the group fits
                    group_results.append({
                        "size": len(group),
                        "refused": True,
                        "top": [],
                    })
                    continue
                ranked = sorted(group, key=lambda o: -answer.probabilities.get(o, 0.0))
                survivors.extend(ranked[:keep])
                # Survivors plus the strongest eliminated options show the margin
                top = ranked[: keep + TOP_ELIMINATED]
                group_results.append({
                    "size": len(group),
                    "refused": False,
                    "top": [[o, answer.probabilities.get(o, 0.0)] for o in top],
                })
            rounds.append({
                "candidates": len(candidates),
                "groups": len(groups),
                "group_size": group_size,
                "refused_groups": refused,
                "survivors": survivors,
                "group_results": group_results,
            })
            candidates = survivors

        if not candidates:  # every group was refused
            return DecisionAnswer(choice=None, probabilities={}, refused=True), rounds
        if len(candidates) == 1:
            only = candidates[0]
            return DecisionAnswer(only, {only: 1.0}, confidence=1.0), rounds
        final = ask_about(name, candidates)
        return (await self._ask(state, [final], images))[name], rounds

    def _wire_questions(
        self, candidates: dict[str, str] | None = None
    ) -> list[DecisionQuestion]:
        """The questions sent to the provider; a checklist becomes one yes/no
        question per item. ``candidates`` restricts the single question."""
        wire = []
        for question in self.questions:
            prompt = self.instructions or question.__question__
            options = candidates if candidates is not None else question.__options__
            if question.__kind__ != "checklist":
                if candidates is not None and len(candidates) < 2:
                    continue  # decided without a request
                wire.append(
                    DecisionQuestion(
                        name=question.__name__,
                        instructions=prompt,
                        options=options,
                        kind=question.__kind__,
                        # a restricted choice is a subset of the declared options
                        group=question.__name__ if candidates is not None else None,
                    )
                )
                continue
            for index, (item, text) in enumerate(options.items()):
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
        # The more probable answer, firm if it reaches the threshold (as for a
        # YesNo question; below 0.5 the yes and no regions would overlap)
        answer, probability = ("yes", p_yes) if p_yes >= 0.5 else ("no", 1.0 - p_yes)
        if self.threshold is None or probability >= self.threshold:
            return answer
        return UNSURE

    def _checklist_decision(
        self,
        question: type[Question],
        wire: list[DecisionQuestion],
        answers: dict[str, DecisionAnswer],
        subject_ids: list[str],
        latency_ms: float,
        trail: _Trail | None = None,
    ) -> Decision:
        trail = trail or _Trail()
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
            if item_question.name in trail.verdicts:
                results[item] = trail.verdicts[item_question.name] or UNSURE
            else:
                results[item] = self._item_result(probabilities[item])

        if not results:
            outcome = UNSURE  # no items to check
        elif "no" in results.values():
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
        # Escalated items: the highest tier answered, earlier tiers per round
        items = [q for q in wire if q.group == question.__name__]
        tier = max((trail.tiers.get(q.name, 0) for q in items), default=0)
        attempts: list[dict[str, Any]] = []
        for item_question in items:
            for index, (label, earlier) in enumerate(
                trail.attempts.get(item_question.name, [])
            ):
                while len(attempts) <= index:
                    attempts.append({"model": label, "results": {}})
                attempts[index]["results"][item_question.item] = (
                    UNSURE
                    if earlier.refused or earlier.choice is None
                    else self._item_result(earlier.probabilities.get("yes", 0.0))
                )
        # Ensembles: every model's result per item, in the order of the models
        votes: list[dict[str, Any]] = []
        for item_question in items:
            for index, (label, vote) in enumerate(
                trail.votes.get(item_question.name, [])
            ):
                while len(votes) <= index:
                    votes.append({"model": label, "results": {}})
                votes[index]["results"][item_question.item] = (
                    self._firm_value(item_question, vote) or UNSURE
                )
        # The model the top tier reported, else its configured label
        top_label = next(
            (
                answers[q.name].model or trail.labels[q.name]
                for q in items
                if trail.tiers.get(q.name, 0) == tier and q.name in trail.labels
            ),
            None,
        )
        return Decision.of(question)(
            choice=outcome,
            best_guess=best_guess,
            probabilities=probabilities,
            results=results,
            refused_items=refused,
            refused=bool(results) and len(refused) == len(results),
            threshold=self.threshold,
            subject_ids=subject_ids,
            model=top_label or (models[0] if models else self._label),
            tier=tier,
            attempts=attempts,
            votes=votes,
            latency_ms=latency_ms,
        )

    @property
    def _label(self) -> str:
        """The configured model name: the provider's, or an ensemble's joined."""
        if self.ensemble:
            return " + ".join(provider.label for provider in self.ensemble)
        return self.provider.label

    def _firm(self, answer: DecisionAnswer) -> bool:
        if answer.refused or answer.choice is None:
            return False
        if self.threshold is None:
            return True
        top = answer.probabilities.get(answer.choice, answer.confidence)
        return top is not None and top >= self.threshold


__all__ = [
    "VOTES",
    "DecisionEngine",
    "inherited_visibility",
    "prepare_state",
    "render_state",
]

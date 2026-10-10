"""Engine that asks a decision model and publishes a Decision artifact."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

from pydantic import ConfigDict, Field

from flock.components.agent import EngineComponent
from flock.core.artifacts import Artifact
from flock.core.image import Image
from flock.core.visibility import Visibility, ensure_visibility
from flock.decisions.choice import UNSURE, Question
from flock.decisions.models import Decision
from flock.decisions.providers import (
    DecisionAnswer,
    DecisionProvider,
    DecisionQuestion,
)
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
    """Answers :class:`Choice`, :class:`YesNo` and :class:`Scale` questions
    about the agent's inputs, all in one provider request.

    Publishes one ``Decision.of(question)`` artifact per question and
    execution. Below ``threshold`` a decision's ``choice`` is ``UNSURE``;
    ``best_guess`` keeps the model's pick either way. A refused question is
    ``UNSURE`` with ``refused=True``. Decisions inherit their inputs'
    visibility unless ``visibility`` is set. ``instructions`` replaces the
    docstring of a single question.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    questions: list[type[Question]]
    provider: DecisionProvider
    threshold: float | None = None
    instructions: str | None = None
    visibility: Visibility | None = None
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
        questions = [
            DecisionQuestion(
                name=question.__name__,
                instructions=self.instructions or question.__question__,
                options=question.__options__,
                kind=question.__kind__,
            )
            for question in self.questions
        ]

        state, images = prepare_state(inputs.artifacts)
        if images and not self.provider.supports_images:
            raise ValueError(
                f"Decision model '{self.provider.label}' does not accept images; "
                "use a provider with image support (openai/, local/ with a vision "
                "model) for inputs with Image fields."
            )

        started = time.perf_counter()
        answers = await self.provider.decide_many(state, questions, images)
        latency_ms = round((time.perf_counter() - started) * 1000, 3)

        subject_ids = [str(a.id) for a in inputs.artifacts]
        artifacts = []
        for question in self.questions:
            model = Decision.of(question)
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

    def _firm(self, answer: DecisionAnswer) -> bool:
        if answer.refused or answer.choice is None:
            return False
        if self.threshold is None:
            return True
        top = answer.probabilities.get(answer.choice, answer.confidence)
        return top is not None and top >= self.threshold


__all__ = ["DecisionEngine", "inherited_visibility", "prepare_state", "render_state"]

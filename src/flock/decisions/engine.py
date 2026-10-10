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
from flock.decisions.choice import UNSURE, Choice
from flock.decisions.models import Decision
from flock.decisions.providers import DecisionProvider, DecisionQuestion
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
    """Answers a :class:`Choice` question about the agent's inputs.

    Publishes one ``Decision.of(choice)`` artifact per execution. Below
    ``threshold`` the decision's ``choice`` is ``UNSURE``; ``best_guess`` keeps
    the model's pick either way. The decision inherits its inputs' visibility
    unless ``visibility`` is set.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    choice: type[Choice]
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
        question = DecisionQuestion(
            name=self.choice.__name__,
            instructions=self.instructions or self.choice.__question__,
            options=self.choice.__options__,
        )

        state, images = prepare_state(inputs.artifacts)
        if images and not self.provider.supports_images:
            raise ValueError(
                f"Decision model '{self.provider.label}' does not accept images; "
                "use a provider with image support (openai/, local/ with a vision "
                "model) for inputs with Image fields."
            )

        started = time.perf_counter()
        answer = await self.provider.decide(state, question, images)
        latency_ms = (time.perf_counter() - started) * 1000

        top = answer.probabilities.get(answer.choice, answer.confidence)
        firm = self.threshold is None or (top is not None and top >= self.threshold)
        model = Decision.of(self.choice)
        decision = model(
            choice=answer.choice if firm else UNSURE,
            best_guess=answer.choice,
            probabilities=answer.probabilities,
            confidence=answer.confidence,
            threshold=self.threshold,
            subject_ids=[str(a.id) for a in inputs.artifacts],
            model=answer.model or self.provider.label,
            latency_ms=round(latency_ms, 3),
        )
        artifact = Artifact(
            type=type_registry.name_for(model),
            payload=decision.model_dump(mode="json"),
            produced_by=agent.name,
            visibility=visibility,
        )
        return EvalResult(artifacts=[artifact])


__all__ = ["DecisionEngine", "inherited_visibility", "prepare_state", "render_state"]

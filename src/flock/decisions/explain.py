"""Explanations of decisions, written by an LLM on demand.

Decision models give probabilities, no reasons. An agent subscribed to
decision handles (``.consumes(Route.UNSURE)``) calls ``.explains()`` and an LLM
writes an :class:`Explanation` of each decision that reaches it, linked to the
decision and its subject.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from flock.core.artifacts import Artifact
from flock.decisions.choice import UNSURE
from flock.decisions.engine import inherited_visibility
from flock.decisions.models import choice_of
from flock.engines.dspy_engine import DSPyEngine
from flock.registry import flock_type, type_registry
from flock.utils.runtime import Context, EvalInputs, EvalResult


DEFAULT_INSTRUCTIONS = (
    "A decision model answered a question about the input; the decision shows "
    "its answer, the probability of every option and the threshold. If the "
    f"choice is {UNSURE}, explain from the input why the question is hard to "
    "answer; otherwise explain which parts of the input support the choice. "
    "Quote or name the parts of the input you rely on. Say what information "
    "would settle the question, if any. Do not answer the question yourself."
)


@flock_type
class DecisionToExplain(BaseModel):
    """A decision as the explaining LLM sees it."""

    question: str = Field(description="The question the decision model answered")
    options: dict[str, str] = Field(
        description="Options (checklists: items) and their criteria"
    )
    choice: str = Field(description=f"The decision's answer, {UNSURE} if not firm")
    best_guess: str | None = Field(
        default=None, description="The most probable answer, also when unsure"
    )
    probabilities: dict[str, float] = Field(
        default_factory=dict,
        description="Probability per option (checklists: probability of yes per item)",
    )
    threshold: float | None = Field(
        default=None, description="Minimum probability for a firm answer"
    )
    refused: bool = Field(default=False, description="The decision model refused")
    results: dict[str, str] | None = Field(
        default=None, description="Checklists: yes, no or UNSURE per item"
    )
    refused_items: list[str] = Field(
        default_factory=list,
        description="Checklists: items the decision model refused to answer",
    )


@flock_type
class Explanation(BaseModel):
    """An LLM's explanation of one or more decisions about the same subject."""

    explanation: str = Field(
        description="Why the decision came out this way, citing the input"
    )
    missing: str | None = Field(
        default=None,
        description="Information that would settle the question, if any",
    )
    decision_ids: list[str] = Field(
        default_factory=list,
        description="Ids of the explained decisions (set by Flock, leave empty)",
    )
    questions: list[str] = Field(
        default_factory=list,
        description="Names of the explained questions (set by Flock, leave empty)",
    )
    subject_ids: list[str] = Field(
        default_factory=list,
        description="Ids of the decided artifacts (set by Flock, leave empty)",
    )
    model: str = Field(
        default="", description="LLM that wrote the explanation (set by Flock)"
    )


def decision_case(decision_type: str, payload: dict[str, Any]) -> DecisionToExplain:
    """The question, options and answer of a decision payload."""
    question = choice_of(type_registry.resolve(decision_type))
    options = dict(question.__options__) if question is not None else {}
    if payload.get("candidates") is not None:  # restricted at runtime (options=)
        candidates = set(payload["candidates"])
        options = {name: text for name, text in options.items() if name in candidates}
    text = question.__question__ if question is not None else payload.get("question")
    return DecisionToExplain(
        question=text or payload.get("question", ""),
        options=options,
        choice=payload.get("choice", UNSURE),
        best_guess=payload.get("best_guess"),
        probabilities=dict(payload.get("probabilities") or {}),
        threshold=payload.get("threshold"),
        refused=bool(payload.get("refused")),
        results=dict(payload["results"]) if payload.get("results") else None,
        refused_items=list(payload.get("refused_items") or []),
    )


class ExplainEngine(DSPyEngine):
    """Asks an LLM to explain the decisions that triggered the agent.

    The LLM gets the decided artifacts and one :class:`DecisionToExplain` per
    decision; the published :class:`Explanation` is linked to the decisions
    and keeps the subjects' visibility.
    """

    instructions: str | None = DEFAULT_INSTRUCTIONS
    enable_context: bool = False

    async def evaluate(
        self, agent: Any, ctx: Context, inputs: EvalInputs, output_group: Any
    ) -> EvalResult:
        decisions = (ctx.state or {}).get("__decisions__") or []
        if not decisions:  # another trigger: nothing to explain or link to
            return EvalResult(artifacts=[], state=dict(inputs.state))
        cases = [
            Artifact(
                type=type_registry.name_for(DecisionToExplain),
                payload=decision_case(item["type"], item["payload"]).model_dump(
                    mode="json"
                ),
                produced_by=agent.name,
            )
            for item in decisions
        ]
        augmented = EvalInputs(
            artifacts=[*inputs.artifacts, *cases], state=dict(inputs.state)
        )
        result = await super().evaluate(agent, ctx, augmented, output_group)

        visibility = inherited_visibility(inputs.artifacts)
        links = {
            "decision_ids": [item["id"] for item in decisions],
            "questions": [item["payload"].get("question", "") for item in decisions],
            "subject_ids": [str(a.id) for a in inputs.artifacts],
            "model": self._resolve_model_name(),
        }
        name = type_registry.name_for(Explanation)
        for artifact in result.artifacts:
            if artifact.type == name:
                artifact.payload = {**artifact.payload, **links}
                artifact.visibility = visibility.model_copy(deep=True)
        return result


__all__ = ["DecisionToExplain", "ExplainEngine", "Explanation", "decision_case"]

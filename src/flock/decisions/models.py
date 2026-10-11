"""Decision artifacts published by decision agents."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, create_model

from flock.decisions.choice import FAILED, PASSED, UNSURE, Question
from flock.registry import type_registry


class Decision(BaseModel):
    """One answer of a decision model to a :class:`Choice` question.

    Each Choice gets its own registered subclass (``Decision.of(Route)``) whose
    ``choice`` and ``best_guess`` fields only accept that Choice's options.
    """

    question: str = Field(
        default="", description="Name of the question class that was decided"
    )
    kind: str = Field(default="choice", description="choice, yesno, scale or checklist")
    choice: str = Field(
        description=f"Selected option, or {UNSURE} when below the threshold"
    )
    best_guess: str | None = Field(
        default=None, description="Most probable option, even when unsure"
    )
    probabilities: dict[str, float] = Field(
        default_factory=dict, description="Probability per option"
    )
    confidence: float | None = Field(
        default=None, description="Confidence reported by the decision model"
    )
    threshold: float | None = Field(
        default=None, description="Minimum top probability for a firm choice"
    )
    instructions: str | None = Field(
        default=None,
        description="The question text asked instead of the question's docstring "
        "(.decides(instructions=...))",
    )
    score: float | None = Field(
        default=None,
        description="Scale questions: probability-weighted level (0 = lowest)",
    )
    refused: bool = Field(
        default=False, description="The model refused to answer (choice is UNSURE)"
    )
    subject_ids: list[str] = Field(
        default_factory=list, description="Ids of the artifacts that were decided on"
    )
    candidates: list[str] | None = Field(
        default=None,
        description="Options the decision was asked about when they were "
        "restricted at runtime (options=)",
    )
    rounds: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Tournament rounds before the final question: candidates, "
        "groups, survivors and the top candidates of every group per round",
    )
    model: str = Field(description="Decision model that answered")
    tier: int = Field(
        default=0,
        description="Escalation tier that answered: 0 is the decider's model, "
        "1 the first model in escalate=, and so on",
    )
    attempts: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Answers of lower tiers that were not firm, oldest first: "
        "model, choice, probabilities, confidence, refused (checklists: model "
        "and the results of the escalated items)",
    )
    votes: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Ensembles: every model's answer, in the order of models=: "
        "model, choice, probabilities, confidence, refused (checklists: model "
        "and its result per item)",
    )
    mode: Literal["single", "escalation", "ensemble"] = Field(
        default="single",
        description="How the decider answers: one model, a model with "
        "escalate=, or several models with models=; recorded even when no "
        "escalation or vote happened",
    )
    shadow: dict[str, Any] | None = Field(
        default=None,
        description="Shadow mode: the shadow model's answer, recorded but not "
        "routed: model, choice (under the same threshold), best_guess, "
        "probabilities, confidence, refused, latency_ms (checklists: model, "
        "choice, best_guess, results, refused_items, latency_ms); model and "
        "error when the shadow failed",
    )
    item_thresholds: dict[str, float] = Field(
        default_factory=dict,
        description="Checklists: the items that had their own threshold instead "
        "of threshold",
    )
    review_of: str | None = Field(
        default=None,
        description="Id of the decision a person confirmed or overrode with this one",
    )
    sections: dict[str, Any] | None = Field(
        default=None,
        description="Long documents: the split text field, the sections' spans "
        "[start, end) in it and, per question (checklists: per item), the "
        "section whose answer was kept (answered_by)",
    )
    latency_ms: float | None = Field(
        default=None, description="Round trip of the decision request"
    )

    @classmethod
    def of(cls, choice: type[Question]) -> type[Decision]:
        """Return the registered Decision model for a question class (cached)."""
        if not (
            isinstance(choice, type)
            and issubclass(choice, Question)
            and choice.__options__
        ):
            raise TypeError(
                "Decision.of() expects a Choice, YesNo, Scale or Checklist subclass, "
                f"got {choice!r}"
            )
        cached = choice.__dict__.get("__decision_model__")
        if cached is not None:
            return cached

        options = tuple(choice.__options__)
        if choice.__kind__ == "checklist":
            fields: dict[str, Any] = {
                "choice": (
                    Literal[PASSED, FAILED, UNSURE],
                    Field(description="Outcome over all items"),
                ),
                "best_guess": (
                    Literal[PASSED, FAILED] | None,
                    Field(default=None, description="Outcome ignoring the threshold"),
                ),
                "results": (
                    dict[Literal[options], Literal["yes", "no", UNSURE]],
                    Field(default_factory=dict, description="Answer per item"),
                ),
                "refused_items": (
                    list[str],
                    Field(default_factory=list, description="Items the model refused"),
                ),
            }
        else:
            fields = {
                "choice": (
                    Literal[(*options, UNSURE)],
                    Field(description="Selected option"),
                ),
                "best_guess": (
                    Literal[options] | None,
                    Field(default=None, description="Most probable option"),
                ),
            }
        model = create_model(
            f"{choice.__name__}Decision",
            __base__=Decision,
            __module__=choice.__module__,
            question=(str, Field(default=choice.__name__)),
            kind=(str, Field(default=choice.__kind__)),
            **fields,
        )
        model.__flock_choice__ = choice
        type_registry.register(
            model, name=f"Decision[{choice.__module__}.{choice.__qualname__}]"
        )
        choice.__decision_model__ = model
        return model


def choice_of(model: type[BaseModel]) -> type[Question] | None:
    """Return the Choice behind a Decision model, or None for other models."""
    return getattr(model, "__flock_choice__", None)


__all__ = ["Decision", "choice_of"]

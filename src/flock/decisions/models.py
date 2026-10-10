"""Decision artifacts published by decision agents."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, create_model

from flock.decisions.choice import UNSURE, Choice
from flock.registry import type_registry


class Decision(BaseModel):
    """One answer of a decision model to a :class:`Choice` question.

    Each Choice gets its own registered subclass (``Decision.of(Route)``) whose
    ``choice`` and ``best_guess`` fields only accept that Choice's options.
    """

    question: str = Field(
        default="", description="Name of the Choice class that was decided"
    )
    choice: str = Field(
        description=f"Selected option, or {UNSURE} when below the threshold"
    )
    best_guess: str = Field(description="Most probable option, even when unsure")
    probabilities: dict[str, float] = Field(
        default_factory=dict, description="Probability per option"
    )
    confidence: float | None = Field(
        default=None, description="Confidence reported by the decision model"
    )
    threshold: float | None = Field(
        default=None, description="Minimum top probability for a firm choice"
    )
    subject_ids: list[str] = Field(
        default_factory=list, description="Ids of the artifacts that were decided on"
    )
    model: str = Field(description="Decision model that answered")
    latency_ms: float | None = Field(
        default=None, description="Round trip of the decision request"
    )

    @classmethod
    def of(cls, choice: type[Choice]) -> type[Decision]:
        """Return the registered Decision model for ``choice`` (cached)."""
        if not (isinstance(choice, type) and issubclass(choice, Choice)):
            raise TypeError(f"Decision.of() expects a Choice subclass, got {choice!r}")
        cached = choice.__dict__.get("__decision_model__")
        if cached is not None:
            return cached

        options = tuple(choice.__options__)
        model = create_model(
            f"{choice.__name__}Decision",
            __base__=Decision,
            __module__=choice.__module__,
            question=(str, Field(default=choice.__name__)),
            choice=(Literal[(*options, UNSURE)], Field(description="Selected option")),
            best_guess=(Literal[options], Field(description="Most probable option")),
        )
        model.__flock_choice__ = choice
        type_registry.register(
            model, name=f"Decision[{choice.__module__}.{choice.__qualname__}]"
        )
        choice.__decision_model__ = model
        return model


def choice_of(model: type[BaseModel]) -> type[Choice] | None:
    """Return the Choice behind a Decision model, or None for other models."""
    return getattr(model, "__flock_choice__", None)


__all__ = ["Decision", "choice_of"]

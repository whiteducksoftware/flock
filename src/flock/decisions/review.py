"""Human review: a person confirms or overrides a decision.

``await flock.review(decision_id, choice="billing")`` publishes a decision of
the same question about the same subject, made by the reviewer. It routes like
any other decision, and reviewed decisions double as labels for calibration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from flock.core.artifacts import Artifact
from flock.decisions.models import choice_of
from flock.registry import RegistryError, type_registry


if TYPE_CHECKING:
    from flock.core.orchestrator import Flock


async def review_decision(
    flock: Flock,
    decision_id: str | UUID,
    choice: str | None = None,
    reviewer: str = "human",
) -> Artifact:
    """Publish ``reviewer``'s answer to the question of decision ``decision_id``.

    ``choice`` defaults to the decision's best guess (a confirmation). The new
    decision has probability 1.0 for its choice, names the reviewer as its
    ``model`` and producer, points to the reviewed decision in ``review_of``
    and keeps its subjects, correlation and visibility. Raises ``LookupError``
    for an unknown id and ``ValueError`` for anything that cannot be reviewed.
    """
    if any(agent.name == reviewer for agent in flock.agents):
        # Agents do not consume their own outputs: a review by "tech" would
        # never reach the tech agent
        raise ValueError(
            f"Reviewer '{reviewer}' is also an agent's name; choose another name."
        )
    original = await flock.store.get(UUID(str(decision_id)))
    if original is None:
        raise LookupError(f"There is no artifact {decision_id}.")
    try:
        model = type_registry.resolve(original.type)
    except (KeyError, RegistryError):
        model = None
    question = choice_of(model) if model is not None else None
    if question is None:
        raise ValueError(f"Artifact {decision_id} ({original.type}) is not a decision.")
    if question.__kind__ == "checklist":
        raise ValueError(
            f"Checklist decisions ({question.__name__}) cannot be reviewed yet; "
            "review choice, yes/no and scale decisions."
        )
    decision = model(**original.payload)
    options = list(question.__options__)
    choice = choice if choice is not None else decision.best_guess
    if choice not in options:
        raise ValueError(
            f"'{choice}' is not an option of {question.__name__}: {', '.join(options)}."
        )
    reviewed = model(
        choice=choice,
        best_guess=choice,
        probabilities={choice: 1.0},
        confidence=1.0,
        threshold=decision.threshold,
        instructions=decision.instructions,
        # A scale's score is the level a person chose
        score=float(options.index(choice)) if question.__kind__ == "scale" else None,
        subject_ids=list(decision.subject_ids),
        model=reviewer,
        review_of=str(original.id),
    )
    return await flock.publish(
        Artifact(
            type=original.type,
            payload=reviewed.model_dump(mode="json"),
            produced_by=reviewer,
            visibility=original.visibility.model_copy(deep=True),
            correlation_id=original.correlation_id,
        )
    )


__all__ = ["review_decision"]

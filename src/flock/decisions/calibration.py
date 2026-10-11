"""Calibration: thresholds for a target precision, from labelled decisions.

Thresholds are per task, not global. ``calibrate()`` takes recorded decisions
and labels (the right answer per decided artifact) and suggests, per question
and per checklist item, the lowest threshold whose firm answers reach the
target precision; the lowest such threshold leaves the most answers firm.
Human reviews (``review_of``) are labels too: ``labels_from_reviews()``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel, Field

from flock.decisions.graph import is_decision_type


class Suggestion(BaseModel):
    """A suggested threshold for one question or checklist item."""

    question: str = Field(description="Name of the question")
    item: str | None = Field(default=None, description="Checklist item, if any")
    labeled: int = Field(description="Labelled answers considered")
    threshold: float | None = Field(
        description="Lowest threshold whose firm answers reach the target "
        "precision; None when no threshold does"
    )
    precision: float | None = Field(
        description="Share of right answers among the firm ones at that threshold"
    )
    coverage: float = Field(
        description="Share of the labelled answers that are firm at that threshold"
    )


def suggest_threshold(
    points: Iterable[tuple[float, bool]], target: float, min_support: int = 5
) -> tuple[float | None, float | None, float]:
    """The lowest confidence threshold whose answers reach ``target``.

    ``points`` are ``(confidence, correct)`` per labelled answer. A threshold
    counts only with at least ``min_support`` answers at or above it. Returns
    ``(threshold, precision, coverage)``; threshold and precision are None
    when no threshold reaches the target.
    """
    points = list(points)
    for threshold in sorted({confidence for confidence, _ in points}):
        firm = [correct for confidence, correct in points if confidence >= threshold]
        if len(firm) < min_support:
            break  # higher thresholds keep even fewer answers
        precision = sum(firm) / len(firm)
        if precision >= target:
            return threshold, precision, len(firm) / len(points)
    return None, None, 0.0


def _payload(decision: BaseModel | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(decision, BaseModel):
        return decision.model_dump(mode="json")
    return dict(decision)


def labels_from_reviews(
    decisions: Iterable[BaseModel | Mapping[str, Any]],
) -> dict[str, str]:
    """Decided artifact id -> the reviewer's answer, from human reviews."""
    labels: dict[str, str] = {}
    for decision in decisions:
        payload = _payload(decision)
        if payload.get("review_of") and payload.get("subject_ids"):
            labels[str(payload["subject_ids"][0])] = str(payload["choice"])
    return labels


def calibrate(
    decisions: Iterable[BaseModel | Mapping[str, Any]],
    labels: Mapping[str, Any],
    target_precision: float = 0.95,
    min_support: int = 5,
) -> list[Suggestion]:
    """Suggest thresholds per question, and per item for checklists.

    ``labels`` maps a decided artifact's id (the decision's first subject) to
    the right answer: an option, or for a checklist a mapping of item to
    ``"yes"`` or ``"no"``. A choice, yes/no or scale answer is its best guess
    with its probability; a checklist item's answer is yes or no, whichever is
    more probable, with that probability. Human reviews themselves are left
    out.
    """
    points: dict[tuple[str, str | None], list[tuple[float, bool]]] = {}
    for decision in decisions:
        payload = _payload(decision)
        subject_ids = payload.get("subject_ids") or []
        if payload.get("review_of") or not subject_ids:
            continue
        label = labels.get(str(subject_ids[0]))
        if label is None:
            continue
        question = str(payload.get("question"))
        probabilities = payload.get("probabilities") or {}
        if payload.get("kind") == "checklist":
            if not isinstance(label, Mapping):
                continue
            for item, p_yes in probabilities.items():
                if item not in label:
                    continue
                answer, confidence = (
                    ("yes", p_yes) if p_yes >= 0.5 else ("no", 1 - p_yes)
                )
                points.setdefault((question, item), []).append((
                    confidence,
                    answer == label[item],
                ))
        elif payload.get("best_guess") is not None:
            best = payload["best_guess"]
            points.setdefault((question, None), []).append((
                probabilities.get(best, 0.0),
                best == label,
            ))
    suggestions = []
    for (question, item), answers in points.items():
        threshold, precision, coverage = suggest_threshold(
            answers, target_precision, min_support
        )
        suggestions.append(
            Suggestion(
                question=question,
                item=item,
                labeled=len(answers),
                threshold=threshold,
                precision=precision,
                coverage=coverage,
            )
        )
    return suggestions


async def calibrate_store(
    store: Any,
    target_precision: float = 0.95,
    min_support: int = 5,
    labels: Mapping[str, Any] | None = None,
) -> list[Suggestion]:
    """``calibrate()`` over every decision in ``store``, with the human reviews
    in it (and ``labels``, which win) as labels."""
    decisions = [
        artifact.payload
        for artifact in await store.list()
        if is_decision_type(artifact.type)
    ]
    merged = {**labels_from_reviews(decisions), **(labels or {})}
    return calibrate(decisions, merged, target_precision, min_support)


__all__ = [
    "Suggestion",
    "calibrate",
    "calibrate_store",
    "labels_from_reviews",
    "suggest_threshold",
]

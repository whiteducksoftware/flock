"""Calibration: thresholds for a target precision, from labelled decisions.

Thresholds are per task, not global. ``calibrate()`` takes recorded decisions
and labels (the right answer per decided artifact and question) and suggests,
per decider and question and per checklist item, the lowest threshold whose
firm answers reach the target precision; the lowest such threshold leaves the
most answers firm. Human reviews (``review_of``) are labels too:
``labels_from_reviews()``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel, Field

from flock.core.artifacts import Artifact
from flock.decisions.graph import is_decision_type


class Suggestion(BaseModel):
    """A suggested threshold for one question or checklist item of a decider."""

    decider: str | None = Field(
        default=None, description="Agent that made the decisions, if known"
    )
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
    note: str | None = Field(
        default=None, description="Why no threshold was suggested, if not the target"
    )


def _check(target: float, min_support: int) -> None:
    if not 0.0 < target <= 1.0:
        raise ValueError(f"The target precision must be in (0, 1], got {target}.")
    if min_support < 1:
        raise ValueError(f"min_support must be at least 1, got {min_support}.")


def suggest_threshold(
    points: Iterable[tuple[float, bool]], target: float, min_support: int = 5
) -> tuple[float | None, float | None, float]:
    """The lowest confidence threshold whose answers reach ``target``.

    ``points`` are ``(confidence, correct)`` per labelled answer. A threshold
    counts only with at least ``min_support`` answers at or above it. Returns
    ``(threshold, precision, coverage)``; threshold and precision are None
    when no threshold reaches the target.
    """
    _check(target, min_support)
    points = list(points)
    for threshold in sorted({confidence for confidence, _ in points}):
        firm = [correct for confidence, correct in points if confidence >= threshold]
        if len(firm) < min_support:
            break  # higher thresholds keep even fewer answers
        precision = sum(firm) / len(firm)
        if precision >= target:
            return threshold, precision, len(firm) / len(points)
    return None, None, 0.0


def _unpack(decision: Any) -> tuple[str | None, dict[str, Any]]:
    """(decider, payload) of an artifact, a decision model or a payload."""
    if isinstance(decision, Artifact):
        return decision.produced_by, dict(decision.payload)
    if isinstance(decision, BaseModel):
        return None, decision.model_dump(mode="json")
    return None, dict(decision)


def labels_from_reviews(decisions: Iterable[Any]) -> dict[str, dict[str, str]]:
    """Decided artifact id -> question -> the reviewer's answer."""
    labels: dict[str, dict[str, str]] = {}
    for decision in decisions:
        _, payload = _unpack(decision)
        if payload.get("review_of") and payload.get("subject_ids"):
            subject = str(payload["subject_ids"][0])
            question = str(payload.get("question"))
            labels.setdefault(subject, {})[question] = str(payload["choice"])
    return labels


def calibrate(
    decisions: Iterable[Any],
    labels: Mapping[str, Mapping[str, Any]],
    target_precision: float = 0.95,
    min_support: int = 5,
) -> list[Suggestion]:
    """Suggest thresholds per decider and question, and per checklist item.

    ``decisions`` are decision artifacts (their producer is the decider),
    decision models or payloads (decider unknown). ``labels`` maps a decided
    artifact's id (the decision's first subject) to the right answer per
    question name: an option, or for a checklist a mapping of item to
    ``"yes"`` or ``"no"``. A choice, yes/no or scale answer is its best guess
    with its probability (its confidence when it has none, as in routing); a
    checklist item's answer is yes or no, whichever is more probable, with
    that probability. Human reviews themselves are left out.
    """
    _check(target_precision, min_support)
    points: dict[tuple[str | None, str, str | None], list[tuple[float, bool]]] = {}
    multi_stage: set[tuple[str | None, str]] = set()
    for decision in decisions:
        decider, payload = _unpack(decision)
        subject_ids = payload.get("subject_ids") or []
        if payload.get("review_of") or not subject_ids:
            continue
        question = str(payload.get("question"))
        if payload.get("mode", "single") != "single" or (
            # Decisions recorded before the mode existed
            payload.get("attempts") or payload.get("votes") or payload.get("tier")
        ):
            # A threshold acts per tier or per vote there, not on the final answer
            multi_stage.add((decider, question))
        label = (labels.get(str(subject_ids[0])) or {}).get(question)
        if label is None:
            continue
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
                key = (decider, question, item)
                points.setdefault(key, []).append((confidence, answer == label[item]))
        elif payload.get("best_guess") is not None:
            best = payload["best_guess"]
            # As in routing: the confidence when the choice has no probability
            confidence = probabilities.get(best, payload.get("confidence"))
            if confidence is None:
                continue
            key = (decider, question, None)
            points.setdefault(key, []).append((confidence, best == label))
    suggestions = []
    for (decider, question, item), answers in points.items():
        if (decider, question) in multi_stage:
            suggestions.append(
                Suggestion(
                    decider=decider,
                    question=question,
                    item=item,
                    labeled=len(answers),
                    threshold=None,
                    precision=None,
                    coverage=0.0,
                    note="escalation or ensemble: thresholds act per tier or "
                    "vote, not calibrated",
                )
            )
            continue
        threshold, precision, coverage = suggest_threshold(
            answers, target_precision, min_support
        )
        if threshold is not None:
            note = None
        elif len(answers) < min_support:
            note = f"too few labels: {len(answers)}, min_support is {min_support}"
        else:
            note = f"no threshold with {min_support} or more answers reaches the target"
        suggestions.append(
            Suggestion(
                decider=decider,
                question=question,
                item=item,
                labeled=len(answers),
                threshold=threshold,
                precision=precision,
                coverage=coverage,
                note=note,
            )
        )
    return suggestions


async def calibrate_store(
    store: Any,
    target_precision: float = 0.95,
    min_support: int = 5,
    labels: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[Suggestion]:
    """``calibrate()`` over every decision in ``store``, per decider, with the
    human reviews in it (and ``labels``, which win) as labels."""
    # A standalone process may not have imported the application's question
    # types; persisted decisions are recognised by their type name too
    decisions = [
        artifact
        for artifact in await store.list()
        if artifact.type.startswith("Decision[") or is_decision_type(artifact.type)
    ]
    merged: dict[str, dict[str, Any]] = labels_from_reviews(decisions)
    for subject, answers in (labels or {}).items():
        merged.setdefault(subject, {}).update(answers)
    return calibrate(decisions, merged, target_precision, min_support)


__all__ = [
    "Suggestion",
    "calibrate",
    "calibrate_store",
    "labels_from_reviews",
    "suggest_threshold",
]

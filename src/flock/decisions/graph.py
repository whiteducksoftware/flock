"""Dashboard graph data for decision agents, choice subscribers and decisions."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import TYPE_CHECKING, Any

from flock.decisions.choice import UNSURE
from flock.decisions.models import Decision
from flock.registry import RegistryError, type_registry


if TYPE_CHECKING:
    from flock.core.agent import Agent


def is_decision_type(type_name: str) -> bool:
    """True if ``type_name`` names a registered Decision model."""
    try:
        return issubclass(type_registry.resolve(type_name), Decision)
    except RegistryError:
        return False


SAMPLES_PER_OPTION = 6


def decider_info(
    agent: Agent,
    produced: Iterable[tuple[str, Mapping[str, Any]]],
    subject_thumb: Callable[[Mapping[str, Any]], str | None] | None = None,
) -> dict[str, Any] | None:
    """Question, options and per-option counts of a decision agent, else None.

    ``produced`` yields ``(type_name, payload)`` of the artifacts in view,
    oldest first. With ``subject_thumb`` (decision payload -> thumbnail of the
    decided image), the result also holds ``samples``: the latest image
    thumbnails per option with the chosen option's probability.
    """
    from flock.decisions.engine import DecisionEngine

    engine = next((e for e in agent.engines if isinstance(e, DecisionEngine)), None)
    if engine is None:
        return None
    choice = engine.choice
    type_name = type_registry.name_for(Decision.of(choice))
    counts = dict.fromkeys(choice.__options__, 0)
    if engine.threshold is not None:
        counts[UNSURE] = 0
    samples: dict[str, list[dict[str, Any]]] = {}
    for produced_type, payload in produced:
        if produced_type != type_name:
            continue
        option = payload.get("choice")
        counts[option] = counts.get(option, 0) + 1
        thumb = subject_thumb(payload) if subject_thumb else None
        if thumb:
            probabilities = payload.get("probabilities") or {}
            samples.setdefault(option, []).append({
                "thumb": thumb,
                "p": probabilities.get(payload.get("best_guess"), 0.0),
            })
    info = {
        "question": choice.__name__,
        "instructions": engine.instructions or choice.__question__,
        "options": list(choice.__options__),
        "threshold": engine.threshold,
        "model": engine.provider.label,
        "counts": counts,
    }
    if samples:
        info["samples"] = {
            option: items[-SAMPLES_PER_OPTION:][::-1]
            for option, items in samples.items()
        }
    return info


def choice_type_labels(agent: Agent) -> dict[str, str]:
    """Readable labels for the decision types an agent consumes via choice handles."""
    handles: dict[str, list[str]] = {}
    for subscription in agent.subscriptions:
        if subscription.choice is None:
            continue
        for type_name in subscription.type_names:
            handles.setdefault(type_name, []).append(repr(subscription.choice))
    return {name: "◆ " + " | ".join(refs) for name, refs in handles.items()}


def decision_view(
    payload: Mapping[str, Any], subject_thumb: str | None = None
) -> dict[str, Any]:
    """Decision fields for the dashboard's decision artifact view."""
    view = {
        "question": payload.get("question"),
        "choice": payload.get("choice"),
        "bestGuess": payload.get("best_guess"),
        "probabilities": dict(payload.get("probabilities") or {}),
        "confidence": payload.get("confidence"),
        "threshold": payload.get("threshold"),
        "model": payload.get("model"),
        "latencyMs": payload.get("latency_ms"),
    }
    if subject_thumb:
        view["subjectThumb"] = subject_thumb
    return view


__all__ = ["choice_type_labels", "decider_info", "decision_view", "is_decision_type"]

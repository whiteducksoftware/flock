"""Dashboard graph data for decision agents, choice subscribers and decisions."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import TYPE_CHECKING, Any

from flock.decisions.choice import FAILED, PASSED, UNSURE, Question
from flock.decisions.models import Decision
from flock.registry import RegistryError, type_registry


if TYPE_CHECKING:
    from flock.core.agent import Agent
    from flock.decisions.engine import DecisionEngine


def is_decision_type(type_name: str) -> bool:
    """True if ``type_name`` names a registered Decision model."""
    try:
        return issubclass(type_registry.resolve(type_name), Decision)
    except RegistryError:
        return False


SAMPLES_PER_OPTION = 6


def _question_info(
    question: type[Question],
    instructions: str | None,
    threshold: float | None,
    produced: list[tuple[str, Mapping[str, Any]]],
    subject_thumb: Callable[[Mapping[str, Any]], str | None] | None,
) -> dict[str, Any]:
    type_name = type_registry.name_for(Decision.of(question))
    checklist = question.__kind__ == "checklist"
    if checklist:
        counts = dict.fromkeys([PASSED, FAILED, UNSURE], 0)
        item_stats = {item: [0, 0, 0] for item in question.__options__}
    else:
        counts = dict.fromkeys(question.__options__, 0)
        if threshold is not None:
            counts[UNSURE] = 0
    refused = 0
    scores: list[float] = []
    samples: dict[str, list[dict[str, Any]]] = {}
    for produced_type, payload in produced:
        if produced_type != type_name:
            continue
        option = payload.get("choice")
        counts[option] = counts.get(option, 0) + 1
        refused += bool(payload.get("refused"))
        if payload.get("score") is not None:
            scores.append(payload["score"])
        if checklist:
            for item, result in (payload.get("results") or {}).items():
                if item in item_stats:
                    item_stats[item][("yes", "no", UNSURE).index(result)] += 1
        thumb = subject_thumb(payload) if subject_thumb else None
        if thumb:
            probabilities = payload.get("probabilities") or {}
            samples.setdefault(option, []).append({
                "thumb": thumb,
                "p": probabilities.get(payload.get("best_guess"), 0.0),
            })
    info: dict[str, Any] = {
        "name": question.__name__,
        "kind": question.__kind__,
        "instructions": instructions or question.__question__,
        "options": list(question.__options__),
        "counts": counts,
    }
    if refused:
        info["refused"] = refused
    if question.__kind__ == "scale" and scores:
        info["meanScore"] = sum(scores) / len(scores)
    if checklist:
        # [yes, no, unsure] per item, in item order; descriptions for tooltips
        info["itemStats"] = [item_stats[item] for item in question.__options__]
        info["descriptions"] = dict(question.__options__)
    if samples:
        info["samples"] = {
            option: items[-SAMPLES_PER_OPTION:][::-1]
            for option, items in samples.items()
        }
    return info


def decider_info(
    agent: Agent,
    produced: Iterable[tuple[str, Mapping[str, Any]]],
    subject_thumb: Callable[[Mapping[str, Any]], str | None] | None = None,
) -> dict[str, Any] | None:
    """Model, threshold and per-question data of a decision agent, else None.

    Each question lists its kind, options and how often each option was
    chosen. ``produced`` yields ``(type_name, payload)`` of the artifacts in
    view, oldest first. With ``subject_thumb`` (decision payload -> thumbnail
    of the decided image), a question also holds ``samples``: the latest image
    thumbnails per option with the chosen option's probability. Scale
    questions carry the ``meanScore`` of their decisions, questions with
    refusals their ``refused`` count. With escalation, ``escalate`` lists the
    models asked after the decider's own, in order. An ensemble lists its
    models in ``ensemble`` and its ``vote``. A shadow lists its ``model`` and
    how many decisions were ``compared`` and ``agree``.
    """
    from flock.decisions.engine import DecisionEngine

    engine = next((e for e in agent.engines if isinstance(e, DecisionEngine)), None)
    if engine is None:
        return None
    produced = list(produced)
    info: dict[str, Any] = {
        "model": engine.provider.label,
        "threshold": engine.threshold,
        "questions": [
            _question_info(
                question, engine.instructions, engine.threshold, produced, subject_thumb
            )
            for question in engine.questions
        ],
    }
    if engine.tournament is not None:
        info["tournament"] = {
            "groupSize": engine.tournament.group_size,
            "keep": engine.tournament.keep,
        }
    if engine.escalation:
        info["escalate"] = [provider.label for provider in engine.escalation]
    if engine.ensemble:
        info["ensemble"] = [provider.label for provider in engine.ensemble]
        info["vote"] = engine.vote
    if engine.shadow is not None:
        info["shadow"] = _shadow_info(engine, produced)
    if engine.item_thresholds:
        info["itemThresholds"] = dict(engine.item_thresholds)
    return info


def _shadow_info(
    engine: DecisionEngine, produced: list[tuple[str, Mapping[str, Any]]]
) -> dict[str, Any]:
    """The shadow model and how often its choice matched the decision."""
    types = {type_registry.name_for(Decision.of(q)) for q in engine.questions}
    compared = agree = 0
    for type_name, payload in produced:
        shadow = payload.get("shadow")
        if type_name not in types or not shadow or "error" in shadow:
            continue
        compared += 1
        agree += shadow.get("choice") == payload.get("choice")
    return {"model": engine.shadow.label, "compared": compared, "agree": agree}


def choice_type_labels(agent: Agent) -> dict[str, str]:
    """Readable labels for the decision types an agent consumes via choice handles."""
    handles: dict[str, list[str]] = {}
    for subscription in agent.subscriptions:
        for type_name, ref in subscription.choices.items():
            handles.setdefault(type_name, []).append(repr(ref))
    return {name: "◆ " + " | ".join(refs) for name, refs in handles.items()}


def decision_label(payload: Mapping[str, Any]) -> str | None:
    """Edge label of a decision: the option, qualified for yes/no and scale
    questions (``Urgent.yes``), whose options mean little on their own."""
    choice = payload.get("choice")
    if choice is None or payload.get("kind", "choice") == "choice":
        return choice
    return f"{payload.get('question')}.{choice}"


def decision_view(
    payload: Mapping[str, Any],
    subject_thumb: str | None = None,
    levels: list[str] | None = None,
) -> dict[str, Any]:
    """Decision fields for the dashboard's decision artifact view.

    ``levels`` are the ordered options of a scale question or the items of a
    checklist.
    """
    view = {
        "question": payload.get("question"),
        "kind": payload.get("kind", "choice"),
        "choice": payload.get("choice"),
        "bestGuess": payload.get("best_guess"),
        "probabilities": dict(payload.get("probabilities") or {}),
        "confidence": payload.get("confidence"),
        "threshold": payload.get("threshold"),
        "model": payload.get("model"),
        "latencyMs": payload.get("latency_ms"),
        "score": payload.get("score"),
        "refused": bool(payload.get("refused")),
    }
    if payload.get("rounds"):
        view["rounds"] = list(payload["rounds"])
    if payload.get("candidates") is not None:
        view["candidates"] = list(payload["candidates"])
    if payload.get("attempts"):
        view["tier"] = payload.get("tier", 0)
        view["attempts"] = list(payload["attempts"])
    if payload.get("votes"):
        view["votes"] = list(payload["votes"])
    if payload.get("shadow"):
        view["shadow"] = dict(payload["shadow"])
    if payload.get("review_of"):
        view["reviewOf"] = payload["review_of"]
    if payload.get("sections"):
        sections = payload["sections"]
        view["sections"] = {
            "field": sections.get("field"),
            "spans": [list(span) for span in sections.get("spans") or []],
            "answeredBy": dict(sections.get("answered_by") or {}),
        }
    if view["kind"] == "checklist":
        view["items"] = levels or list(payload.get("results") or {})
        view["results"] = dict(payload.get("results") or {})
        view["refusedItems"] = list(payload.get("refused_items") or [])
    elif levels:
        view["levels"] = levels
    if subject_thumb:
        view["subjectThumb"] = subject_thumb
    return view


def is_explanation_type(type_name: str) -> bool:
    """True for the type name of :class:`~flock.decisions.explain.Explanation`."""
    from flock.decisions.explain import Explanation

    return type_name == type_registry.name_for(Explanation)


def explanation_view(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Explanation fields for the dashboard's explanation artifact view."""
    return {
        "explanation": payload.get("explanation", ""),
        "missing": payload.get("missing"),
        "model": payload.get("model", ""),
        "questions": list(payload.get("questions") or []),
    }


def explanations_by_decision(
    explanations: Iterable[tuple[Mapping[str, Any], str | None]],
) -> dict[str, dict[str, Any]]:
    """Decision id -> the latest explanation of it, from ``(payload, producer)``
    pairs in publication order."""
    by_decision: dict[str, dict[str, Any]] = {}
    for payload, producer in explanations:
        view = {
            "explanation": payload.get("explanation", ""),
            "missing": payload.get("missing"),
            "model": payload.get("model", ""),
            "by": producer,
        }
        for decision_id in payload.get("decision_ids") or []:
            by_decision[str(decision_id)] = view
    return by_decision


def _coverage_checklist(type_name: str) -> type[Question] | None:
    try:
        model = type_registry.resolve(type_name)
    except (KeyError, RegistryError):
        return None
    return getattr(model, "__flock_checklist__", None)


def is_coverage_type(type_name: str) -> bool:
    """True for the type name of a ``Coverage.of(checklist)`` model."""
    return _coverage_checklist(type_name) is not None


def coverage_view(type_name: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Coverage fields for the dashboard, shaped like a checklist decision."""
    checklist = _coverage_checklist(type_name)
    items = list(checklist.__options__) if checklist is not None else []
    return {
        "question": payload.get("question"),
        "kind": "checklist",
        "group": payload.get("group"),
        "combine": payload.get("combine"),
        "documents": len(payload.get("subject_ids") or []),
        "choice": payload.get("choice"),
        "results": dict(payload.get("results") or {}),
        "items": items or list(payload.get("results") or {}),
        "probabilities": {},
        "refusedItems": [],
    }


def aggregator_info(
    agent: Agent, produced: Iterable[tuple[str, Mapping[str, Any]]]
) -> dict[str, Any] | None:
    """Checklist, grouping and outcome counts of an aggregating agent, else None.

    ``produced`` yields ``(type_name, payload)`` of the artifacts in view; the
    coverage with the highest revision of each group counts.
    """
    from flock.decisions.coverage import AggregateEngine, Coverage

    engine = next((e for e in agent.engines if isinstance(e, AggregateEngine)), None)
    if engine is None:
        return None
    coverage_type = type_registry.name_for(Coverage.of(engine.question))
    current: dict[str, Mapping[str, Any]] = {}  # group -> highest revision
    for type_name, payload in produced:
        if type_name != coverage_type:
            continue
        group = str(payload.get("group"))
        if payload.get("revision", 0) >= current.get(group, {}).get("revision", 0):
            current[group] = payload
    groups = {PASSED: 0, FAILED: 0, UNSURE: 0}
    for payload in current.values():
        choice = str(payload.get("choice"))
        groups[choice] = groups.get(choice, 0) + 1
    return {
        "question": engine.question.__name__,
        "by": engine.by if isinstance(engine.by, str) else "custom",
        "combine": engine.combine,
        "groups": groups,
    }


def reviews_by_decision(
    reviews: Iterable[tuple[Mapping[str, Any], str | None]],
) -> dict[str, dict[str, Any]]:
    """Decision id -> the latest review of it, from ``(payload, producer)``
    pairs of decisions in publication order."""
    by_decision: dict[str, dict[str, Any]] = {}
    for payload, producer in reviews:
        if payload.get("review_of"):
            by_decision[str(payload["review_of"])] = {
                "choice": payload.get("choice"),
                "by": producer,
            }
    return by_decision


__all__ = [
    "aggregator_info",
    "choice_type_labels",
    "coverage_view",
    "decider_info",
    "decision_label",
    "decision_view",
    "explanation_view",
    "explanations_by_decision",
    "is_coverage_type",
    "is_decision_type",
    "is_explanation_type",
    "reviews_by_decision",
]

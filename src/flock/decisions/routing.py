"""Deliver a decision's subject to agents that subscribed to one of its options."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from flock.decisions.models import Decision
from flock.registry import RegistryError, type_registry


if TYPE_CHECKING:
    from pydantic import BaseModel

    from flock.core.agent import Agent
    from flock.core.artifacts import Artifact
    from flock.core.store import BlackboardStore


def is_decision(artifact: Artifact) -> bool:
    """True if ``artifact`` holds a Decision."""
    try:
        return issubclass(type_registry.resolve(artifact.type), Decision)
    except RegistryError:
        return False


def decision_meta(artifacts: list[Artifact]) -> list[dict[str, Any]]:
    """Decision payloads among ``artifacts``, for ``Context.decisions``."""
    return [
        {
            "id": str(artifact.id),
            "type": artifact.type,
            "payload": dict(artifact.payload),
        }
        for artifact in artifacts
        if is_decision(artifact)
    ]


def subject_ids(artifacts: list[Artifact]) -> set[UUID]:
    """Ids of the artifacts the given decisions were made about."""
    return {
        UUID(sid)
        for artifact in artifacts
        if is_decision(artifact)
        for sid in artifact.payload.get("subject_ids", [])
    }


async def resolve_subjects(
    store: BlackboardStore, agent: Agent, artifacts: list[Artifact]
) -> list[Artifact]:
    """Replace decisions from choice subscriptions with their subjects.

    Agents that subscribed with a Choice handle (``.consumes(Route.billing)``)
    work on what was decided about, not on the decision. Other inputs pass
    through unchanged. A subject the agent may not read is an error rather than
    a silently smaller input.
    """
    routed_types = {
        name for subscription in agent.subscriptions for name in subscription.choices
    }
    if not routed_types:
        return artifacts

    resolved: list[Artifact] = []
    seen: set[str] = set()  # several decisions about one subject deliver it once
    for artifact in artifacts:
        if artifact.type not in routed_types:
            resolved.append(artifact)
            continue
        for sid in artifact.payload.get("subject_ids", []):
            if sid in seen:
                continue
            seen.add(sid)
            subject = await store.get(UUID(sid))
            if subject is None or not subject.visibility.allows(agent.identity):
                raise LookupError(
                    f"Subject {sid} of decision {artifact.id} is not available "
                    f"to agent '{agent.name}'."
                )
            resolved.append(subject)
    return resolved


def same_subject(decision: BaseModel) -> tuple[str, ...]:
    """Join key of decisions about the same artifacts (their ``subject_ids``)."""
    return tuple(getattr(decision, "subject_ids", ()))


__all__ = [
    "decision_meta",
    "is_decision",
    "resolve_subjects",
    "same_subject",
    "subject_ids",
]

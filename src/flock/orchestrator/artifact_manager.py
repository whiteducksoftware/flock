"""Artifact publishing and persistence."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pydantic import BaseModel

from flock.core.artifacts import Artifact
from flock.core.visibility import PublicVisibility, Visibility
from flock.registry import type_registry


if TYPE_CHECKING:
    from flock.core import Flock
    from flock.core.store import BlackboardStore
    from flock.orchestrator import AgentScheduler


class ArtifactManager:
    """Manages artifact publishing and persistence.

    Responsibilities:
    - Normalize different input types (BaseModel, dict, Artifact)
    - Persist artifacts to store
    - Trigger scheduling after publish
    - Handle batch publishing
    """

    def __init__(
        self, orchestrator: Flock, store: BlackboardStore, scheduler: AgentScheduler
    ):
        """Initialize artifact manager.

        Args:
            orchestrator: Flock orchestrator instance
            store: Blackboard store for persistence
            scheduler: Scheduler for triggering agent execution
        """
        self._orchestrator = orchestrator
        self._store = store
        self._scheduler = scheduler
        self._logger = orchestrator._logger

    async def publish(
        self,
        obj: BaseModel | dict | Artifact,
        *,
        visibility: Visibility | None = None,
        correlation_id: str | None = None,
        partition_key: str | None = None,
        tags: set[str] | None = None,
        is_dashboard: bool = False,
        schedule_immediately: bool = True,
    ) -> Artifact:
        """Publish an artifact to the blackboard (event-driven).

        All agents with matching subscriptions will be triggered according to
        their filters (type, predicates, visibility, etc).

        Args:
            obj: Object to publish (BaseModel instance, dict, or Artifact)
            visibility: Access control (defaults to PublicVisibility)
            correlation_id: Optional correlation ID for request tracing
            partition_key: Optional partition key for sharding
            tags: Optional tags for channel-based routing
            is_dashboard: Internal flag for dashboard events

        Returns:
            The published Artifact

        Examples:
            >>> # Publish a model instance (recommended)
            >>> task = Task(name="Deploy", priority=5)
            >>> await artifact_manager.publish(task)

            >>> # Publish with custom visibility
            >>> await artifact_manager.publish(
            ...     task, visibility=PrivateVisibility(agents={"admin"})
            ... )
        """
        # Handle different input types
        if isinstance(obj, Artifact):
            # Already an artifact - publish as-is
            artifact = obj
        elif isinstance(obj, BaseModel):
            # BaseModel instance - get type from registry
            type_name = type_registry.name_for(type(obj))
            artifact = Artifact(
                type=type_name,
                payload=obj.model_dump(),
                produced_by="external",
                visibility=visibility or PublicVisibility(),
                correlation_id=correlation_id or uuid4(),
                partition_key=partition_key,
                tags=tags or set(),
            )
        elif isinstance(obj, dict):
            # Dict must have 'type' key
            if "type" not in obj:
                raise ValueError(
                    "Dict input must contain 'type' key. "
                    "Example: {'type': 'Task', 'name': 'foo', 'priority': 5}"
                )
            # Support both {'type': 'X', 'payload': {...}} and {'type': 'X', ...}
            type_name = obj["type"]
            if "payload" in obj:
                payload = obj["payload"]
            else:
                payload = {k: v for k, v in obj.items() if k != "type"}

            artifact = Artifact(
                type=type_name,
                payload=payload,
                produced_by="external",
                visibility=visibility or PublicVisibility(),
                correlation_id=correlation_id,
                partition_key=partition_key,
                tags=tags or set(),
            )
        else:
            raise TypeError(
                f"Cannot publish object of type {type(obj).__name__}. "
                "Expected BaseModel, dict, or Artifact."
            )

        if schedule_immediately:
            await self.persist_and_schedule(artifact)
        else:
            await self.persist(artifact)

        return artifact

    async def publish_many(
        self,
        objects: Iterable[BaseModel | dict | Artifact],
        schedule_immediately: bool = True,
        **kwargs: Any,
    ) -> list[Artifact]:
        """Publish multiple artifacts at once (event-driven).

        Args:
            objects: Iterable of objects to publish
            **kwargs: Passed to each publish() call (visibility, tags, etc)

        Returns:
            List of published Artifacts

        Example:
            >>> tasks = [
            ...     Task(name="Deploy", priority=5),
            ...     Task(name="Test", priority=3),
            ... ]
            >>> await artifact_manager.publish_many(tasks, tags={"sprint-3"})
        """
        artifacts = []
        for obj in objects:
            artifact = await self.publish(
                obj, schedule_immediately=schedule_immediately, **kwargs
            )
            artifacts.append(artifact)
        return artifacts

    async def persist_and_schedule(self, artifact: Artifact) -> None:
        """Persist artifact to store and trigger scheduling.

        Args:
            artifact: Artifact to publish
        """
        await self._store.publish(artifact)
        self._orchestrator.metrics["artifacts_published"] += 1
        await self._scheduler.schedule_artifact(artifact)

    async def persist(self, artifact: Artifact) -> None:
        """Persist artifact to store without scheduling.

        Args:
            artifact: Artifact to publish
        """
        await self._store.publish(artifact)
        self._orchestrator.metrics["artifacts_published"] += 1


__all__ = ["ArtifactManager"]

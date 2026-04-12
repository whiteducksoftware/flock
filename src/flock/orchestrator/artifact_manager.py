"""Artifact publishing and persistence."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pydantic import BaseModel

from flock.core.artifacts import Artifact
from flock.core.visibility import PublicVisibility, Visibility
from flock.logging.logging import get_logger
from flock.models.changelog import ChangelogEvent, ChangelogEventType
from flock.registry import type_registry


if TYPE_CHECKING:
    from flock.components.server.changelog.stream_dispatcher import StreamDispatcher
    from flock.core import Flock
    from flock.core.store import BlackboardStore
    from flock.orchestrator import AgentScheduler

logger = get_logger(__name__)


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
        # Late-bound by ChangelogStreamComponent.on_startup_async()
        self._stream_dispatcher: StreamDispatcher | None = None
        # Cascade depth tracking — prevents unbounded A→B→A loops
        self._cascade_depths: dict[str, int] = {}
        self._max_cascade_depth: int = 10

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
                correlation_id=correlation_id or str(uuid4()),
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
        """Persist artifact to store, notify stream, and trigger scheduling.

        Args:
            artifact: Artifact to publish
        """
        # Check cascade depth before scheduling
        cid = artifact.correlation_id
        if cid:
            depth = self._cascade_depths.get(cid, 0) + 1
            if depth > self._max_cascade_depth:
                logger.warning(
                    "Cascade depth %d exceeded for correlation_id=%s "
                    "— persisting but skipping schedule",
                    depth,
                    cid,
                )
                changelog_event = self._build_changelog_event(artifact)
                await self._store.publish(artifact, changelog_event)
                self._orchestrator.metrics["artifacts_published"] += 1
                self._notify_dispatcher(changelog_event)
                return
            self._cascade_depths[cid] = depth

        changelog_event = self._build_changelog_event(artifact)
        await self._store.publish(artifact, changelog_event)
        self._orchestrator.metrics["artifacts_published"] += 1
        # schedule_artifact triggers component initialization (including
        # ExternalAgentScheduler subscribe), so it must run BEFORE the
        # dispatcher notification — otherwise the event arrives before
        # the scheduler is listening.
        await self._scheduler.schedule_artifact(artifact)
        self._notify_dispatcher(changelog_event)

    async def persist(self, artifact: Artifact) -> None:
        """Persist artifact to store without scheduling.

        Args:
            artifact: Artifact to publish
        """
        changelog_event = self._build_changelog_event(artifact)
        await self._store.publish(artifact, changelog_event)
        self._orchestrator.metrics["artifacts_published"] += 1
        self._notify_dispatcher(changelog_event)

    def _notify_dispatcher(self, event: ChangelogEvent) -> None:
        """Fire-and-forget push to StreamDispatcher subscribers."""
        if self._stream_dispatcher is not None:
            self._stream_dispatcher.publish(event)

    def _build_changelog_event(self, artifact: Artifact) -> ChangelogEvent:
        """Construct a changelog event from a published artifact."""
        return ChangelogEvent(
            event_type=ChangelogEventType.artifact_published,
            artifact_id=artifact.id,
            artifact_type=artifact.type,
            produced_by=artifact.produced_by,
            correlation_id=artifact.correlation_id,
            visibility=artifact.visibility.model_dump(mode="json"),
            timestamp=artifact.created_at,
            payload_summary={
                "tags": sorted(artifact.tags) if artifact.tags else [],
                "version": artifact.version,
            },
        )


__all__ = ["ArtifactManager"]

from __future__ import annotations


"""Blackboard storage primitives."""

from asyncio import Lock
from collections import defaultdict
from typing import TYPE_CHECKING, TypeVar

from flock.registry import type_registry


if TYPE_CHECKING:
    import builtins
    from collections.abc import Iterable
    from uuid import UUID

    from flock.artifacts import Artifact

T = TypeVar("T")


class BlackboardStore:
    async def publish(self, artifact: Artifact) -> None:
        raise NotImplementedError

    async def get(self, artifact_id: UUID) -> Artifact | None:
        raise NotImplementedError

    async def list(self) -> builtins.list[Artifact]:
        raise NotImplementedError

    async def list_by_type(self, type_name: str) -> builtins.list[Artifact]:
        raise NotImplementedError

    async def get_by_type(self, artifact_type: type[T]) -> builtins.list[T]:
        """Get artifacts by Pydantic type, returning data already cast.

        Args:
            artifact_type: The Pydantic model class (e.g., BugAnalysis)

        Returns:
            List of data objects of the specified type (not Artifact wrappers)

        Example:
            bug_analyses = await store.get_by_type(BugAnalysis)
            # Returns list[BugAnalysis] directly, no .data access needed
        """
        raise NotImplementedError


class InMemoryBlackboardStore(BlackboardStore):
    """Simple in-memory implementation suitable for local dev and tests."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._by_id: dict[UUID, Artifact] = {}
        self._by_type: dict[str, list[Artifact]] = defaultdict(list)

    async def publish(self, artifact: Artifact) -> None:
        async with self._lock:
            self._by_id[artifact.id] = artifact
            self._by_type[artifact.type].append(artifact)

    async def get(self, artifact_id: UUID) -> Artifact | None:
        async with self._lock:
            return self._by_id.get(artifact_id)

    async def list(self) -> builtins.list[Artifact]:
        async with self._lock:
            return list(self._by_id.values())

    async def list_by_type(self, type_name: str) -> builtins.list[Artifact]:
        async with self._lock:
            canonical = type_registry.resolve_name(type_name)
            return list(self._by_type.get(canonical, []))

    async def get_by_type(self, artifact_type: type[T]) -> builtins.list[T]:
        """Get artifacts by Pydantic type, returning data already cast.

        Args:
            artifact_type: The Pydantic model class (e.g., BugAnalysis)

        Returns:
            List of data objects of the specified type (not Artifact wrappers)
        """
        async with self._lock:
            # Get canonical name from the type
            canonical = type_registry.resolve_name(artifact_type.__name__)
            artifacts = self._by_type.get(canonical, [])
            # Reconstruct Pydantic models from payload dictionaries
            return [artifact_type(**artifact.payload) for artifact in artifacts]  # type: ignore

    async def extend(self, artifacts: Iterable[Artifact]) -> None:  # pragma: no cover - helper
        for artifact in artifacts:
            await self.publish(artifact)


__all__ = [
    "BlackboardStore",
    "InMemoryBlackboardStore",
]

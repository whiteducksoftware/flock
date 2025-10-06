from __future__ import annotations


"""Blackboard storage primitives."""

from asyncio import Lock
from collections import defaultdict
from typing import TYPE_CHECKING

from flock.registry import type_registry


if TYPE_CHECKING:
    import builtins
    from collections.abc import Iterable
    from uuid import UUID

    from flock.artifacts import Artifact


class BlackboardStore:
    async def publish(self, artifact: Artifact) -> None:
        raise NotImplementedError

    async def get(self, artifact_id: UUID) -> Artifact | None:
        raise NotImplementedError

    async def list(self) -> builtins.list[Artifact]:
        raise NotImplementedError

    async def list_by_type(self, type_name: str) -> builtins.list[Artifact]:
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

    async def extend(self, artifacts: Iterable[Artifact]) -> None:  # pragma: no cover - helper
        for artifact in artifacts:
            await self.publish(artifact)


__all__ = [
    "BlackboardStore",
    "InMemoryBlackboardStore",
]

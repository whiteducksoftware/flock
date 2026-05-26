from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class VectorHit:
    """Result object returned from vector search."""

    id: str
    content: str | None
    metadata: dict[str, Any]
    score: float  # similarity score (higher = more similar)


class VectorAdapter(ABC):
    """Protocol for vector-store adapters."""

    def __init__(self, **kwargs):
        """Store-specific kwargs are passed through subclass constructor."""
        super().__init__()

    # ----------------------
    # CRUD operations
    # ----------------------
    @abstractmethod
    def add(
        self,
        *,
        id: str,
        content: str,
        embedding: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> None:  # pragma: no cover – interface
        """Insert or upsert a single document."""

    @abstractmethod
    def query(
        self, *, embedding: list[float], k: int
    ) -> list[VectorHit]:  # pragma: no cover – interface
        """Return top-k most similar hits."""

    def close(self) -> None:  # Optional override
        """Free resources / flush buffers."""
        return

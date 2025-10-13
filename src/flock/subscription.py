"""Agent subscription declarations and helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from flock.registry import type_registry


if TYPE_CHECKING:
    from flock.artifacts import Artifact


Predicate = Callable[[BaseModel], bool]


@dataclass
class TextPredicate:
    text: str
    min_p: float = 0.0


@dataclass
class JoinSpec:
    """
    Specification for correlated AND gates.

    Correlates artifacts by a common key within a time OR count window.

    Examples:
        # Time-based correlation (within 5 minutes)
        JoinSpec(
            by=lambda x: x.correlation_id,
            within=timedelta(minutes=5)
        )

        # Count-based correlation (within next 10 artifacts)
        JoinSpec(
            by=lambda x: x.correlation_id,
            within=10
        )

    Args:
        by: Callable that extracts the correlation key from an artifact payload
        within: Window for correlation
            - timedelta: Time window (artifacts must arrive within this time)
            - int: Count window (artifacts must arrive within N published artifacts)
    """

    by: Callable[[BaseModel], Any]  # Extract correlation key from payload
    within: timedelta | int  # Time window OR count window for correlation


@dataclass
class BatchSpec:
    """
    Specification for batch processing.

    Accumulates artifacts and triggers agent when:
    - Size threshold reached (e.g., batch of 10)
    - Timeout expires (e.g., flush every 30 seconds)
    - Whichever comes first

    Examples:
        # Size-based batching (flush when 25 artifacts accumulated)
        BatchSpec(size=25)

        # Timeout-based batching (flush every 30 seconds)
        BatchSpec(timeout=timedelta(seconds=30))

        # Hybrid (whichever comes first)
        BatchSpec(size=100, timeout=timedelta(minutes=5))

    Args:
        size: Optional batch size threshold (flush when this many artifacts accumulated)
        timeout: Optional timeout threshold (flush when this much time elapsed since first artifact)

    Note: At least one of size or timeout must be specified.
    """

    size: int | None = None
    timeout: timedelta | None = None

    def __post_init__(self):
        if self.size is None and self.timeout is None:
            raise ValueError("BatchSpec requires at least one of: size, timeout")


class Subscription:
    """Defines how an agent consumes artifacts from the blackboard."""

    def __init__(
        self,
        *,
        agent_name: str,
        types: Sequence[type[BaseModel]],
        where: Sequence[Predicate] | None = None,
        text_predicates: Sequence[TextPredicate] | None = None,
        from_agents: Iterable[str] | None = None,
        channels: Iterable[str] | None = None,
        join: JoinSpec | None = None,
        batch: BatchSpec | None = None,
        delivery: str = "exclusive",
        mode: str = "both",
        priority: int = 0,
    ) -> None:
        if not types:
            raise ValueError("Subscription must declare at least one type.")
        self.agent_name = agent_name
        self.type_models: list[type[BaseModel]] = list(types)

        # Register all types and build counts (supports duplicates for count-based AND gates)
        type_name_list = [type_registry.register(t) for t in types]
        self.type_names: set[str] = set(type_name_list)  # Unique type names (for matching)

        # Count-based AND gate: Track how many of each type are required
        # Example: .consumes(A, A, B) → {"TypeA": 2, "TypeB": 1}
        self.type_counts: dict[str, int] = {}
        for type_name in type_name_list:
            self.type_counts[type_name] = self.type_counts.get(type_name, 0) + 1

        self.where = list(where or [])
        self.text_predicates = list(text_predicates or [])
        self.from_agents = set(from_agents or [])
        self.channels = set(channels or [])
        self.join = join
        self.batch = batch
        self.delivery = delivery
        self.mode = mode
        self.priority = priority

    def accepts_direct(self) -> bool:
        return self.mode in {"direct", "both"}

    def accepts_events(self) -> bool:
        return self.mode in {"events", "both"}

    def matches(self, artifact: Artifact) -> bool:
        if artifact.type not in self.type_names:
            return False
        if self.from_agents and artifact.produced_by not in self.from_agents:
            return False
        if self.channels and not artifact.tags.intersection(self.channels):
            return False

        # Evaluate where predicates on typed payloads
        model_cls = type_registry.resolve(artifact.type)
        payload = model_cls(**artifact.payload)
        for predicate in self.where:
            try:
                if not predicate(payload):
                    return False
            except Exception:
                return False
        return True

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"Subscription(agent={self.agent_name!r}, types={list(self.type_names)!r}, "
            f"delivery={self.delivery!r}, mode={self.mode!r})"
        )


__all__ = [
    "BatchSpec",
    "JoinSpec",
    "Subscription",
    "TextPredicate",
]

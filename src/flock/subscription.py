"""Agent subscription declarations and helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
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
    kind: str
    window: float
    by: Callable[[Artifact], Any] | None = None


@dataclass
class BatchSpec:
    size: int
    within: float
    by: Callable[[Artifact], Any] | None = None


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
        self.type_names: set[str] = {type_registry.register(t) for t in types}
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

"""Program interface and registry (skeleton)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Callable, Dict


class Program(ABC):
    """Abstract program interface for prediction/planning algorithms."""

    @abstractmethod
    async def run(self, *, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute program and return structured outputs."""
        raise NotImplementedError

    async def run_stream(self, *, inputs: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        """Optional streaming variant that yields typed events and/or a final result."""
        raise NotImplementedError


class ProgramRegistry:
    _REGISTRY: Dict[str, Callable[..., Program]] = {}

    @classmethod
    def register(cls, name: str, factory: Callable[..., Program]) -> None:
        cls._REGISTRY[name] = factory

    @classmethod
    def get(cls, name: str) -> Callable[..., Program]:
        if name not in cls._REGISTRY:
            available = ", ".join(sorted(cls._REGISTRY.keys())) or "<none>"
            raise KeyError(f"Unknown program '{name}'. Available: {available}")
        return cls._REGISTRY[name]


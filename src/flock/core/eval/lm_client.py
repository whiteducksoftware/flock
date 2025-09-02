"""LMClient skeleton — provider-agnostic, LiteLLM-backed interface.

This module defines a thin surface over LiteLLM to keep the rest of the
evaluator code independent of provider quirks. It intentionally avoids any
side-effects or global state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Literal


ModelMode = Literal["chat", "text", "responses"]


@dataclass
class LMRequest:
    model: str
    messages: list[dict[str, Any]]
    temperature: float | None = None
    max_tokens: int | None = None
    timeout: float | None = None
    extra: dict[str, Any] | None = None


@dataclass
class LMUsage:
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost: float | None = None


class LMClient:
    """Skeleton LM client.

    In a later implementation, this will call LiteLLM and normalize responses
    and streaming chunks. For now it only defines the interface and docstrings.
    """

    def __init__(self, model: str, mode: ModelMode = "chat") -> None:
        self.model = model
        self.mode = mode

    async def generate(self, request: LMRequest) -> tuple[dict[str, Any], LMUsage]:
        """Perform a single generation request.

        Returns a (result_dict, usage) tuple. The result_dict is expected to
        include the raw text and, where applicable, a parsed JSON payload.
        """
        raise NotImplementedError

    async def stream(self, request: LMRequest) -> AsyncIterator[dict[str, Any]]:
        """Yield a normalized stream of chunks.

        Each yielded item should be a dict with typed keys (e.g., {"token": str}
        or {"field": "summary", "delta": "..."}). A final item can include a
        completion marker and usage summary.
        """
        raise NotImplementedError


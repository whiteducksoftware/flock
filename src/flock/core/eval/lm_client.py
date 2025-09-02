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
        # Delayed import so tests can stub without importing network libs
        import litellm  # type: ignore

        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": request.messages,
        }
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.max_tokens is not None:
            # new OpenAI param is sometimes max_completion_tokens; litellm maps both
            kwargs["max_tokens"] = request.max_tokens
        if request.extra:
            kwargs.update(request.extra)

        resp = await litellm.acompletion(**kwargs)  # type: ignore
        # Extract text
        text = None
        try:
            choice = resp.choices[0]
            if hasattr(choice, "message"):
                text = choice.message.get("content")
            elif hasattr(choice, "text"):
                text = choice.text
        except Exception:
            text = None

        # Usage
        usage = LMUsage(
            model=request.model,
            input_tokens=getattr(resp, "usage", {}).get("prompt_tokens") if hasattr(resp, "usage") else None,  # type: ignore
            output_tokens=getattr(resp, "usage", {}).get("completion_tokens") if hasattr(resp, "usage") else None,  # type: ignore
            cost=None,
        )
        return {"text": text, "raw": resp}, usage

    async def stream(self, request: LMRequest) -> AsyncIterator[dict[str, Any]]:
        """Yield a normalized stream of chunks.

        Each yielded item should be a dict with typed keys (e.g., {"token": str}
        or {"field": "summary", "delta": "..."}). A final item can include a
        completion marker and usage summary.
        """
        import litellm  # type: ignore

        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": request.messages,
            "stream": True,
        }
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens
        if request.extra:
            kwargs.update(request.extra)

        async for chunk in await litellm.acompletion(**kwargs):  # type: ignore
            # Normalize to token delta when available
            try:
                delta = chunk.choices[0].get("delta", {})
                content = delta.get("content")
                if content:
                    yield {"token": content}
            except Exception:
                yield {"chunk": chunk}

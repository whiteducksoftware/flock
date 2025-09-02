"""StreamAdapter — normalize streaming events across providers and programs.

This module provides a small utility to wrap provider-level token streams
into a consistent sequence of typed events that programs can yield to
consumers. The intent is to keep event shapes stable across models.
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from .lm_client import LMClient, LMRequest


async def stream_text(client: LMClient, request: LMRequest) -> AsyncIterator[dict[str, Any]]:
    """Yield a normalized stream of token events from the LM client.

    Yields dicts like:
    - {"event": "start"}
    - {"event": "token", "text": "..."}
    - {"event": "end"}
    """
    yield {"event": "start"}
    async for chunk in client.stream(request):
        token = chunk.get("token") or chunk.get("text")
        if token:
            yield {"event": "token", "text": token}
    yield {"event": "end"}


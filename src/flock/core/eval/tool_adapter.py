"""ToolAdapter skeleton — unify native and MCP tool invocation.

Programs should call tools via this adapter to avoid third-party wrappers.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable


ToolFn = Callable[..., Any]
AToolFn = Callable[..., Awaitable[Any]]


class ToolAdapter:
    """Uniform interface for invoking native and MCP tools (sync/async)."""

    def __init__(self) -> None:
        pass

    async def call(self, tool: ToolFn | AToolFn, **kwargs) -> Any:
        """Invoke a tool; supports sync or async callables.

        Implement timeouts, structured error handling, and result normalization
        in the concrete implementation.
        """
        raise NotImplementedError


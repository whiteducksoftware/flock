"""ToolAdapter skeleton — unify native and MCP tool invocation.

Programs should call tools via this adapter to avoid third-party wrappers.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable
import asyncio


ToolFn = Callable[..., Any]
AToolFn = Callable[..., Awaitable[Any]]


class ToolAdapter:
    """Uniform interface for invoking native and MCP tools (sync/async)."""

    def __init__(self) -> None:
        pass

    async def call(self, tool: ToolFn | AToolFn, timeout: float | None = None, **kwargs) -> Any:
        """Invoke a tool; supports sync or async callables.

        Implement timeouts, structured error handling, and result normalization
        in the concrete implementation.
        """
        try:
            if asyncio.iscoroutinefunction(tool):  # type: ignore[arg-type]
                coro = tool(**kwargs)  # type: ignore[misc]
            else:
                # run sync function in default loop executor
                loop = asyncio.get_running_loop()
                coro = loop.run_in_executor(None, lambda: tool(**kwargs))  # type: ignore[misc]

            if timeout is not None and timeout > 0:
                return await asyncio.wait_for(coro, timeout=timeout)
            return await coro
        except Exception as e:
            # Normalize tool errors
            return {
                "error": str(e),
                "type": e.__class__.__name__,
            }

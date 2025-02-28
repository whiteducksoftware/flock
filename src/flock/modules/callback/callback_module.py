"""Callback module for handling agent lifecycle hooks."""

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import Field

from flock.core import FlockModule, FlockModuleConfig
from flock.core.context.context import FlockContext


class CallbackModuleConfig(FlockModuleConfig):
    """Configuration for callback module."""

    initialize_callback: (
        Callable[[Any, dict[str, Any]], Awaitable[None]] | None
    ) = Field(
        default=None,
        description="Optional callback function for initialization",
    )
    evaluate_callback: (
        Callable[[Any, dict[str, Any]], Awaitable[dict[str, Any]]] | None
    ) = Field(
        default=None, description="Optional callback function for evaluate"
    )
    terminate_callback: (
        Callable[[Any, dict[str, Any], dict[str, Any]], Awaitable[None]] | None
    ) = Field(
        default=None, description="Optional callback function for termination"
    )
    on_error_callback: (
        Callable[[Any, Exception, dict[str, Any]], Awaitable[None]] | None
    ) = Field(
        default=None,
        description="Optional callback function for error handling",
    )


class CallbackModule(FlockModule):
    """Module that provides callback functionality for agent lifecycle events."""

    name: str = "callbacks"
    config: CallbackModuleConfig = Field(
        default_factory=CallbackModuleConfig,
        description="Callback module configuration",
    )

    async def pre_initialize(
        self,
        agent: Any,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
    ) -> None:
        """Run initialize callback if configured."""
        if self.config.initialize_callback:
            await self.config.initialize_callback(agent, inputs)

    async def pre_evaluate(
        self,
        agent: Any,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
    ) -> dict[str, Any]:
        """Run evaluate callback if configured."""
        if self.config.evaluate_callback:
            return await self.config.evaluate_callback(agent, inputs)
        return inputs

    async def pre_terminate(
        self,
        agent: Any,
        inputs: dict[str, Any],
        result: dict[str, Any],
        context: FlockContext | None = None,
    ) -> None:
        """Run terminate callback if configured."""
        if self.config.terminate_callback:
            await self.config.terminate_callback(agent, inputs, result)

    async def on_error(
        self,
        agent: Any,
        error: Exception,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
    ) -> None:
        """Run error callback if configured."""
        if self.config.on_error_callback:
            await self.config.on_error_callback(agent, error, inputs)

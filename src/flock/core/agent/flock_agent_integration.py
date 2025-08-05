# src/flock/core/agent/flock_agent_integration.py
"""Tool and server integration functionality for FlockAgent."""

from collections.abc import Callable
from functools import wraps
from inspect import Parameter, signature
from typing import TYPE_CHECKING, Any, TypeVar, cast

from flock.core.context.context import FlockContext
from flock.core.logging.logging import get_logger
from flock.core.mcp.flock_mcp_server import FlockMCPServer

if TYPE_CHECKING:
    from flock.core.flock_agent import FlockAgent

logger = get_logger("agent.integration")

R = TypeVar("R", bound=str)


def adapt(prop_name: str, fn: Callable[..., R]) -> Callable[[FlockContext], R]:
    """Coerce *fn* into the canonical ``(ctx: FlockContext) -> str`` form.

    Acceptable signatures
    ---------------------
    1. ``() -> str``                           (no parameters)
    2. ``(ctx: FlockContext) -> str``          (exactly one positional parameter)

    Anything else raises ``TypeError``.

    The wrapper also enforces at runtime that the result is ``str``.
    """
    if not callable(fn):
        raise TypeError(f"{prop_name} must be a callable, got {type(fn).__name__}")

    sig = signature(fn)
    params = list(sig.parameters.values())

    def _validate_result(res: object) -> R:
        if not isinstance(res, str):
            raise TypeError(
                f"{prop_name} callable must return str, got {type(res).__name__}"
            )
        return cast(R, res)

    # ── Case 1: () -> str ────────────────────────────────────────────────────
    if len(params) == 0:

        @wraps(fn)
        def _wrapped(ctx: FlockContext) -> R:
            return _validate_result(fn())

        return _wrapped

    # ── Case 2: (ctx) -> str ────────────────────────────────────────────────
    if len(params) == 1:
        p: Parameter = params[0]
        valid_kind = p.kind in (
            Parameter.POSITIONAL_ONLY,
            Parameter.POSITIONAL_OR_KEYWORD,
        )
        valid_annotation = p.annotation in (Parameter.empty, FlockContext)
        has_no_default = p.default is Parameter.empty

        if valid_kind and valid_annotation and has_no_default:

            @wraps(fn)
            def _wrapped(ctx: FlockContext) -> R:
                return _validate_result(fn(ctx))  # type: ignore[arg-type]

            return _wrapped

    # ── Anything else: reject ───────────────────────────────────────────────
    raise TypeError(
        f"{prop_name} callable must be () -> str or (ctx: FlockContext) -> str; "
        f"got signature {sig}"
    )

class FlockAgentIntegration:
    """Handles tool and server integration for FlockAgent including MCP servers and callable tools."""

    def __init__(self, agent: "FlockAgent"):
        self.agent = agent

    def _resolve(self, raw: str | Callable[..., str], name: str, ctx: FlockContext | None) -> str | None:
        if callable(raw):
            raw = adapt(name, raw)(ctx or FlockContext())
        return raw

    def resolve_description(self, context: FlockContext | None = None) -> str | None:
        """Resolve the agent's description, handling callable descriptions."""
        return self._resolve(self.agent.description_spec, "description", context)

    def resolve_input(self, context: FlockContext | None = None) -> str | None:
        """Resolve the agent's input, handling callable inputs."""
        return self._resolve(self.agent.input_spec, "input", context)

    def resolve_output(self, context: FlockContext | None = None) -> str | None:
        """Resolve the agent's output, handling callable outputs."""
        return self._resolve(self.agent.output_spec, "output", context)

    def resolve_next_agent(self, context: FlockContext | None = None) -> str | None:
        """Resolve the next agent, handling callable next agents."""
        return self._resolve(self.agent.next_agent_spec, "next_agent", context)

    async def get_mcp_tools(self) -> list[Any]:
        """Get tools from registered MCP servers."""
        mcp_tools = []
        if self.agent.servers:
            from flock.core.registry import get_registry

            registry = get_registry()  # Get the registry
            for server in self.agent.servers:
                registered_server: FlockMCPServer | None = None
                server_tools = []
                if isinstance(server, FlockMCPServer):
                    # check if registered
                    server_name = server.config.name
                    registered_server = registry.get_server(
                        server_name
                    )
                else:
                    # servers must be registered.
                    registered_server = registry.get_server(
                        name=server
                    )
                if registered_server:
                    server_tools = await registered_server.get_tools(
                        agent_id=self.agent.agent_id,
                        run_id=self.agent.context.run_id,
                    )
                else:
                    logger.warning(
                        f"No Server with name '{server.config.name if isinstance(server, FlockMCPServer) else server}' registered! Skipping."
                    )
                mcp_tools = mcp_tools + server_tools
        return mcp_tools

    async def execute_with_middleware(
        self,
        current_inputs: dict[str, Any],
        registered_tools: list[Any],
        mcp_tools: list[Any]
    ) -> dict[str, Any]:
        """Execute evaluator with optional DI middleware pipeline."""
        container = None
        if self.agent.context is not None:
            container = self.agent.context.get_variable("di.container")

        # If a MiddlewarePipeline is registered in DI, wrap the evaluator
        result: dict[str, Any] | None = None

        if container is not None:
            try:
                from wd.di.middleware import (
                    MiddlewarePipeline,
                )

                pipeline: MiddlewarePipeline | None = None
                try:
                    pipeline = container.get_service(MiddlewarePipeline)
                except Exception:
                    pipeline = None

                if pipeline is not None:
                    # Build execution chain where the evaluator is the terminal handler

                    async def _final_handler():
                        return await self.agent.evaluator.evaluate_core(
                            self.agent, current_inputs, self.agent.context, registered_tools, mcp_tools
                        )

                    idx = 0

                    async def _invoke_next():
                        nonlocal idx

                        if idx < len(pipeline._middleware):
                            mw = pipeline._middleware[idx]
                            idx += 1
                            return await mw(self.agent.context, _invoke_next)  # type: ignore[arg-type]
                        return await _final_handler()

                    # Execute pipeline
                    result = await _invoke_next()
                else:
                    # No pipeline registered, direct evaluation
                    result = await self.agent.evaluator.evaluate_core(
                        self.agent, current_inputs, self.agent.context, registered_tools, mcp_tools
                    )
            except ImportError:
                # wd.di not installed – fall back
                result = await self.agent.evaluator.evaluate_core(
                    self.agent, current_inputs, self.agent.context, registered_tools, mcp_tools
                )
        else:
            # No DI container – standard execution
            result = await self.agent.evaluator.evaluate_core(
                self.agent,
                current_inputs,
                self.agent.context,
                registered_tools,
                mcp_tools,
            )

        return result

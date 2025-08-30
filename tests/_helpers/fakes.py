from typing import Any

from flock.core.component.evaluation_component import EvaluationComponent
from flock.core.component.routing_component import RoutingComponent
from flock.core.component.agent_component_base import AgentComponent
from flock.core.context.context import FlockContext


class FakeEvaluator(EvaluationComponent):
    name: str

    def set_model(self, model: str, temperature: float = 0.0, max_tokens: int = 4096) -> None:
        # For tests we just store it on the config if present
        try:
            self.config.model = model
        except Exception:
            pass

    async def evaluate_core(
        self,
        agent: Any,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
        tools: list[Any] | None = None,
        mcp_tools: list[Any] | None = None,
    ) -> dict[str, Any]:
        # Deterministic echo with agent name tag for routing tests
        msg = inputs.get("message")
        if msg is None:
            # Try common fallbacks used by the orchestrator
            msg = inputs.get("flock.message") or inputs.get("init_input") or inputs
        return {"result": f"{msg}:{agent.name}" if hasattr(agent, "name") else msg}


class FakeRouter(RoutingComponent):
    name: str

    async def determine_next_step(
        self,
        agent: Any,
        result: dict[str, Any],
        context: FlockContext | None = None,
    ) -> str | Any | None:
        # Follow explicit next_agent in context (flock namespace), else stop
        next_name = None
        if context is not None:
            next_name = context.get_variable("flock.next_agent") or context.get_variable("next_agent")
        if not next_name and isinstance(result, dict):
            next_name = result.get("next_agent")
        return next_name


class HookRecorder(AgentComponent):
    name: str

    async def on_initialize(self, agent: Any, inputs: dict[str, Any], context: FlockContext | None = None) -> None:
        if context is not None:
            order = context.get_variable("order", [])
            order.append("on_initialize")
            context.set_variable("order", order)

    async def on_pre_evaluate(self, agent: Any, inputs: dict[str, Any], context: FlockContext | None = None) -> dict[str, Any]:
        if context is not None:
            order = context.get_variable("order", [])
            order.append("on_pre_evaluate")
            context.set_variable("order", order)
        return inputs

    async def on_post_evaluate(self, agent: Any, inputs: dict[str, Any], context: FlockContext | None = None, result: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if context is not None:
            order = context.get_variable("order", [])
            order.append("on_post_evaluate")
            context.set_variable("order", order)
        return result

    async def terminate(self, agent: Any, inputs: dict[str, Any], result: dict[str, Any], context: FlockContext | None = None) -> None:
        if context is not None:
            order = context.get_variable("order", [])
            order.append("terminate")
            context.set_variable("order", order)

    async def on_terminate(self, agent: Any, inputs: dict[str, Any], context: FlockContext | None = None, result: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if context is not None:
            order = context.get_variable("order", [])
            order.append("terminate")
            context.set_variable("order", order)
        return result

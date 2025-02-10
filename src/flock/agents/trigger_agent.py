from collections.abc import Callable
from typing import Any

from pydantic import Field

from flock.core.context.context import FlockContext
from flock.core.flock_agent import FlockAgent


class TriggerAgent(FlockAgent):
    """An agent that executes based on specific triggers/conditions.

    Attributes:
        input: Input domain for the agent
        output: Output types for the agent
        tools: Tools the agent is allowed to use
        trigger_condition: Callable that evaluates whether the agent should execute
        trigger_check_interval: How often to check the trigger condition (in seconds)
        max_wait_time: Maximum time to wait for trigger (in seconds)
    """

    input: str = Field(default="", description="Input domain for the agent")
    output: str = Field(default="", description="Output types for the agent")
    tools: list[Callable] | None = Field(default=None, description="Tools the agent is allowed to use")
    trigger_condition: Callable[[dict[str, Any]], bool] = Field(
        ..., description="Function that evaluates trigger conditions"
    )
    trigger_check_interval: float = Field(default=1.0, description="Interval between trigger checks (seconds)")
    max_wait_time: float = Field(default=60.0, description="Maximum time to wait for trigger (seconds)")

    async def _evaluate_trigger(self, context: FlockContext) -> bool:
        """Evaluate the trigger condition."""
        try:
            return self.trigger_condition(context.state)
        except Exception:
            raise

    async def _execute_action(self, context: FlockContext) -> dict[str, Any]:
        """Execute the agent's action once triggered."""
        try:
            # Here you would implement the actual action logic
            # For now, we'll just return a simple result
            result = {"status": "completed", "trigger_time": context.state.get("current_time")}
            return result
        except Exception:
            raise

    async def run(self, context: FlockContext) -> dict[str, Any]:
        """Run the agent, waiting for and responding to triggers."""
        import asyncio
        import time

        try:
            start_time = time.time()
            triggered = False

            while (time.time() - start_time) < self.max_wait_time:
                if await self._evaluate_trigger(context):
                    triggered = True
                    break

                await asyncio.sleep(self.trigger_check_interval)

            if not triggered:
                return {"error": "Trigger timeout", "max_wait_time": self.max_wait_time}

            # Execute action when triggered
            result = await self._execute_action(context)
            return result

        except Exception:
            raise

    async def run_temporal(self, context: FlockContext) -> dict[str, Any]:
        """Run the trigger agent via Temporal."""
        try:
            from temporalio.client import Client

            from flock.workflow.agent_activities import run_agent_activity
            from flock.workflow.temporal_setup import run_activity

            client = await Client.connect("localhost:7233", namespace="default")

            # First activity: Monitor trigger
            context_data = {
                "state": context.state,
                "history": [record.__dict__ for record in context.history],
                "agent_definitions": [definition.__dict__ for definition in context.agent_definitions],
            }
            agent_data = self.dict()

            monitor_result = await run_activity(
                client,
                f"{self.name}_monitor",
                run_agent_activity,
                {"agent_data": agent_data, "context_data": context_data},
            )

            if monitor_result.get("error"):
                return monitor_result

            # Second activity: Execute action
            action_result = await run_activity(
                client,
                f"{self.name}_action",
                run_agent_activity,
                {"agent_data": agent_data, "context_data": context_data},
            )

            return action_result

        except Exception:
            raise

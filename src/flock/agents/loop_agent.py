from collections.abc import Callable
from typing import Any

from pydantic import Field

from flock.core.context.context import FlockContext
from flock.core.flock_agent import FlockAgent


class LoopAgent(FlockAgent):
    """An agent that executes its logic in a loop until a termination condition is met.

    Attributes:
        input: Input domain for the agent
        output: Output types for the agent
        tools: Tools the agent is allowed to use
        max_iterations: Maximum number of iterations before forced termination
        termination_condition: Optional callable that determines when to stop the loop
    """

    input: str = Field(default="", description="Input domain for the agent")
    output: str = Field(default="", description="Output types for the agent")
    tools: list[Callable] | None = Field(default=None, description="Tools the agent is allowed to use")
    max_iterations: int = Field(default=10, description="Maximum number of iterations")
    termination_condition: Callable[[dict[str, Any]], bool] | None = Field(
        default=None, description="Optional function to determine loop termination"
    )

    async def _process_iteration(self, context: FlockContext, iteration: int) -> dict[str, Any]:
        """Process a single iteration of the loop."""
        try:
            # Here you would implement the actual iteration logic
            # For now, we'll just return a simple result
            return {"iteration": iteration, "status": "completed"}
        except Exception:
            raise

    def _should_continue(self, result: dict[str, Any], iteration: int) -> bool:
        """Determine if the loop should continue."""
        if iteration >= self.max_iterations:
            return False

        if self.termination_condition:
            should_terminate = self.termination_condition(result)
            return not should_terminate

        return True

    async def run(self, context: FlockContext) -> dict[str, Any]:
        """Run the agent in a loop until the termination condition is met or max iterations reached."""
        try:
            results = []
            iteration = 0

            while True:
                result = await self._process_iteration(context, iteration)
                results.append(result)

                # Check termination conditions
                if not self._should_continue(result, iteration):
                    break

                iteration += 1

            return {
                "iterations": iteration + 1,
                "results": results,
                "final_result": results[-1] if results else None,
            }

        except Exception:
            raise

    async def run_temporal(self, context: FlockContext) -> dict[str, Any]:
        """Run the loop agent via Temporal."""
        try:
            from temporalio.client import Client

            from flock.workflow.agent_activities import run_agent_activity
            from flock.workflow.temporal_setup import run_activity

            client = await Client.connect("localhost:7233", namespace="default")

            results = []
            iteration = 0

            while True:
                # Process iteration as a temporal activity
                context_data = {
                    "state": context.state,
                    "history": [record.__dict__ for record in context.history],
                    "agent_definitions": [definition.__dict__ for definition in context.agent_definitions],
                }
                agent_data = self.dict()

                result = await run_activity(
                    client,
                    f"{self.name}_iteration_{iteration}",
                    run_agent_activity,
                    {"agent_data": agent_data, "context_data": context_data},
                )
                results.append(result)

                # Check termination conditions
                if not self._should_continue(result, iteration):
                    break

                iteration += 1

            return {
                "iterations": iteration + 1,
                "results": results,
                "final_result": results[-1] if results else None,
            }

        except Exception:
            raise

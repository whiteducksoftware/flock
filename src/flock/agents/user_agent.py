from collections.abc import Callable
from typing import Any

from pydantic import Field
from temporalio import activity

from flock.core.context.context import FlockContext
from flock.core.flock_agent import FlockAgent


@activity.defn
async def run_user_agent_activity(context: dict[str, Any]) -> dict[str, Any]:
    """Temporal activity to process a user agent task.

    Expects context to contain:
      - "model": the model name
      - "agent_input": the key used for the input
      - "output": the agent output specification
      - "init_input": the initial input
      - "tools": (optional) list of tools
    """
    try:
        import dspy

        model = context.get("model")
        agent_input = context.get("agent_input")
        output = context.get("output")
        init_input = context.get("init_input")
        tools = context.get("tools")

        lm = dspy.LM(model)
        dspy.configure(lm=lm)

        if tools:
            agent_task = dspy.ReAct(f"{agent_input} -> {output}", tools=tools)
        else:
            agent_task = dspy.Predict(f"{agent_input} -> {output}")

        kwargs = {agent_input: init_input}
        result = agent_task(**kwargs).toDict()
        result[agent_input] = init_input

        return result

    except Exception:
        raise


class UserAgent(FlockAgent):
    """An agent that evaluates declarative inputs with user interaction capabilities.

    This agent extends the base Agent class with the ability to interact with users
    during execution, while maintaining compatibility with both local and Temporal
    execution modes.

    Attributes:
        input: Input domain for the agent
        output: Output types for the agent
        tools: Tools the agent is allowed to use
        require_confirmation: Whether to require user confirmation before proceeding
    """

    input: str = Field(default="", description="Input domain for the agent")
    output: str = Field(default="", description="Output types for the agent")
    tools: list[Callable] | None = Field(default=None, description="Tools the agent is allowed to use")
    require_confirmation: bool = Field(default=False, description="Whether to require user confirmation")

    async def _configure_model(self) -> tuple[Any, Any]:
        """Configure the model and create the appropriate task."""
        try:
            import dspy

            lm = dspy.LM(self.model)
            dspy.configure(lm=lm)

            if self.tools:
                agent_task = dspy.ReAct(f"{self.input} -> {self.output}", tools=self.tools)
            else:
                agent_task = dspy.Predict(f"{self.input} -> {self.output}")

            return lm, agent_task

        except Exception:
            raise

    async def _execute_task(self, task: Any, context: FlockContext) -> dict[str, Any]:
        """Execute the configured task."""
        try:
            kwargs = {self.input: context.get_variable("init_input")}
            result = task(**kwargs).toDict()
            result[self.input] = kwargs[self.input]
            return result

        except Exception:
            raise

    async def run(self, context: FlockContext) -> dict[str, Any]:
        """Run the agent on a task with optional user interaction."""
        try:
            # Configure model and task
            _, task = await self._configure_model()

            # Execute with user confirmation if required
            if self.require_confirmation:
                # Here you would implement user confirmation logic
                # For now, we'll just proceed
                pass

            # Execute the task
            result = await self._execute_task(task, context)
            return result

        except Exception:
            raise

    async def run_temporal(self, context: FlockContext) -> dict[str, Any]:
        """Run the user agent via Temporal."""
        try:
            from temporalio.client import Client

            from flock.workflow.temporal_setup import run_activity

            client = await Client.connect("localhost:7233", namespace="default")

            # Prepare context for temporal activity
            activity_context = {
                "model": self.model,
                "agent_input": self.input,
                "output": self.output,
                "init_input": context.get_variable("init_input"),
                "tools": self.tools,
            }

            # Execute the activity
            result = await run_activity(
                client,
                self.name,
                run_user_agent_activity,
                activity_context,
            )

            return result

        except Exception:
            raise

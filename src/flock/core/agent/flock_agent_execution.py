# src/flock/core/agent/flock_agent_execution.py
"""Execution management functionality for FlockAgent."""

import asyncio
from typing import TYPE_CHECKING, Any

from opentelemetry import trace
from flock.core.logging.logging import get_logger

if TYPE_CHECKING:
    from flock.core.flock_agent import FlockAgent

logger = get_logger("agent.execution")
tracer = trace.get_tracer(__name__)


class FlockAgentExecution:
    """Handles execution management for FlockAgent including run, run_async, and run_temporal."""

    def __init__(self, agent: "FlockAgent"):
        self.agent = agent

    def run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Synchronous wrapper for run_async."""
        try:
            loop = asyncio.get_running_loop()
        except (
            RuntimeError
        ):  # 'RuntimeError: There is no current event loop...'
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.run_async(inputs))

    async def run_async(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Asynchronous execution logic with lifecycle hooks."""
        with tracer.start_as_current_span("agent.run") as span:
            span.set_attribute("agent.name", self.agent.name)
            span.set_attribute("inputs", str(inputs))
            try:
                # Initialize lifecycle system if not already present
                if not hasattr(self.agent, '_lifecycle'):
                    from flock.core.agent.flock_agent_lifecycle import FlockAgentLifecycle
                    self.agent._lifecycle = FlockAgentLifecycle(self.agent)
                    
                await self.agent._lifecycle.initialize(inputs)
                result = await self.agent._lifecycle.evaluate(inputs)
                await self.agent._lifecycle.terminate(inputs, result)
                span.set_attribute("result", str(result))
                logger.info("Agent run completed", agent=self.agent.name)
                return result
            except Exception as run_error:
                logger.error(
                    "Error running agent", agent=self.agent.name, error=str(run_error)
                )
                if "evaluate" not in str(
                    run_error
                ):  # Simple check, might need refinement
                    await self.agent._lifecycle.on_error(run_error, inputs)
                logger.error(
                    f"Agent '{self.agent.name}' run failed: {run_error}",
                    exc_info=True,
                )
                span.record_exception(run_error)
                raise  # Re-raise after handling

    async def run_temporal(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute agent using Temporal workflow orchestration."""
        with tracer.start_as_current_span("agent.run_temporal") as span:
            span.set_attribute("agent.name", self.agent.name)
            span.set_attribute("inputs", str(inputs))
            try:
                from temporalio.client import Client

                from flock.workflow.agent_activities import (
                    run_flock_agent_activity,
                )
                from flock.workflow.temporal_setup import run_activity

                client = await Client.connect(
                    "localhost:7233", namespace="default"
                )
                agent_data = self.agent._serialization.to_dict()
                inputs_data = inputs

                result = await run_activity(
                    client,
                    self.agent.name,
                    run_flock_agent_activity,
                    {"agent_data": agent_data, "inputs": inputs_data},
                )
                span.set_attribute("result", str(result))
                logger.info("Temporal run successful", agent=self.agent.name)
                return result
            except Exception as temporal_error:
                logger.error(
                    "Error in Temporal workflow",
                    agent=self.agent.name,
                    error=str(temporal_error),
                )
                span.record_exception(temporal_error)
                raise

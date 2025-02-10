import asyncio
import uuid
from typing import Any

from pydantic import Field

from flock.core.context.context import FlockContext
from flock.core.flock_agent import FlockAgent


class BatchAgent(FlockAgent):
    """A DeclarativeAgent that processes an iterable input in batches.

    Additional Attributes:
      iter_input: The key in the FlockContext that holds the iterable (a list).
      batch_site: The number of items per batch.

    For each batch, the agent's input dictionary is built from the FlockContext with the
    value for the iter_input key overridden by the current batch. The outputs across batches
    are then aggregated.
    """

    iter_input: str = Field(
        default="",
        description="Key of the iterable input (must be a list in the FlockContext)",
    )
    batch_size: int = Field(
        default=1, description="Batch size (number of items per batch)"
    )

    async def run(self, context: FlockContext) -> dict:
        """Run the BatchAgent locally by partitioning the iterable and aggregating the results."""
        try:
            iterable = context.get_variable(self.iter_input)
            if not isinstance(iterable, list):
                error_msg = (
                    f"Expected a list for key '{self.iter_input}' in context."
                )
                return {"error": error_msg}

            # Partition the iterable into batches
            batches: list[list[Any]] = [
                iterable[i : i + self.batch_size]
                for i in range(0, len(iterable), self.batch_size)
            ]

            # Process batches
            tasks = []
            for batch in batches:
                tasks.append(
                    self.evaluate(
                        context, input_overrides={self.iter_input: batch}
                    )
                )

            batch_results = await asyncio.gather(*tasks)

            # Aggregate the outputs
            output_keys = self._parse_keys(self.output)
            aggregated = {key: [] for key in output_keys}
            for res in batch_results:
                for key in output_keys:
                    aggregated[key].append(res.get(key))
            aggregated["batch_results"] = batch_results
            return aggregated

        except Exception:
            raise

    async def run_temporal(self, context: FlockContext) -> dict:
        """Run the BatchAgent via Temporal.

        For each batch, the agent's evaluation is performed as a separate Temporal activity.
        The results are then aggregated.
        """
        try:
            from temporalio.client import Client

            from flock.workflow.agent_activities import (
                run_declarative_agent_activity,
            )
            from flock.workflow.temporal_setup import run_activity

            # Connect to Temporal
            client = await Client.connect("localhost:7233", namespace="default")

            # Validate and prepare input
            iterable = context.get_variable(self.iter_input)
            if not isinstance(iterable, list):
                error_msg = (
                    f"Expected a list for key '{self.iter_input}' in context."
                )
                return {"error": error_msg}

            # Partition into batches
            batches: list[list[Any]] = [
                iterable[i : i + self.batch_size]
                for i in range(0, len(iterable), self.batch_size)
            ]

            # Process batches
            tasks = []
            for batch in batches:
                # Prepare context for this batch
                new_state = context.state.copy()
                new_state[self.iter_input] = batch
                context_data = {
                    "state": new_state,
                    "history": [],  # you might choose to pass along history if needed
                    "agent_definitions": [],
                }
                agent_data = self.dict()
                task_id = f"{self.name}_{uuid.uuid4().hex[:4]}"

                # Create temporal activity task
                tasks.append(
                    run_activity(
                        client,
                        task_id,
                        run_declarative_agent_activity,
                        {
                            "agent_data": agent_data,
                            "context_data": context_data,
                        },
                    )
                )

            batch_results = await asyncio.gather(*tasks)

            # Aggregate the outputs
            output_keys = self._parse_keys(self.output)
            aggregated = {key: [] for key in output_keys}
            for res in batch_results:
                for key in output_keys:
                    aggregated[key].append(res.get(key))
            aggregated["batch_results"] = batch_results
            return aggregated

        except Exception:
            raise

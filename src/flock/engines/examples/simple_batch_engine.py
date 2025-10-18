"""Reference batch-aware engine used in tutorials and tests."""

from __future__ import annotations

from pydantic import BaseModel, Field

from flock.components.agent import EngineComponent
from flock.registry import flock_type
from flock.utils.runtime import EvalInputs, EvalResult


@flock_type(name="BatchItem")
class BatchItem(BaseModel):
    """Input payload used by reference tests and tutorials."""

    value: int = Field(description="Numeric value contributed by the artifact")


@flock_type(name="BatchSummary")
class BatchSummary(BaseModel):
    """Output payload describing the batch that was processed."""

    batch_size: int = Field(description="Number of items included in this evaluation")
    values: list[int] = Field(
        description="Original values processed", default_factory=list
    )


class SimpleBatchEngine(EngineComponent):
    """Example engine that processes items individually or in batches.

    The engine auto-detects batch mode via ctx.is_batch flag and processes
    accordingly. It annotates each item with the current batch size so tests
    can verify that all artifacts were processed together.
    """

    async def evaluate(
        self, agent, ctx, inputs: EvalInputs, output_group
    ) -> EvalResult:
        """Process single item or batch with auto-detection.

        Auto-detects batch mode via ctx.is_batch flag (set by orchestrator when
        BatchSpec flushes accumulated artifacts).

        Args:
            agent: Agent instance
            ctx: Execution context (check ctx.is_batch for batch mode)
            inputs: EvalInputs with input artifacts
            output_group: OutputGroup defining what artifacts to produce

        Returns:
            EvalResult with BatchSummary artifact
        """
        # Auto-detect batch mode from context
        is_batch = bool(getattr(ctx, "is_batch", False))

        if is_batch:
            # Batch mode: Process all items together
            items = inputs.all_as(BatchItem)
            if not items:
                return EvalResult.empty()

            batch_size = len(items)
            summary = BatchSummary(
                batch_size=batch_size, values=[item.value for item in items]
            )

            state = dict(inputs.state)
            state["batch_size"] = summary.batch_size
            state["processed_values"] = list(summary.values)

            return EvalResult.from_object(summary, agent=agent, state=state)
        # Single mode: Process one item
        item = inputs.first_as(BatchItem)
        if item is None:
            return EvalResult.empty()

        annotated = BatchSummary(batch_size=1, values=[item.value])
        state = dict(inputs.state)
        state.setdefault("batch_size", annotated.batch_size)
        state.setdefault("processed_values", list(annotated.values))

        return EvalResult.from_object(annotated, agent=agent, state=state)

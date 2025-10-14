"""Reference batch-aware engine used in tutorials and tests."""

from __future__ import annotations

from pydantic import BaseModel, Field

from flock.components import EngineComponent
from flock.registry import flock_type
from flock.runtime import EvalInputs, EvalResult


@flock_type(name="BatchItem")
class BatchItem(BaseModel):
    """Input payload used by reference tests and tutorials."""

    value: int = Field(description="Numeric value contributed by the artifact")


@flock_type(name="BatchSummary")
class BatchSummary(BaseModel):
    """Output payload describing the batch that was processed."""

    batch_size: int = Field(description="Number of items included in this evaluation")
    values: list[int] = Field(description="Original values processed", default_factory=list)


class SimpleBatchEngine(EngineComponent):
    """Example engine that processes items individually or in batches.

    - ``evaluate`` is used when the agent is invoked directly without BatchSpec.
    - ``evaluate_batch`` is triggered when BatchSpec flushes accumulated artifacts.

    The engine simply annotates each item with the current batch size so tests can
    verify that all artifacts were processed together.
    """

    async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
        item = inputs.first_as(BatchItem)
        if item is None:
            return EvalResult.empty()

        annotated = BatchSummary(batch_size=1, values=[item.value])
        state = dict(inputs.state)
        state.setdefault("batch_size", annotated.batch_size)
        state.setdefault("processed_values", list(annotated.values))

        return EvalResult.from_object(annotated, agent=agent, state=state)

    async def evaluate_batch(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
        items = inputs.all_as(BatchItem)
        if not items:
            return EvalResult.empty()

        batch_size = len(items)
        summary = BatchSummary(batch_size=batch_size, values=[item.value for item in items])

        state = dict(inputs.state)
        state["batch_size"] = summary.batch_size
        state["processed_values"] = list(summary.values)

        return EvalResult.from_object(summary, agent=agent, state=state)

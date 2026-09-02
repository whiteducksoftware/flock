"""Test correlation safety for multi-type subscriptions."""

import pytest
from pydantic import BaseModel

from flock.components.agent import EngineComponent
from flock.core import Flock
from flock.registry import flock_type
from flock.utils.runtime import EvalResult


@flock_type(name="WfInputA")
class WfInputA(BaseModel):
    value: str


@flock_type(name="WfInputB")
class WfInputB(BaseModel):
    value: str


@pytest.mark.asyncio
async def test_multi_type_subscription_isolates_by_correlation_id():
    """Verify that multi-type subscriptions isolate waiting pools by correlation_id."""
    flock = Flock()
    received_batches = []

    class RecordEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            received_batches.append({
                "correlation_ids": [a.correlation_id for a in inputs.artifacts],
                "values": {a.payload["value"] for a in inputs.artifacts},
            })
            return EvalResult(artifacts=[])

    flock.agent("joiner").consumes(WfInputA, WfInputB).with_engines(RecordEngine())

    # Workflow 1 publishes InputA
    await flock.publish(WfInputA(value="A1"), correlation_id="wf-1")
    await flock.run_until_idle()
    assert len(received_batches) == 0, "Should wait for InputB in wf-1"

    # Workflow 2 publishes InputB
    await flock.publish(WfInputB(value="B2"), correlation_id="wf-2")
    await flock.run_until_idle()
    assert len(received_batches) == 0, (
        "Cross-pairing must not occur: wf-1 A1 and wf-2 B2 must not combine!"
    )

    # Now Workflow 1 publishes InputB
    await flock.publish(WfInputB(value="B1"), correlation_id="wf-1")
    await flock.run_until_idle()
    assert len(received_batches) == 1, "wf-1 should now be complete"
    assert received_batches[0]["correlation_ids"] == ["wf-1", "wf-1"]
    assert received_batches[0]["values"] == {"A1", "B1"}

    # Now Workflow 2 publishes InputA
    await flock.publish(WfInputA(value="A2"), correlation_id="wf-2")
    await flock.run_until_idle()
    assert len(received_batches) == 2, "wf-2 should now be complete"
    assert received_batches[1]["correlation_ids"] == ["wf-2", "wf-2"]
    assert received_batches[1]["values"] == {"A2", "B2"}

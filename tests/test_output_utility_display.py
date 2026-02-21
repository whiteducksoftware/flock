"""Tests for output utility display behavior (labels + input preview)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from flock.components.agent.output_utility import (
    OutputUtilityComponent,
    OutputUtilityConfig,
)
from flock.core.artifacts import Artifact
from flock.integrations.openclaw import GatewayConfig, OpenClawEngine
from flock.utils.runtime import Context, EvalInputs, EvalResult


@pytest.mark.asyncio
async def test_openclaw_label_uses_lobster_and_hides_global_model() -> None:
    """OpenClaw agents should show a lobster badge instead of orchestrator model."""
    component = OutputUtilityComponent(config=OutputUtilityConfig())
    component._formatter.display_result = MagicMock()

    openclaw_engine = OpenClawEngine(
        alias="codie",
        gateway=GatewayConfig(
            url="http://localhost:19789",
            token_env="OPENCLAW_CODIE_TOKEN",
        ),
    )
    agent = SimpleNamespace(name="codie", model=None, engines=[openclaw_engine])

    ctx = Context(task_id="task-1", state={"model": "azure/gpt-4.1"})
    inputs = EvalInputs(
        artifacts=[
            Artifact(
                type="tests.Input",
                payload={"pizza_idea": "Spicy Hawaiian"},
                produced_by="tester",
            )
        ]
    )
    result = EvalResult(
        artifacts=[
            Artifact(
                type="tests.Pizza",
                payload={"size": "12-inch"},
                produced_by="codie",
            )
        ]
    )

    await component.on_post_evaluate(agent, ctx, inputs, result)

    call = component._formatter.display_result.call_args
    assert call is not None
    _display_items, label = call.args
    assert label == "codie 🦞"


@pytest.mark.asyncio
async def test_openclaw_display_includes_input_object_preview() -> None:
    """OpenClaw table output should include the input object for parity."""
    component = OutputUtilityComponent(config=OutputUtilityConfig())
    component._formatter.display_result = MagicMock()

    openclaw_engine = OpenClawEngine(
        alias="codie",
        gateway=GatewayConfig(
            url="http://localhost:19789",
            token_env="OPENCLAW_CODIE_TOKEN",
        ),
    )
    agent = SimpleNamespace(name="codie", model=None, engines=[openclaw_engine])

    input_payload = {"pizza_idea": "Spicy Hawaiian"}
    ctx = Context(task_id="task-2", state={"model": "azure/gpt-4.1"})
    inputs = EvalInputs(
        artifacts=[
            Artifact(
                type="tests.Input",
                payload=input_payload,
                produced_by="tester",
            )
        ]
    )
    result = EvalResult(
        artifacts=[
            Artifact(
                type="tests.Pizza",
                payload={"size": "12-inch"},
                produced_by="codie",
            )
        ]
    )

    await component.on_post_evaluate(agent, ctx, inputs, result)

    call = component._formatter.display_result.call_args
    assert call is not None
    display_items, _label = call.args

    assert isinstance(display_items, list)
    assert isinstance(display_items[0], dict)
    assert list(display_items[0].keys())[0] == "input"
    assert display_items[0]["input"] == input_payload
    assert result.artifacts[0].payload == {"size": "12-inch"}


@pytest.mark.asyncio
async def test_native_agent_keeps_model_suffix() -> None:
    """Native agents should continue showing model suffix in the table title."""
    component = OutputUtilityComponent(config=OutputUtilityConfig())
    component._formatter.display_result = MagicMock()

    agent = SimpleNamespace(name="chef", model=None, engines=[object()])

    ctx = Context(task_id="task-3", state={"model": "azure/gpt-4.1"})
    inputs = EvalInputs(
        artifacts=[
            Artifact(
                type="tests.Input",
                payload={"idea": "Margherita"},
                produced_by="tester",
            )
        ]
    )
    result = EvalResult(
        artifacts=[
            Artifact(
                type="tests.Pizza",
                payload={"size": "large"},
                produced_by="chef",
            )
        ]
    )

    await component.on_post_evaluate(agent, ctx, inputs, result)

    call = component._formatter.display_result.call_args
    assert call is not None
    display_items, label = call.args

    assert label == "chef - azure/gpt-4.1"
    assert isinstance(display_items[0], Artifact)

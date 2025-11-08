import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import BaseModel, Field

from flock.core import Flock
from flock.core.artifacts import Artifact
from flock.engines.dspy_engine import DSPyEngine
from flock.registry import flock_type


@flock_type(name="IssueTask")
class IssueTask(BaseModel):
    title: str
    repository: str
    content: str


@flock_type(name="CreatedIssue")
class CreatedIssue(BaseModel):
    title: str
    repository: str
    content: str
    url: str


class TrackingTool:
    def __init__(self) -> None:
        self.sync_calls: int = 0
        self.async_calls: int = 0

    def __call__(self, **kwargs):  # pragma: no cover - should never be called
        self.sync_calls += 1
        raise RuntimeError("sync tool path invoked")

    async def acall(self, **kwargs):
        self.async_calls += 1
        task = kwargs.get("task", {})
        return {
            "title": task.get("title", ""),
            "repository": task.get("repository", ""),
            "content": task.get("content", ""),
            "url": f"https://example.com/issues/{self.async_calls}",
        }


class MockPrediction:
    def __init__(self, issue_payload: dict):
        self.output = {"issue": issue_payload}


class MockReAct:
    def __init__(self, signature, tools=None, max_iters=None):
        self.tools = tools or []

    def __call__(self, **kwargs):  # pragma: no cover - regression guard
        for tool in self.tools:
            tool(**kwargs.get("input", {}))
        return MockPrediction({})

    async def acall(self, **kwargs):
        issue_payload = {}
        for tool in self.tools:
            issue_payload = await tool.acall(**kwargs.get("input", {}))
        return MockPrediction(issue_payload)


class MockLM:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class MockDSPyModule(SimpleNamespace):
    def __init__(self):
        super().__init__(LM=MockLM, ReAct=MockReAct, Predict=MockReAct)

    def context(self, **kwargs):
        class _Ctx:
            def __enter__(self_inner):
                return self_inner

            def __exit__(self_inner, exc_type, exc_val, exc_tb):
                return False

        return _Ctx()


class StubSignatureBuilder:
    def prepare_signature_for_output_group(
        self, dspy_mod, *, agent, inputs, output_group, has_context, batched, engine_instructions
    ):
        return object()

    def prepare_execution_payload_for_output_group(
        self, inputs, output_group, *, batched, has_context, context_history, sys_desc
    ):
        task_payload = inputs.artifacts[-1].payload
        return {
            "description": sys_desc,
            "input": {"task": task_payload},
        }

    def extract_multi_output_payload(self, prediction, output_group):
        return prediction.output


class StubArtifactMaterializer:
    def materialize_artifacts(self, payload, outputs, produced_by, pre_generated_id=None):
        issue_payload = payload.get("issue", {})
        artifact = Artifact(
            id=pre_generated_id,
            type=outputs[0].spec.type_name,
            payload=issue_payload,
            produced_by=produced_by,
        )
        return [artifact], []


@pytest.mark.asyncio
async def test_async_mcp_tool_invocation_with_max_concurrency(monkeypatch):
    """Ensure async MCP tools run for every concurrent agent execution (no streaming)."""

    flock = Flock(model="test-model")
    engine = DSPyEngine(model="test-model", stream=False)
    engine._signature_builder = StubSignatureBuilder()
    engine._artifact_materializer = StubArtifactMaterializer()

    mock_dspy = MockDSPyModule()
    monkeypatch.setattr(engine, "_import_dspy", Mock(return_value=mock_dspy))

    tracking_tool = TrackingTool()

    agent_builder = (
        flock.agent("issue_creator")
        .description("Creates GitHub issues using MCP tools")
        .consumes(IssueTask)
        .publishes(CreatedIssue)
        .max_concurrency(5)
        .with_engines(engine)
    )

    monkeypatch.setattr(
        agent_builder.agent,
        "_get_mcp_tools",
        AsyncMock(return_value=[tracking_tool]),
    )

    tasks = [
        IssueTask(title=f"Task {idx}", repository="acme/repo", content="Fix bug")
        for idx in range(5)
    ]
    for task in tasks:
        await flock.publish(task)

    await flock.run_until_idle()

    assert tracking_tool.sync_calls == 0
    assert tracking_tool.async_calls == len(tasks)

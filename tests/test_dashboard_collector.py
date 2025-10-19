"""Unit tests for DashboardEventCollector component.

Tests verify event emission during agent lifecycle according to DATA_MODEL.md.
"""

import asyncio
import traceback
from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import BaseModel

from flock.core.artifacts import Artifact
from flock.core.store import InMemoryBlackboardStore
from flock.core.visibility import (
    LabelledVisibility,
    PrivateVisibility,
    PublicVisibility,
    TenantVisibility,
)
from flock.dashboard.collector import DashboardEventCollector
from flock.dashboard.events import (
    AgentActivatedEvent,
    AgentCompletedEvent,
    AgentErrorEvent,
    MessagePublishedEvent,
)
from flock.utils.runtime import Context


class TestInput(BaseModel):
    """Test input artifact type."""

    content: str


class TestOutput(BaseModel):
    """Test output artifact type."""

    result: str


@pytest.fixture
def collector():
    """Create fresh collector instance for each test."""
    return DashboardEventCollector(store=InMemoryBlackboardStore())


@pytest.fixture
def test_agent(orchestrator):
    """Create test agent with minimal configuration."""

    # Create agent builder
    builder = orchestrator.agent("test_agent")

    # Access the underlying agent object directly
    agent = builder._agent
    agent.labels.add("test")
    agent.labels.add("unit")
    agent.tenant_id = None
    agent.max_concurrency = 1

    return agent


@pytest.fixture
def test_context(orchestrator):
    """Create test context with correlation_id."""
    correlation_id = uuid4()
    return Context(
        board=orchestrator.store,
        orchestrator=orchestrator,
        task_id=f"task-{uuid4()}",
        state={},
        correlation_id=correlation_id,
    )


@pytest.fixture
def test_artifacts(test_context):
    """Create test input artifacts."""
    artifact = Artifact(
        id=uuid4(),
        type="TestInput",
        payload={"content": "test input"},
        produced_by="external",
        visibility=PublicVisibility(),
        correlation_id=test_context.correlation_id,
    )
    return [artifact]


@pytest.mark.asyncio
async def test_on_pre_consume_emits_agent_activated(
    collector, test_agent, test_context, test_artifacts
):
    """Test that on_pre_consume emits agent_activated event with correct data."""
    # Don't set subscriptions directly - just verify event is emitted
    # The subscriptions list is populated by orchestrator during agent building

    # Call on_pre_consume
    result = await collector.on_pre_consume(test_agent, test_context, test_artifacts)

    # Verify inputs passed through unchanged
    assert result == test_artifacts

    # Verify event was captured
    assert len(collector.events) == 1
    event = collector.events[0]

    # Verify event type
    assert isinstance(event, AgentActivatedEvent)

    # Verify required fields per DATA_MODEL.md lines 53-66
    assert event.agent_name == "test_agent"
    assert event.agent_id == "test_agent"
    assert event.consumed_types == ["TestInput"]
    assert len(event.consumed_artifacts) == 1
    assert str(test_artifacts[0].id) in event.consumed_artifacts

    # Verify subscription_info exists (may be empty if no subscriptions set)
    assert hasattr(event, "subscription_info")
    assert isinstance(event.subscription_info, dict) or hasattr(
        event.subscription_info, "from_agents"
    )

    # Verify metadata
    assert "test" in event.labels
    assert "unit" in event.labels
    assert event.tenant_id is None
    assert event.max_concurrency == 1

    # Verify correlation_id
    assert event.correlation_id == str(test_context.correlation_id)


@pytest.mark.asyncio
async def test_on_post_publish_emits_message_published(
    collector, test_agent, test_context
):
    """Test that on_post_publish emits message_published event with correct data."""
    # Create output artifact
    output_artifact = Artifact(
        id=uuid4(),
        type="TestOutput",
        payload={"result": "test output"},
        produced_by="test_agent",
        visibility=PublicVisibility(),
        correlation_id=test_context.correlation_id,
        tags=["generated", "test"],
        version=1,
    )

    # Call on_post_publish
    await collector.on_post_publish(test_agent, test_context, output_artifact)

    # Verify event was captured
    assert len(collector.events) == 1
    event = collector.events[0]

    # Verify event type
    assert isinstance(event, MessagePublishedEvent)

    # Verify required fields per DATA_MODEL.md lines 100-115
    assert event.artifact_id == str(output_artifact.id)
    assert event.artifact_type == "TestOutput"
    assert event.produced_by == "test_agent"
    assert event.payload == {"result": "test output"}

    # Verify visibility
    assert event.visibility.kind == "Public"

    # Verify tags
    assert "generated" in event.tags
    assert "test" in event.tags

    # Verify version
    assert event.version == 1

    # Verify correlation_id
    assert event.correlation_id == str(test_context.correlation_id)

    # Note: consumers field will be empty in Phase 1 (no subscription matching)
    assert event.consumers == []


@pytest.mark.asyncio
async def test_snapshot_agent_registry_tracks_metadata(
    collector, test_agent, test_context, test_artifacts
):
    test_agent.description = "Historical agent"
    await collector.on_pre_consume(test_agent, test_context, test_artifacts)
    registry = await collector.snapshot_agent_registry()
    assert "test_agent" in registry
    snapshot = registry["test_agent"]
    assert snapshot.name == "test_agent"
    assert snapshot.description == "Historical agent"
    assert snapshot.first_seen is not None
    assert snapshot.last_seen is not None
    await collector.clear_agent_registry()
    registry_after_clear = await collector.snapshot_agent_registry()
    assert "test_agent" not in registry_after_clear


@pytest.mark.asyncio
async def test_on_terminate_emits_agent_completed(collector, test_agent, test_context):
    """Test that on_terminate emits agent_completed event with correct metrics."""
    # First call on_pre_consume to set start time
    artifact = Artifact(
        id=uuid4(),
        type="TestInput",
        payload={"test": "data"},
        produced_by="external",
        visibility=PublicVisibility(),
        correlation_id=test_context.correlation_id,
    )
    await collector.on_pre_consume(test_agent, test_context, [artifact])

    # Set up run tracking state
    test_context.state["artifacts_produced"] = [str(uuid4()), str(uuid4())]
    test_context.state["metrics"] = {"tokens_used": 1234, "cost_usd": 0.05}

    # Simulate some execution time
    await asyncio.sleep(0.01)

    # Clear events from on_pre_consume
    collector.events.clear()

    # Call on_terminate
    await collector.on_terminate(test_agent, test_context)

    # Verify event was captured
    assert len(collector.events) == 1
    event = collector.events[0]

    # Verify event type
    assert isinstance(event, AgentCompletedEvent)

    # Verify required fields per DATA_MODEL.md lines 205-212
    assert event.agent_name == "test_agent"
    assert event.run_id == test_context.task_id
    assert event.duration_ms > 0
    assert len(event.artifacts_produced) == 2
    assert event.metrics["tokens_used"] == 1234
    assert event.metrics["cost_usd"] == 0.05

    # Verify final state snapshot
    assert "artifacts_produced" in event.final_state
    assert "metrics" in event.final_state

    # Verify correlation_id
    assert event.correlation_id == str(test_context.correlation_id)


@pytest.mark.asyncio
async def test_on_error_emits_agent_error(collector, test_agent, test_context):
    """Test that on_error emits agent_error event with traceback."""
    # Create test exception
    try:
        raise ValueError("Test validation error")
    except ValueError as e:
        error = e
        traceback.format_exc()

    # Call on_error
    await collector.on_error(test_agent, test_context, error)

    # Verify event was captured
    assert len(collector.events) == 1
    event = collector.events[0]

    # Verify event type
    assert isinstance(event, AgentErrorEvent)

    # Verify required fields per DATA_MODEL.md lines 247-253
    assert event.agent_name == "test_agent"
    assert event.run_id == test_context.task_id
    assert event.error_type == "ValueError"
    assert event.error_message == "Test validation error"
    assert "ValueError: Test validation error" in event.traceback
    assert event.failed_at is not None

    # Verify correlation_id
    assert event.correlation_id == str(test_context.correlation_id)


@pytest.mark.asyncio
async def test_correlation_id_propagation(
    collector, test_agent, test_artifacts, orchestrator
):
    """Test that correlation_id is correctly propagated from context to all events."""
    # Create context with specific correlation_id
    correlation_id = uuid4()
    ctx = Context(
        board=orchestrator.store,
        orchestrator=orchestrator,
        task_id=f"task-{uuid4()}",
        state={},
        correlation_id=correlation_id,
    )

    # Emit various events
    await collector.on_pre_consume(test_agent, ctx, test_artifacts)

    output = Artifact(
        id=uuid4(),
        type="TestOutput",
        payload={"result": "test"},
        produced_by="test_agent",
        visibility=PublicVisibility(),
        correlation_id=correlation_id,
    )
    await collector.on_post_publish(test_agent, ctx, output)

    await collector.on_terminate(test_agent, ctx)

    # Verify all events have same correlation_id
    assert len(collector.events) == 3
    for event in collector.events:
        assert event.correlation_id == str(correlation_id)


@pytest.mark.asyncio
async def test_event_schemas_match_data_model(collector, test_agent, test_context):
    """Test that event schemas exactly match DATA_MODEL.md specifications."""
    # Test AgentActivatedEvent schema
    # Don't set subscriptions directly - let the agent use its defaults

    artifact = Artifact(
        id=uuid4(),
        type="TestInput",
        payload={"test": "data"},
        produced_by="external",
        visibility=PublicVisibility(),
        correlation_id=test_context.correlation_id,
    )

    await collector.on_pre_consume(test_agent, test_context, [artifact])

    event = collector.events[0]
    # Verify all required fields from DATA_MODEL.md lines 53-66
    required_fields = [
        "agent_name",
        "agent_id",
        "consumed_types",
        "consumed_artifacts",
        "subscription_info",
        "labels",
        "tenant_id",
        "max_concurrency",
        "correlation_id",
        "timestamp",
    ]
    for field in required_fields:
        assert hasattr(event, field), f"Missing required field: {field}"

    # Test MessagePublishedEvent schema
    collector.events.clear()
    output = Artifact(
        id=uuid4(),
        type="TestOutput",
        payload={"result": "test"},
        produced_by="test_agent",
        visibility=PrivateVisibility(agents=["agent1"]),
        correlation_id=test_context.correlation_id,
        tags=["test"],
        version=1,
    )

    await collector.on_post_publish(test_agent, test_context, output)

    event = collector.events[0]
    # Verify all required fields from DATA_MODEL.md lines 100-115
    required_fields = [
        "artifact_id",
        "artifact_type",
        "produced_by",
        "payload",
        "visibility",
        "tags",
        "version",
        "consumers",
        "correlation_id",
        "timestamp",
    ]
    for field in required_fields:
        assert hasattr(event, field), f"Missing required field: {field}"

    # Verify visibility structure
    assert hasattr(event.visibility, "kind")
    assert event.visibility.kind == "Private"
    assert hasattr(event.visibility, "agents")


@pytest.mark.asyncio
async def test_in_memory_buffer_max_size(collector, test_agent, test_context):
    """Test that in-memory buffer respects 100-event limit."""
    # Generate more than 100 events
    for i in range(120):
        artifact = Artifact(
            id=uuid4(),
            type="TestOutput",
            payload={"index": i},
            produced_by="test_agent",
            visibility=PublicVisibility(),
            correlation_id=test_context.correlation_id,
        )
        await collector.on_post_publish(test_agent, test_context, artifact)

    # Verify buffer is capped at 100
    assert len(collector.events) == 100

    # Verify oldest events were evicted (LRU)
    # First event should have index >= 20
    first_event = collector.events[0]
    assert first_event.payload["index"] >= 20


@pytest.mark.asyncio
async def test_multiple_agents_different_correlation_ids(orchestrator):
    """Test that collector tracks events from multiple agents with different correlation_ids."""
    collector = DashboardEventCollector(store=InMemoryBlackboardStore())

    # Create two agents - access underlying agent objects
    agent1 = orchestrator.agent("agent1")._agent
    agent2 = orchestrator.agent("agent2")._agent

    # Create two contexts with different correlation_ids
    corr_id_1 = uuid4()
    corr_id_2 = uuid4()

    ctx1 = Context(
        board=orchestrator.store,
        orchestrator=orchestrator,
        task_id=f"task-{uuid4()}",
        state={},
        correlation_id=corr_id_1,
    )

    ctx2 = Context(
        board=orchestrator.store,
        orchestrator=orchestrator,
        task_id=f"task-{uuid4()}",
        state={},
        correlation_id=corr_id_2,
    )

    # Emit events from both agents
    artifact1 = Artifact(
        id=uuid4(),
        type="Output1",
        payload={"agent": 1},
        produced_by="agent1",
        visibility=PublicVisibility(),
        correlation_id=corr_id_1,
    )

    artifact2 = Artifact(
        id=uuid4(),
        type="Output2",
        payload={"agent": 2},
        produced_by="agent2",
        visibility=PublicVisibility(),
        correlation_id=corr_id_2,
    )

    await collector.on_post_publish(agent1, ctx1, artifact1)
    await collector.on_post_publish(agent2, ctx2, artifact2)

    # Verify both events captured
    assert len(collector.events) == 2

    # Verify correlation_ids are different
    assert collector.events[0].correlation_id == str(corr_id_1)
    assert collector.events[1].correlation_id == str(corr_id_2)


@pytest.mark.asyncio
async def test_visibility_serialization(collector, test_agent, test_context):
    """Test that all visibility types serialize correctly."""
    test_cases = [
        (PublicVisibility(), {"kind": "Public"}),
        (
            PrivateVisibility(agents=["agent1", "agent2"]),
            {"kind": "Private", "agents": ["agent1", "agent2"]},
        ),
        (
            LabelledVisibility(required_labels=["admin", "user"]),
            {"kind": "Labelled", "required_labels": ["admin", "user"]},
        ),
        (
            TenantVisibility(tenant_id="tenant-123"),
            {"kind": "Tenant", "tenant_id": "tenant-123"},
        ),
    ]

    for visibility, expected_dict in test_cases:
        collector.events.clear()

        artifact = Artifact(
            id=uuid4(),
            type="TestOutput",
            payload={"test": "data"},
            produced_by="test_agent",
            visibility=visibility,
            correlation_id=test_context.correlation_id,
        )

        await collector.on_post_publish(test_agent, test_context, artifact)

        event = collector.events[0]
        assert event.visibility.kind == expected_dict["kind"]

        # Verify specific fields for each type
        if "agents" in expected_dict:
            assert set(event.visibility.agents) == set(expected_dict["agents"])
        if "required_labels" in expected_dict:
            assert set(event.visibility.required_labels) == set(
                expected_dict["required_labels"]
            )
        if "tenant_id" in expected_dict:
            assert event.visibility.tenant_id == expected_dict["tenant_id"]


@pytest.mark.asyncio
async def test_event_timestamps_are_iso_format(collector, test_agent, test_context):
    """Test that all events have ISO 8601 UTC timestamps."""

    # Emit various events
    artifact = Artifact(
        id=uuid4(),
        type="TestInput",
        payload={"test": "data"},
        produced_by="external",
        visibility=PublicVisibility(),
        correlation_id=test_context.correlation_id,
    )

    await collector.on_pre_consume(test_agent, test_context, [artifact])

    output = Artifact(
        id=uuid4(),
        type="TestOutput",
        payload={"result": "test"},
        produced_by="test_agent",
        visibility=PublicVisibility(),
        correlation_id=test_context.correlation_id,
    )
    await collector.on_post_publish(test_agent, test_context, output)

    await collector.on_terminate(test_agent, test_context)

    # Verify all timestamps are ISO 8601 format
    for event in collector.events:
        # Parse timestamp to verify format
        timestamp = datetime.fromisoformat(event.timestamp.replace("Z", "+00:00"))
        assert timestamp is not None

        # Verify timestamp ends with Z (UTC)
        assert event.timestamp.endswith("Z")


@pytest.mark.asyncio
async def test_collector_as_agent_component(orchestrator):
    """Test that collector can be added as agent component and hooks are called."""
    from flock.components.agent import EngineComponent
    from flock.registry import flock_type
    from flock.utils.runtime import EvalInputs, EvalResult

    # Register test types
    @flock_type(name="CollectorTestInput")
    class CollectorTestInput(BaseModel):
        content: str

    @flock_type(name="CollectorTestOutput")
    class CollectorTestOutput(BaseModel):
        result: str

    # Create simple echo engine
    class EchoEngine(EngineComponent):
        async def evaluate(
            self, agent, ctx, inputs: EvalInputs, output_group
        ) -> EvalResult:
            # Transform input to output
            output = CollectorTestOutput(result=inputs.artifacts[0].payload["content"])
            return EvalResult.from_object(output, agent=agent)

    # Create agent with collector
    collector = DashboardEventCollector(store=InMemoryBlackboardStore())
    agent = (
        orchestrator.agent("test_agent")
        .consumes(CollectorTestInput)
        .with_utilities(collector)
        .with_engines(EchoEngine())
    )

    # Create input
    test_input = CollectorTestInput(content="test")

    # Run agent (this will trigger lifecycle hooks)
    await orchestrator.invoke(agent, test_input)

    # Verify events were captured
    # Should have: agent_activated, message_published (output), agent_completed
    assert len(collector.events) >= 2  # At minimum: activated and completed

    # Verify event types
    event_types = [type(event).__name__ for event in collector.events]
    assert "AgentActivatedEvent" in event_types
    assert "AgentCompletedEvent" in event_types

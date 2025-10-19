"""Tests for Store functionality."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import BaseModel

from flock.core.artifacts import Artifact
from flock.core.store import (
    ArtifactEnvelope,
    ConsumptionRecord,
    FilterConfig,
    InMemoryBlackboardStore,
    SQLiteBlackboardStore,
)
from flock.core.visibility import PublicVisibility
from flock.registry import flock_type, type_registry


@flock_type(name="TypeA")
class TypeA(BaseModel):
    data: str


@flock_type(name="TypeB")
class TypeB(BaseModel):
    data: str


@pytest.fixture(params=["memory", "sqlite"], ids=["memory", "sqlite"])
async def store(tmp_path, request):
    """Create a store instance for the given backend."""
    if request.param == "memory":
        yield InMemoryBlackboardStore()
    else:
        db_path = tmp_path / "blackboard.db"
        store = SQLiteBlackboardStore(str(db_path))
        await store.ensure_schema()
        try:
            yield store
        finally:
            await store.close()


@pytest.fixture
def sample_artifacts():
    """Create sample artifacts for testing."""
    return [
        Artifact(
            id=uuid4(),
            type="TypeA",
            payload={"data": "test1"},
            produced_by="agent1",
            visibility=PublicVisibility(),
        ),
        Artifact(
            id=uuid4(),
            type="TypeB",
            payload={"data": "test2"},
            produced_by="agent2",
            visibility=PublicVisibility(),
        ),
        Artifact(
            id=uuid4(),
            type="TypeA",
            payload={"data": "test3"},
            produced_by="agent3",
            visibility=PublicVisibility(),
        ),
    ]


@pytest.mark.asyncio
async def test_store_add_single_artifact(store, sample_artifacts):
    """Test adding a single artifact to the store."""
    artifact = sample_artifacts[0]
    await store.publish(artifact)

    artifacts = await store.list()
    assert len(artifacts) == 1
    assert artifacts[0].id == artifact.id
    assert artifacts[0].type == artifact.type


@pytest.mark.asyncio
async def test_store_add_multiple_artifacts(store, sample_artifacts):
    """Test adding multiple artifacts to the store."""
    for artifact in sample_artifacts:
        await store.publish(artifact)

    artifacts = await store.list()
    assert len(artifacts) == 3

    # Verify all artifacts are present
    stored_ids = {a.id for a in artifacts}
    expected_ids = {a.id for a in sample_artifacts}
    assert stored_ids == expected_ids


@pytest.mark.asyncio
async def test_store_list_empty(store):
    """Test listing artifacts from an empty store."""
    artifacts = await store.list()
    assert artifacts == []


@pytest.mark.asyncio
async def test_store_list_with_type_filter(store, sample_artifacts):
    """Test listing artifacts with type filtering."""
    for artifact in sample_artifacts:
        await store.publish(artifact)

    # Filter by TypeA
    type_a_artifacts = await store.list_by_type("TypeA")
    assert len(type_a_artifacts) == 2
    assert all(a.type == "TypeA" for a in type_a_artifacts)

    # Filter by TypeB
    type_b_artifacts = await store.list_by_type("TypeB")
    assert len(type_b_artifacts) == 1
    assert type_b_artifacts[0].type == "TypeB"


@pytest.mark.asyncio
async def test_store_get_by_id(store, sample_artifacts):
    """Test getting artifact by ID."""
    artifact = sample_artifacts[0]
    await store.publish(artifact)

    # Get existing artifact
    retrieved = await store.get(artifact.id)
    assert retrieved is not None
    assert retrieved.id == artifact.id
    assert retrieved.type == artifact.type

    # Get non-existent artifact
    non_existent = await store.get(uuid4())
    assert non_existent is None


@pytest.mark.asyncio
async def test_store_maintains_insertion_order(store):
    """Test that store maintains insertion order."""
    artifacts = []
    for i in range(5):
        artifact = Artifact(
            id=uuid4(),
            type=f"Type{i}",
            payload={"order": i},
            produced_by=f"agent{i}",
            visibility=PublicVisibility(),
        )
        artifacts.append(artifact)
        await store.publish(artifact)

    stored = await store.list()
    assert len(stored) == 5

    # Verify order is maintained
    for i, artifact in enumerate(stored):
        assert artifact.payload["order"] == i


@pytest.mark.asyncio
async def test_store_duplicate_artifacts(store):
    """Test adding duplicate artifacts (same ID)."""
    artifact_id = uuid4()
    artifact1 = Artifact(
        id=artifact_id,
        type="TypeA",
        payload={"version": 1},
        produced_by="agent1",
        visibility=PublicVisibility(),
    )
    artifact2 = Artifact(
        id=artifact_id,
        type="TypeA",
        payload={"version": 2},
        produced_by="agent1",
        visibility=PublicVisibility(),
    )

    await store.publish(artifact1)
    await store.publish(artifact2)

    # Store deduplicates by ID - latest wins
    artifacts = await store.list()
    assert len(artifacts) == 1
    # Verify latest version is stored
    assert artifacts[0].payload["version"] == 2


@pytest.mark.asyncio
async def test_store_thread_safety(store):
    """Test that store operations are thread-safe."""
    import asyncio

    async def add_artifacts(agent_name: str, count: int):
        for i in range(count):
            artifact = Artifact(
                type="TestType",
                payload={"agent": agent_name, "index": i},
                produced_by=agent_name,
                visibility=PublicVisibility(),
            )
            await store.publish(artifact)

    # Run multiple concurrent additions
    await asyncio.gather(
        add_artifacts("agent1", 10),
        add_artifacts("agent2", 10),
        add_artifacts("agent3", 10),
    )

    artifacts = await store.list()
    assert len(artifacts) == 30

    # Verify all artifacts are present
    agent1_count = len([a for a in artifacts if a.produced_by == "agent1"])
    agent2_count = len([a for a in artifacts if a.produced_by == "agent2"])
    agent3_count = len([a for a in artifacts if a.produced_by == "agent3"])

    assert agent1_count == 10
    assert agent2_count == 10
    assert agent3_count == 10


@pytest.mark.asyncio
async def test_sqlite_store_schema_idempotent(tmp_path):
    """Ensure SQLite schema creation can run multiple times without error."""
    store = SQLiteBlackboardStore(str(tmp_path / "schema.db"))
    await store.ensure_schema()
    await store.ensure_schema()  # run twice for idempotency
    await store.close()


@pytest.mark.asyncio
@pytest.mark.order(1)  # Run early to avoid registry race conditions
async def test_store_query_and_summary(store):
    """Verify filtering, pagination, and summaries across backends."""
    base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)

    artifacts = [
        Artifact(
            id=uuid4(),
            type=type_registry.name_for(TypeA),
            payload={"data": "alpha-1"},
            produced_by="agent1",
            tags={"alpha", "beta"},
            correlation_id=uuid4(),
            created_at=base_time,
        ),
        Artifact(
            id=uuid4(),
            type=type_registry.name_for(TypeA),
            payload={"data": "alpha-2"},
            produced_by="agent1",
            tags={"alpha"},
            correlation_id=uuid4(),
            created_at=base_time + timedelta(minutes=1),
        ),
        Artifact(
            id=uuid4(),
            type=type_registry.name_for(TypeB),
            payload={"data": "beta"},
            produced_by="agent2",
            tags={"beta"},
            correlation_id=uuid4(),
            created_at=base_time + timedelta(minutes=2),
        ),
    ]

    for artifact in artifacts:
        await store.publish(artifact)

    # Filter by canonical type and tags
    filtered, total = await store.query_artifacts(
        FilterConfig(
            type_names={type_registry.name_for(TypeA)},
            tags={"alpha"},
        ),
        limit=10,
        offset=0,
    )
    assert total == 2
    assert len(filtered) == 2
    assert all(item.type == type_registry.name_for(TypeA) for item in filtered)

    # Pagination
    paged, total = await store.query_artifacts(
        FilterConfig(type_names={type_registry.name_for(TypeA)}),
        limit=1,
        offset=1,
    )
    assert total == 2
    assert len(paged) == 1
    assert paged[0].payload["data"] == "alpha-2"

    # Time range filter to limit to latest artifact
    recent_only, total = await store.query_artifacts(
        FilterConfig(start=base_time + timedelta(minutes=2)),
        limit=10,
    )
    assert total == 1
    assert recent_only[0].type == type_registry.name_for(TypeB)

    summary = await store.summarize_artifacts()
    assert summary["total"] == 3
    assert any(
        key.endswith("TypeA") and value == 2
        for key, value in summary["by_type"].items()
    )
    assert summary["by_producer"]["agent1"] == 2
    assert summary["earliest_created_at"].startswith("2025-01-01T12:00:00")


@pytest.mark.asyncio
@pytest.mark.order(2)  # Run early to avoid registry race conditions
async def test_query_artifacts_embed_meta_returns_consumptions(store):
    now = datetime.now(UTC)
    artifact = Artifact(
        type=type_registry.name_for(TypeA),
        payload={"value": "embedded"},
        produced_by="agent_source",
        tags={"history"},
        correlation_id=uuid4(),
        created_at=now,
    )
    await store.publish(artifact)

    await store.record_consumptions([
        ConsumptionRecord(
            artifact_id=artifact.id,
            consumer="agent_consumer",
            run_id="run-123",
            correlation_id="corr-embedded",
            consumed_at=now,
        )
    ])

    results, total = await store.query_artifacts(
        FilterConfig(type_names={artifact.type}),
        limit=10,
        offset=0,
        embed_meta=True,
    )

    assert total == 1
    assert len(results) == 1

    envelope = results[0]
    assert isinstance(envelope, ArtifactEnvelope)
    assert len(envelope.consumptions) == 1
    assert envelope.consumptions[0].consumer == "agent_consumer"
    assert envelope.consumptions[0].correlation_id == "corr-embedded"


@pytest.mark.asyncio
@pytest.mark.order(3)  # Run early to avoid registry race conditions
async def test_agent_history_summary_counts(store):
    now = datetime.now(UTC)
    artifact = Artifact(
        type=type_registry.name_for(TypeA),
        payload={"value": "summary"},
        produced_by="agent_producer",
        tags={"summary"},
        correlation_id=uuid4(),
        created_at=now,
    )
    await store.publish(artifact)

    await store.record_consumptions([
        ConsumptionRecord(
            artifact_id=artifact.id,
            consumer="agent_consumer",
            run_id="run-456",
            correlation_id="corr-summary",
            consumed_at=now,
        )
    ])

    producer_summary = await store.agent_history_summary(
        "agent_producer", FilterConfig()
    )
    assert producer_summary["produced"]["total"] == 1
    assert producer_summary["produced"]["by_type"][artifact.type] == 1
    assert producer_summary["consumed"]["total"] == 0

    consumer_summary = await store.agent_history_summary(
        "agent_consumer", FilterConfig()
    )
    assert consumer_summary["consumed"]["total"] == 1
    assert consumer_summary["consumed"]["by_type"][artifact.type] == 1

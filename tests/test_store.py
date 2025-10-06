"""Tests for Store functionality."""

from uuid import uuid4

import pytest
from pydantic import BaseModel

from flock.artifacts import Artifact
from flock.registry import flock_type
from flock.store import InMemoryBlackboardStore
from flock.visibility import PublicVisibility


@flock_type(name="TypeA")
class TypeA(BaseModel):
    data: str


@flock_type(name="TypeB")
class TypeB(BaseModel):
    data: str


@pytest.fixture
def store():
    """Create an InMemoryBlackboardStore instance."""
    return InMemoryBlackboardStore()


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
async def test_store_thread_safety():
    """Test that store operations are thread-safe."""
    import asyncio

    store = InMemoryBlackboardStore()

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

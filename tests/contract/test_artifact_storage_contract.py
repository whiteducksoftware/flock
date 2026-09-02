"""Contract tests for artifact storage and retrieval with type normalization."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from flock.core.artifacts import Artifact
from flock.core.store import InMemoryBlackboardStore, SQLiteBlackboardStore
from flock.core.visibility import (
    AfterVisibility,
    AgentIdentity,
    PrivateVisibility,
    PublicVisibility,
)
from flock.registry import flock_type, type_registry


@pytest.fixture(params=["memory", "sqlite"], ids=["memory", "sqlite"])
async def storage_store(tmp_path, request):
    """Provide store implementations while preserving registry state."""
    saved_by_name = type_registry._by_name.copy()
    saved_by_cls = type_registry._by_cls.copy()

    if request.param == "memory":
        store = InMemoryBlackboardStore()
        cleanup = None
    else:
        db_path = tmp_path / f"contract-{uuid4()}.db"
        store = SQLiteBlackboardStore(str(db_path))
        await store.ensure_schema()
        cleanup = store.close

    try:
        yield store
    finally:
        type_registry._by_name.clear()
        type_registry._by_cls.clear()
        type_registry._by_name.update(saved_by_name)
        type_registry._by_cls.update(saved_by_cls)
        if cleanup is not None:
            await cleanup()


@pytest.mark.asyncio
async def test_publish_stores_with_canonical_name(storage_store):
    """S1: Artifacts are stored with their canonical type names."""

    @flock_type
    class Document(BaseModel):
        content: str

    canonical_name = type_registry.name_for(Document)

    artifact = Artifact(
        type=canonical_name,
        payload={"content": "test"},
        produced_by="test_agent",
        visibility=PublicVisibility(),
    )

    await storage_store.publish(artifact)

    results = await storage_store.list_by_type(canonical_name)
    assert len(results) == 1
    assert results[0].payload["content"] == "test"


@pytest.mark.asyncio
async def test_list_by_simple_name_finds_qualified_artifacts(storage_store):
    """S2: list_by_type(simple) finds artifacts stored with qualified names."""

    @flock_type
    class Document(BaseModel):
        content: str

    canonical_name = type_registry.name_for(Document)

    artifact = Artifact(
        type=canonical_name,
        payload={"content": "test"},
        produced_by="test_agent",
        visibility=PublicVisibility(),
    )

    await storage_store.publish(artifact)

    results = await storage_store.list_by_type("Document")
    assert len(results) == 1
    assert results[0].payload["content"] == "test"


@pytest.mark.asyncio
async def test_cross_context_type_resolution(storage_store):
    """S3: Artifacts from __main__ can be queried from test context."""

    class Document(BaseModel):
        title: str

    type_registry.register(Document, name="__main__.Document")

    artifact = Artifact(
        type="__main__.Document",
        payload={"title": "Test"},
        produced_by="main_script",
        visibility=PublicVisibility(),
    )

    await storage_store.publish(artifact)

    results = await storage_store.list_by_type("Document")
    assert len(results) == 1
    assert results[0].payload["title"] == "Test"


@pytest.mark.asyncio
async def test_multiple_artifacts_same_type(storage_store):
    """S4: Multiple artifacts of same type are all retrievable."""

    @flock_type
    class Document(BaseModel):
        content: str

    canonical_name = type_registry.name_for(Document)

    artifacts = [
        Artifact(
            type=canonical_name,
            payload={"content": f"doc{i}"},
            produced_by="test_agent",
            visibility=PublicVisibility(),
        )
        for i in range(3)
    ]

    for artifact in artifacts:
        await storage_store.publish(artifact)

    results = await storage_store.list_by_type("Document")
    assert len(results) == 3
    contents = {r.payload["content"] for r in results}
    assert contents == {"doc0", "doc1", "doc2"}


@pytest.mark.asyncio
async def test_query_artifacts_orders_equal_timestamps_by_id(storage_store):
    created_at = datetime(2026, 1, 1, tzinfo=UTC)
    for value in (3, 1, 2):
        await storage_store.publish(
            Artifact(
                id=UUID(int=value),
                type="demo.Ordered",
                payload={},
                produced_by="test",
                created_at=created_at,
            )
        )

    ordered, _ = await storage_store.query_artifacts(limit=0)

    assert [artifact.id for artifact in ordered] == [
        UUID(int=value) for value in (1, 2, 3)
    ]


@pytest.mark.asyncio
async def test_nested_visibility_roundtrip_preserves_policy(storage_store):
    created_at = datetime(2026, 1, 1, tzinfo=UTC)
    artifact = Artifact(
        type="demo.Secret",
        payload={"value": "secret"},
        produced_by="writer",
        created_at=created_at,
        visibility=AfterVisibility(
            ttl=timedelta(days=1),
            then=PrivateVisibility(agents={"reviewer"}),
        ),
    )

    await storage_store.publish(artifact)
    restored = await storage_store.get(artifact.id)

    assert isinstance(restored.visibility, AfterVisibility)
    assert restored.visibility.ttl == timedelta(days=1)
    assert isinstance(restored.visibility.then, PrivateVisibility)
    assert restored.visibility.then.agents == {"reviewer"}
    assert not restored.visibility.allows(
        AgentIdentity(name="reviewer"), now=created_at + timedelta(hours=1)
    )
    assert restored.visibility.allows(
        AgentIdentity(name="reviewer"), now=created_at + timedelta(days=2)
    )
    assert not restored.visibility.allows(
        AgentIdentity(name="outsider"), now=created_at + timedelta(days=2)
    )

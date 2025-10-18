from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import BaseModel

from flock.core.artifacts import Artifact
from flock.core.store import ConsumptionRecord, FilterConfig, SQLiteBlackboardStore
from flock.core.visibility import PublicVisibility
from flock.registry import flock_type


@flock_type(name="GraphType")
class GraphTypeModel(BaseModel):
    value: int | None = None


@flock_type(name="A")
class TypeAModel(BaseModel):
    value: int | None = None


@flock_type(name="B")
class TypeBModel(BaseModel):
    value: int | None = None


@pytest.mark.asyncio
async def test_fetch_graph_artifacts_returns_envelopes(tmp_path):
    db_path = tmp_path / "graph.db"
    store = SQLiteBlackboardStore(str(db_path))
    await store.ensure_schema()

    correlation_id = uuid4()

    artifact = Artifact(
        type="GraphType",
        payload={"value": 42},
        produced_by="producer",
        visibility=PublicVisibility(),
        correlation_id=correlation_id,
    )
    await store.publish(artifact)

    await store.record_consumptions([
        ConsumptionRecord(
            artifact_id=artifact.id,
            consumer="consumer",
            run_id="run-graph",
            correlation_id=str(correlation_id),
            consumed_at=datetime.now(UTC),
        )
    ])

    envelopes, total = await store.fetch_graph_artifacts(
        FilterConfig(),
        limit=10,
    )

    assert total == 1
    assert len(envelopes) == 1
    envelope = envelopes[0]
    assert envelope.artifact.id == artifact.id
    assert envelope.consumptions[0].consumer == "consumer"
    assert envelope.consumptions[0].run_id == "run-graph"

    await store.close()


@pytest.mark.asyncio
async def test_fetch_graph_artifacts_applies_filters(tmp_path):
    db_path = tmp_path / "graph-filter.db"
    store = SQLiteBlackboardStore(str(db_path))
    await store.ensure_schema()

    a = Artifact(
        type="A",
        payload={},
        produced_by="agent_a",
        visibility=PublicVisibility(),
    )
    b = Artifact(
        type="B",
        payload={},
        produced_by="agent_b",
        visibility=PublicVisibility(),
    )

    await store.publish(a)
    await store.publish(b)

    envelopes, total = await store.fetch_graph_artifacts(
        FilterConfig(type_names={"B"}),
        limit=10,
    )

    assert total == 1
    assert len(envelopes) == 1
    assert envelopes[0].artifact.type == "B"

    await store.close()

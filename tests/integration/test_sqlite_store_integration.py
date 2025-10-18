from __future__ import annotations

import pytest
from pydantic import BaseModel

from flock.core import Flock
from flock.core.store import SQLiteBlackboardStore
from flock.registry import flock_type, type_registry


@flock_type
class IntegrationArtifact(BaseModel):
    value: str


@pytest.mark.asyncio
async def test_flock_with_sqlite_store(tmp_path):
    """Ensure orchestrator operates correctly with SQLite-backed store."""
    db_path = tmp_path / "integration-board.db"
    store = SQLiteBlackboardStore(str(db_path))
    await store.ensure_schema()

    orchestrator = Flock(store=store)

    artifact = IntegrationArtifact(value="hello")
    published = await orchestrator.publish(artifact)
    await orchestrator.run_until_idle()

    stored = await orchestrator.store.get(published.id)
    assert stored is not None
    assert stored.payload["value"] == "hello"
    artifacts = await orchestrator.store.list_by_type(
        type_registry.resolve_name("IntegrationArtifact")
    )
    assert len(artifacts) == 1

    await store.close()

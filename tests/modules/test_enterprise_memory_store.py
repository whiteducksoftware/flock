import pytest

from types import SimpleNamespace
from flock.modules.enterprise_memory.enterprise_memory_module import EnterpriseMemoryStore, EnterpriseMemoryModuleConfig
from flock.adapter.vector_base import VectorAdapter, VectorHit


class DummyAdapter(VectorAdapter):
    """In-memory adapter used solely for tests."""

    def __init__(self):
        super().__init__()
        self._store = {}

    def add(self, *, id: str, content: str, embedding: list[float], metadata=None):
        self._store[id] = (content, embedding, metadata)

    def query(self, *, embedding: list[float], k: int):
        # naive similarity = inverse L2
        import numpy as np
        hits = []
        for _id, (content, vec, meta) in self._store.items():
            dist = float(np.linalg.norm(np.array(vec) - np.array(embedding)))
            score = 1 - dist
            hits.append(VectorHit(id=_id, content=content, metadata=meta or {}, score=score))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]


@pytest.mark.asyncio
async def test_enterprise_memory_store_add_and_search(monkeypatch):
    # Prepare config with save_interval=0 to avoid graph writes
    cfg = EnterpriseMemoryModuleConfig(vector_backend="faiss", save_interval=0)
    store = EnterpriseMemoryStore(cfg)

    # Patch adapter and embedding model
    dummy_adapter = DummyAdapter()
    monkeypatch.setattr(store, "_ensure_adapter", lambda: dummy_adapter)
    monkeypatch.setattr(store, "_ensure_embedding_model", lambda: SimpleNamespace(encode=lambda txt: [0.1, 0.2, 0.3]))

    # Add entry
    entry_id = await store.add_entry("hello world", {"hello"})
    assert entry_id in dummy_adapter._store

    # Search
    results = await store.search("hello world", threshold=0.0, k=5)
    assert results
    assert results[0]["id"] == entry_id 
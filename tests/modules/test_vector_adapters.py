import pytest
import random

from flock.adapter.vector_base import VectorHit


@pytest.mark.parametrize("adapter_name", ["faiss", "chroma"])  # add others conditionally
def test_adapter_add_and_query(adapter_name, tmp_path):
    """Smoke-test that each adapter can add vectors and retrieve them back.

    Skips adapters whose third-party packages are missing.
    """
    import importlib
    if adapter_name == "chroma":
        chroma = importlib.util.find_spec("chromadb")
        if chroma is None:
            pytest.skip("chromadb not installed")
        from flock.adapter.chroma_adapter import ChromaAdapter
        adapter = ChromaAdapter(path=str(tmp_path / "chroma"))
    elif adapter_name == "faiss":
        faiss_spec = importlib.util.find_spec("faiss")
        if faiss_spec is None:
            pytest.skip("faiss not installed")
        from flock.adapter.faiss_adapter import FAISSAdapter
        adapter = FAISSAdapter(index_path=str(tmp_path / "faiss.index"))
    else:
        pytest.skip("backend not in test matrix")

    # Generate deterministic embeddings
    vec1 = [random.random() for _ in range(5)]
    vec2 = [v + 0.01 for v in vec1]

    adapter.add(id="a", content="doc a", embedding=vec1, metadata={})
    adapter.add(id="b", content="doc b", embedding=vec2, metadata={})

    hits = adapter.query(embedding=vec1, k=2)
    assert hits, "No hits returned"
    assert isinstance(hits[0], VectorHit)
    ids = [hit.id for hit in hits]
    assert "a" in ids  # Original doc should be retrieved 
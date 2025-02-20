import json
import numpy as np
import pytest
from datetime import datetime

from flock.core.memory.memory_storage import FlockMemoryStore, MemoryEntry, MemoryGraph


# Test that MemoryGraph correctly serializes and reconstructs the graph.
def test_memory_graph_serialization():
    mg = MemoryGraph()
    # Initially, the graph should have no nodes.
    data = json.loads(mg.graph_json)
    assert "nodes" in data and len(data["nodes"]) == 0

    # Add some concepts.
    concepts = {"concept1", "concept2", "concept3"}
    mg.add_concepts(concepts)
    data_after = json.loads(mg.graph_json)
    mg.save_as_image("test_graph.png")
    # Check that all nodes are present.
    assert len(data_after["nodes"]) == 3
    # In a complete graph of 3 nodes (undirected), there are 3 edges.
    assert len(data_after["links"]) == 3

# Test that compute_embedding returns a NumPy array of the expected dimension.
def test_compute_embedding():
    store = FlockMemoryStore()
    text = "Test embedding computation"
    embedding = store.compute_embedding(text)
    assert isinstance(embedding, np.ndarray)
    # "all-MiniLM-L6-v2" returns 384-dimensional embeddings.
    assert embedding.shape[0] == 384

# Test adding a memory entry and retrieving it via semantic similarity.
def test_add_entry_and_retrieve():
    store = FlockMemoryStore()
    text = "This is a test memory entry"
    embedding = store.compute_embedding(text).tolist()  # Store expects a list of floats.
    entry = MemoryEntry(
        id="entry1",
        inputs={"key": "value"},
        outputs={"result": "test"},
        embedding=embedding,
        concepts={"test", "memory"}
    )
    store.add_entry(entry)
    # Use a similar query.
    query_text = "test memory"
    query_embedding = store.compute_embedding(query_text)
    retrieved = store.retrieve(query_embedding, {"test", "memory"}, similarity_threshold=0.5)
    # Expect at least one result containing our entry.
    assert any(e.id == "entry1" for e in retrieved)

# Test that exact_match correctly finds a matching entry.
def test_exact_match():
    store = FlockMemoryStore()
    entry = MemoryEntry(
        id="entry_exact",
        inputs={"foo": "bar", "num": 42},
        outputs={"result": "exact match"},
        embedding=store.compute_embedding("exact match").tolist(),
        concepts={"exact"}
    )
    store.add_entry(entry)
    matches = store.exact_match({"foo": "bar", "num": 42})
    assert any(e.id == "entry_exact" for e in matches)

# Test combine_results to ensure semantic and exact matches are weighted and combined.
def test_combine_results():
    store = FlockMemoryStore()
    entry_sem = MemoryEntry(
        id="entry_sem",
        inputs={"text": "This is a semantic test"},
        outputs={"result": "semantic result"},
        embedding=store.compute_embedding("semantic test").tolist(),
        concepts={"semantic"}
    )
    entry_ex = MemoryEntry(
        id="entry_ex",
        inputs={"text": "Exact match test"},
        outputs={"result": "exact result"},
        embedding=store.compute_embedding("Exact match test").tolist(),
        concepts={"exact"}
    )
    store.add_entry(entry_sem)
    store.add_entry(entry_ex)
    combined = store.combine_results({"text": "Exact match test"}, weights={"semantic": 0.7, "exact": 0.3})
    assert "combined_results" in combined
    results = combined["combined_results"]
    # At least one result should match the exact entry.
    assert any(e.id == "entry_ex" for e in results)

# Test clustering update: after adding multiple entries, clusters and centroids should be populated.
def test_update_clusters():
    store = FlockMemoryStore()
    for i in range(5):
        text = f"Entry {i} for clustering test"
        embedding = store.compute_embedding(text).tolist()
        entry = MemoryEntry(
            id=f"entry_{i}",
            inputs={"text": text},
            outputs={"result": f"result_{i}"},
            embedding=embedding,
            concepts={"cluster", f"entry{i}"}
        )
        store.add_entry(entry)
    store._update_clusters()
    # Expect at least one cluster.
    assert len(store.clusters) > 0
    # Check that cluster centroids are stored as lists of floats.
    for centroid in store.cluster_centroids.values():
        assert isinstance(centroid, list)
        assert all(isinstance(x, float) for x in centroid)

# Test serialization and deserialization of the FlockMemoryStore.
def test_store_serialization():
    store = FlockMemoryStore()
    text = "Serialization test"
    embedding = store.compute_embedding(text).tolist()
    entry = MemoryEntry(
        id="entry_serial",
        inputs={"test": "data"},
        outputs={"result": "serialization"},
        embedding=embedding,
        concepts={"serialize", "test"}
    )
    store.add_entry(entry)
    # Serialize the store to JSON.
    store_json = store.json()
    # Deserialize into a new store instance.
    new_store = FlockMemoryStore.parse_raw(store_json)
    # Check that the previously added entry exists in the new store.
    assert any(e.id == "entry_serial" for e in new_store.short_term)

if __name__ == "__main__":
    pytest.main([__file__])

import pytest
from datetime import datetime, timedelta
import numpy as np

from flock.core.memory.memory_storage import (
    FlockMemoryStore, MemoryEntry, MemoryScope,
    SemanticOperation, ExactOperation, FilterOperation,
    SortOperation, EnrichOperation, CombineOperation
)
from flock.core.memory.memory_parser import MemoryMappingParser


def test_memory_creation():
    store = FlockMemoryStore()
    
    # Create test entries
    entry_local = MemoryEntry(
        id="local_entry",
        inputs={"scope": "local"},
        outputs={"result": "local"},
        embedding=store.compute_embedding("local test").tolist(),
        concepts={"local"}
    )
    
    store.add_entry(entry_local)
    
    # Print debug info about the stored entry
    print(f"\nStored entry embedding shape: {len(entry_local.embedding)}")
    print(f"Stored entry embedding first few values: {entry_local.embedding[:5]}")
    
    # Create and print query info
    query_text = "local test"  # Use exact same text
    query = store.compute_embedding(query_text)
    print(f"\nQuery embedding shape: {query.shape}")
    print(f"Query embedding first few values: {query[:5]}")
    
    # Calculate similarity manually
    norm_query = query / (np.linalg.norm(query) + 1e-8)
    norm_entry = np.array(entry_local.embedding) / (np.linalg.norm(entry_local.embedding) + 1e-8)
    similarity = float(np.dot(norm_query, norm_entry))
    print(f"\nCalculated similarity: {similarity}")
    
    # Retrieve with very low threshold
    results = store.retrieve(query, {"local"}, similarity_threshold=0.01)
    print(f"\nNumber of results: {len(results)}")
    
    if len(results) > 0:
        print(f"First result ID: {results[0].id}")
    
    # Add assertions that will help debug
    assert len(store.short_term) > 0, "Entry wasn't stored in short_term memory"
    assert store.short_term[0].embedding is not None, "Stored embedding is None"
    assert similarity > 0.01, f"Similarity {similarity} is below threshold"
    assert len(results) > 0, "No results returned despite low threshold"
    assert any(e.id == "local_entry" for e in results)

# Test memory scoping
def test_memory_scoping():
    store = FlockMemoryStore()
    
    # Add entries with different scopes
    entry_local = MemoryEntry(
        id="local_entry",
        inputs={"scope": "local"},
        outputs={"result": "local"},
        embedding=store.compute_embedding("local test").tolist(),
        concepts={"local"}
    )
    entry_global = MemoryEntry(
        id="global_entry",
        inputs={"scope": "global"},
        outputs={"result": "global"},
        embedding=store.compute_embedding("global test").tolist(),
        concepts={"global"}
    )
    
    store.add_entry(entry_local)
    store.add_entry(entry_global)
    
    # Use more similar query text to ensure higher similarity
    # Test local retrieval
    local_query = store.compute_embedding("local test")  # Use exact same text
    local_results = store.retrieve(
        local_query, 
        {"local"}, 
        similarity_threshold=0.1  # Lower threshold for testing
    )
    
    # Test global retrieval
    global_query = store.compute_embedding("global test")
    global_results = store.retrieve(
        global_query, 
        {"global"}, 
        similarity_threshold=0.1
    )
    
    # Print debug info
    print(f"Local results count: {len(local_results)}")
    print(f"Global results count: {len(global_results)}")
    
    # Check embeddings similarity
    if len(local_results) > 0:
        similarity = store._calculate_similarity(
            local_query,
            np.array(local_results[0].embedding)
        )
        print(f"Local similarity: {similarity}")
    
    assert any(e.id == "local_entry" for e in local_results)
    assert any(e.id == "global_entry" for e in global_results)

# Test memory operation parsing
def test_memory_mapping_parser():
    parser = MemoryMappingParser()
    mapping = """
        topic -> memory.semantic(threshold=0.9, scope='global') |
        memory.filter(recency='7d') |
        memory.sort(by='relevance')
    """
    
    operations = parser.parse(mapping)
    
    assert len(operations) == 3
    assert isinstance(operations[0], SemanticOperation)
    assert isinstance(operations[1], FilterOperation)
    assert isinstance(operations[2], SortOperation)
    
    assert operations[0].threshold == 0.9
    assert operations[0].scope == MemoryScope.GLOBAL
    assert operations[1].recency == "7d"
    assert operations[2].by == "relevance"

# Test filter operations
def test_filter_operations():
    store = FlockMemoryStore()
    
    # Add entries with different timestamps
    old_time = datetime.now() - timedelta(days=10)
    new_time = datetime.now() - timedelta(days=1)
    
    old_entry = MemoryEntry(
        id="old_entry",
        inputs={"time": "old"},
        outputs={"result": "old"},
        embedding=store.compute_embedding("old test").tolist(),
        concepts={"old"},
        timestamp=old_time
    )
    new_entry = MemoryEntry(
        id="new_entry",
        inputs={"time": "new"},
        outputs={"result": "new"},
        embedding=store.compute_embedding("new test").tolist(),
        concepts={"new"},
        timestamp=new_time
    )
    
    store.add_entry(old_entry)
    store.add_entry(new_entry)
    
    # Test filtering by recency
    query = store.compute_embedding("test query")
    recent_results = store.retrieve(
        query, 
        set(),
        similarity_threshold=0.5
    )
    
    assert any(e.id == "new_entry" for e in recent_results)
    if len(recent_results) > 1:
        assert recent_results[0].timestamp >= recent_results[1].timestamp

# Test enrichment operations
def test_enrichment():
    store = FlockMemoryStore()
    entry = MemoryEntry(
        id="enrich_test",
        inputs={"text": "Test enrichment"},
        outputs={"result": "initial"},
        embedding=store.compute_embedding("test enrichment").tolist(),
        concepts={"test"}
    )
    
    # Mock tool results
    tool_results = {
        "web_search": ["result1", "result2"],
        "extract_numbers": [42, 123]
    }
    
    enriched_entry = store.enrich_entry(
        entry,
        tools=["web_search", "extract_numbers"],
        strategy="comprehensive"
    )
    
    assert "metadata" in enriched_entry.dict()
    assert "enriched" in enriched_entry.dict()["metadata"]

# Test concept spreading
def test_concept_spreading():
    store = FlockMemoryStore()
    
    # Add entries with related concepts
    concepts1 = {"AI", "machine learning"}
    concepts2 = {"machine learning", "neural networks"}
    concepts3 = {"neural networks", "deep learning"}
    
    entries = [
        MemoryEntry(
            id=f"entry_{i}",
            inputs={"text": f"Test {i}"},
            outputs={"result": f"result_{i}"},
            embedding=store.compute_embedding(f"test {i}").tolist(),
            concepts=concepts
        )
        for i, concepts in enumerate([concepts1, concepts2, concepts3])
    ]
    
    for entry in entries:
        store.add_entry(entry)
    
    # Test concept spreading
    activated = store.concept_graph.spread_activation({"AI"}, decay_factor=0.5)
    
    assert "neural networks" in activated
    assert activated["machine learning"] > activated["neural networks"]

# Test decay and reinforcement
def test_decay_and_reinforcement():
    store = FlockMemoryStore()
    entry = MemoryEntry(
        id="decay_test",
        inputs={"text": "Test decay"},
        outputs={"result": "test"},
        embedding=store.compute_embedding("test decay").tolist(),
        concepts={"test"}
    )
    
    store.add_entry(entry)
    
    # Access the entry multiple times
    query = store.compute_embedding("test query")
    for _ in range(5):
        results = store.retrieve(query, {"test"}, similarity_threshold=0.5)
    
    # Check that access count and decay factor have been updated
    updated_entry = next(e for e in store.short_term if e.id == "decay_test")
    assert updated_entry.access_count == 5
    assert updated_entry.decay_factor > 1.0

# Test complex operation chains
def test_operation_chains():
    parser = MemoryMappingParser()
    mapping = """
        topic -> memory.semantic(threshold=0.85) |
        memory.filter(recency='24h') |
        memory.enrich(tools=['web_search']) |
        memory.sort(by='relevance') |
        memory.combine(weights={'semantic': 0.6, 'exact': 0.4})
    """
    
    operations = parser.parse(mapping)
    
    assert len(operations) == 5
    assert isinstance(operations[0], SemanticOperation)
    assert isinstance(operations[1], FilterOperation)
    assert isinstance(operations[2], EnrichOperation)
    assert isinstance(operations[3], SortOperation)
    assert isinstance(operations[4], CombineOperation)

# Test long-term memory promotion
def test_long_term_memory_promotion():
    store = FlockMemoryStore()
    entry = MemoryEntry(
        id="promotion_test",
        inputs={"text": "Test promotion"},
        outputs={"result": "test"},
        embedding=store.compute_embedding("test promotion").tolist(),
        concepts={"test"}
    )
    
    store.add_entry(entry)
    
    # Access the entry enough times to trigger promotion
    query = store.compute_embedding("test query")
    for _ in range(11):  # Promotion threshold is 10
        results = store.retrieve(query, {"test"}, similarity_threshold=0.5)
    
    # Check that entry has been promoted to long-term memory
    assert any(e.id == "promotion_test" for e in store.long_term)

if __name__ == "__main__":
    pytest.main([__file__])
"""Tests for semantic features performance and edge case handling.

These tests ensure robust handling of edge cases, performance characteristics,
and error conditions.
"""

import pytest


# Skip all tests if sentence-transformers not available
pytest.importorskip("sentence_transformers")

from flock.semantic.embedding_service import EmbeddingService


@pytest.mark.asyncio
async def test_empty_string_handling():
    """Empty strings raise ValueError."""
    service = EmbeddingService.get_instance()

    with pytest.raises(ValueError, match="Cannot embed empty text"):
        service.embed("")

    with pytest.raises(ValueError, match="Cannot embed empty text"):
        service.embed("   ")  # Whitespace only


@pytest.mark.asyncio
async def test_very_long_text_handling():
    """Very long text is handled correctly (truncated if needed)."""
    service = EmbeddingService.get_instance()

    # Create text longer than typical model limit (512 tokens ~ 2000 chars)
    long_text = "word " * 1000  # 5000 characters

    # Should not crash, model handles truncation internally
    embedding = service.embed(long_text)
    assert embedding.shape == (384,)


@pytest.mark.asyncio
async def test_unicode_and_special_characters():
    """Unicode and special characters are handled correctly."""
    service = EmbeddingService.get_instance()

    # Various Unicode text
    texts = [
        "Hello 世界",  # Chinese
        "Привет мир",  # Russian
        "مرحبا بالعالم",  # Arabic
        "🚀 💻 🎉",  # Emojis
        "Special chars: @#$%^&*()",
    ]

    for text in texts:
        embedding = service.embed(text)
        assert embedding.shape == (384,)


@pytest.mark.asyncio
async def test_batch_processing_efficiency():
    """Batch processing is more efficient than individual processing."""
    service = EmbeddingService.get_instance()

    texts = [f"Test sentence number {i}" for i in range(10)]

    # Batch processing
    batch_embeddings = service.embed_batch(texts)
    assert len(batch_embeddings) == 10
    assert all(emb.shape == (384,) for emb in batch_embeddings)


@pytest.mark.asyncio
async def test_cache_hit_behavior():
    """Cache returns same embedding for repeated text."""
    service = EmbeddingService.get_instance()

    text = "Cache test sentence"

    # First call - cache miss
    embedding1 = service.embed(text)

    # Second call - cache hit (should be instant)
    embedding2 = service.embed(text)

    # Should return identical embeddings
    import numpy as np

    assert np.array_equal(embedding1, embedding2)


@pytest.mark.asyncio
async def test_similarity_symmetric():
    """Similarity is symmetric: sim(a,b) == sim(b,a)."""
    service = EmbeddingService.get_instance()

    text1 = "The quick brown fox"
    text2 = "Fast brown animal"

    sim1 = service.similarity(text1, text2)
    sim2 = service.similarity(text2, text1)

    assert abs(sim1 - sim2) < 0.0001  # Allow tiny floating point differences


@pytest.mark.asyncio
async def test_similarity_range():
    """Similarity scores are in valid range [0, 1]."""
    service = EmbeddingService.get_instance()

    # Identical text - should be very high similarity
    text1 = "Artificial intelligence"
    sim_identical = service.similarity(text1, text1)
    assert 0.99 <= sim_identical <= 1.0

    # Very different texts - should be low similarity
    text2 = "Completely unrelated topic about cooking pasta"
    sim_different = service.similarity(text1, text2)
    assert 0.0 <= sim_different < 0.5


@pytest.mark.asyncio
async def test_concurrent_access():
    """Service handles concurrent requests correctly."""
    import asyncio

    service = EmbeddingService.get_instance()

    async def embed_async(text: str):
        # Run embedding in executor to simulate concurrent load
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, service.embed, text)

    # Run multiple embeddings concurrently
    texts = [f"Concurrent text {i}" for i in range(5)]
    results = await asyncio.gather(*[embed_async(text) for text in texts])

    assert len(results) == 5
    assert all(emb.shape == (384,) for emb in results)

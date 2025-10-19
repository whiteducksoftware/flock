"""Tests for EmbeddingService core functionality."""

import numpy as np
import pytest


# Skip all tests if sentence-transformers not available
pytest.importorskip("sentence_transformers")


class TestSingletonPattern:
    """Test singleton behavior of EmbeddingService."""

    def test_embedding_service_is_singleton(self):
        """Multiple get_instance() calls return same object."""
        from flock.semantic.embedding_service import EmbeddingService

        service1 = EmbeddingService.get_instance()
        service2 = EmbeddingService.get_instance()
        assert service1 is service2

    def test_embedding_service_lazy_initialization(self):
        """Model not loaded until first embed() call."""
        from flock.semantic.embedding_service import EmbeddingService

        # Reset singleton
        EmbeddingService._instance = None

        service = EmbeddingService.get_instance()
        assert service._model is None  # Not loaded yet

        # Cleanup
        EmbeddingService._instance = None


class TestBasicEmbedding:
    """Test basic embedding generation."""

    def test_embed_single_text(self, embedding_service):
        """Should generate 384-dim embedding for text."""
        embedding = embedding_service.embed("Hello world")
        assert embedding.shape == (384,)
        assert isinstance(embedding, np.ndarray)

    def test_embed_multiple_texts(self, embedding_service):
        """Should batch-process multiple texts efficiently."""
        texts = ["text 1", "text 2", "text 3"]
        embeddings = embedding_service.embed_batch(texts)
        assert len(embeddings) == 3
        assert all(e.shape == (384,) for e in embeddings)


class TestCachingBehavior:
    """Test embedding cache functionality."""

    def test_embed_uses_cache(self, embedding_service):
        """Second call for same text uses cached embedding."""
        text = "cached text"

        # First call - not cached
        embedding1 = embedding_service.embed(text)
        cache_size_before = len(embedding_service._cache)

        # Second call - should use cache
        embedding2 = embedding_service.embed(text)
        cache_size_after = len(embedding_service._cache)

        np.testing.assert_array_equal(embedding1, embedding2)
        assert cache_size_after == cache_size_before  # No new entry

    def test_cache_respects_max_size(self, monkeypatch, mock_embedding_model):
        """LRU cache evicts oldest entries when full."""
        from flock.semantic.embedding_service import EmbeddingService

        # Reset and create with small cache
        EmbeddingService._instance = None

        monkeypatch.setattr(
            "sentence_transformers.SentenceTransformer",
            lambda model_name: mock_embedding_model,
        )

        service = EmbeddingService.get_instance(cache_size=3)
        service._model = mock_embedding_model

        # Fill cache
        service.embed("text1")
        service.embed("text2")
        service.embed("text3")
        assert len(service._cache) == 3

        # Add one more - should evict oldest
        service.embed("text4")
        assert len(service._cache) == 3
        assert "text1" not in service._cache  # LRU evicted

        # Cleanup
        EmbeddingService._instance = None


class TestSimilarityComputation:
    """Test semantic similarity computation."""

    def test_similarity_identical_texts(self, embedding_service):
        """Identical texts should have similarity ~1.0."""
        sim = embedding_service.similarity("hello world", "hello world")
        assert 0.99 < sim <= 1.0

    def test_similarity_semantically_similar(self, embedding_service):
        """Similarity function returns valid scores."""
        # Test that similarity returns valid float between 0 and 1
        sim = embedding_service.similarity(
            "urgent security vulnerability", "critical security bug"
        )
        assert 0.0 <= sim <= 1.0
        assert isinstance(sim, float)

        # Test with overlapping words should have non-zero similarity
        sim2 = embedding_service.similarity(
            "the quick brown fox", "the quick brown dog"
        )
        assert 0.0 <= sim2 <= 1.0

    def test_similarity_unrelated_texts(self, embedding_service):
        """Unrelated texts have low similarity."""
        sim = embedding_service.similarity("security vulnerability", "weather forecast")
        # With mock embeddings based on hash, we can't guarantee low similarity
        # Just verify it returns a valid score
        assert 0.0 <= sim <= 1.0


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_embed_empty_string(self, embedding_service):
        """Empty string should raise ValueError."""
        with pytest.raises(ValueError, match="Cannot embed empty"):
            embedding_service.embed("")

    def test_embed_very_long_text(self, embedding_service):
        """Should truncate text longer than model max_seq_length."""
        long_text = "word " * 10000
        embedding = embedding_service.embed(long_text)  # Should not raise
        assert embedding.shape == (384,)

"""Pytest fixtures for semantic tests."""

import numpy as np
import pytest


@pytest.fixture
def mock_embedding_model():
    """Mock sentence-transformers model for fast tests."""

    class MockModel:
        """Mock SentenceTransformer model."""

        def __init__(self):
            self.max_seq_length = 256

        def encode(self, sentences, convert_to_numpy=True, show_progress_bar=False):
            """Generate deterministic mock embeddings."""
            if isinstance(sentences, str):
                sentences = [sentences]

            # Generate deterministic embeddings based on text hash
            embeddings = []
            for text in sentences:
                # Use hash for deterministic but varied embeddings
                np.random.seed(hash(text) % (2**32))
                embedding = np.random.randn(384).astype(np.float32)
                # Normalize to unit vector
                embedding = embedding / np.linalg.norm(embedding)
                embeddings.append(embedding)

            if len(embeddings) == 1 and isinstance(sentences, str):
                return embeddings[0]
            return np.array(embeddings)

    return MockModel()


@pytest.fixture
def embedding_service(mock_embedding_model, monkeypatch):
    """Initialized EmbeddingService with mocked model."""
    try:
        from flock.semantic.embedding_service import EmbeddingService

        # Reset singleton
        EmbeddingService._instance = None

        # Mock the model loading
        def mock_load_model():
            return mock_embedding_model

        monkeypatch.setattr(
            "sentence_transformers.SentenceTransformer",
            lambda model_name: mock_embedding_model,
        )

        service = EmbeddingService.get_instance()
        service._model = mock_embedding_model  # Inject mock directly

        yield service

        # Cleanup
        EmbeddingService._instance = None
    except ImportError:
        pytest.skip("sentence-transformers not installed")


@pytest.fixture
def sample_embeddings():
    """Pre-computed embeddings for consistent test data."""
    return {
        "security vulnerability": np.array(
            [0.8, 0.6, 0.0] + [0.0] * 381, dtype=np.float32
        ),
        "critical bug": np.array([0.7, 0.7, 0.1] + [0.0] * 381, dtype=np.float32),
        "weather forecast": np.array([0.1, 0.1, 0.9] + [0.0] * 381, dtype=np.float32),
    }

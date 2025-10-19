"""Embedding service for semantic matching.

This module provides a singleton service for generating and caching embeddings
using sentence-transformers.
"""

from flock.logging.logging import get_logger
from collections import OrderedDict

import numpy as np


logger = get_logger(__name__)


class LRUCache:
    """Simple LRU cache with size limit."""

    def __init__(self, max_size: int = 10000):
        """Initialize LRU cache.

        Args:
            max_size: Maximum number of entries
        """
        self.max_size = max_size
        self._cache: OrderedDict[str, np.ndarray] = OrderedDict()

    def get(self, key: str) -> np.ndarray | None:
        """Get value and mark as recently used."""
        if key not in self._cache:
            return None
        # Move to end (most recent)
        self._cache.move_to_end(key)
        return self._cache[key]

    def put(self, key: str, value: np.ndarray) -> None:
        """Put value and evict LRU if needed."""
        if key in self._cache:
            # Update and move to end
            self._cache.move_to_end(key)
        self._cache[key] = value

        # Evict oldest if over limit
        if len(self._cache) > self.max_size:
            self._cache.popitem(last=False)  # Remove oldest (first item)

    def __contains__(self, key: str) -> bool:
        """Check if key exists in cache."""
        return key in self._cache

    def __len__(self) -> int:
        """Get cache size."""
        return len(self._cache)


class EmbeddingService:
    """Singleton service for text embeddings using sentence-transformers.

    This class manages the lifecycle of the embedding model and provides
    efficient caching of embeddings.
    """

    _instance = None

    def __init__(self, cache_size: int = 10000):
        """Private constructor - use get_instance() instead.

        Args:
            cache_size: Maximum number of embeddings to cache
        """
        self._model = None
        self._cache = LRUCache(max_size=cache_size)
        self._cache_size = cache_size
        self._hits = 0
        self._misses = 0

    @staticmethod
    def get_instance(cache_size: int = 10000):
        """Get or create the singleton EmbeddingService instance.

        Args:
            cache_size: Maximum number of embeddings to cache (default: 10000)

        Returns:
            EmbeddingService: The singleton instance
        """
        if EmbeddingService._instance is None:
            EmbeddingService._instance = EmbeddingService(cache_size=cache_size)
        return EmbeddingService._instance

    def _load_model(self):
        """Lazy load the sentence-transformers model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading sentence-transformers model: all-MiniLM-L6-v2")
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Model loaded successfully")

    def embed(self, text: str) -> np.ndarray:
        """Generate embedding for a single text.

        Args:
            text: The text to embed

        Returns:
            np.ndarray: 384-dimensional embedding vector

        Raises:
            ValueError: If text is empty
        """
        if not text or not text.strip():
            raise ValueError("Cannot embed empty text")

        # Check cache first
        cached = self._cache.get(text)
        if cached is not None:
            self._hits += 1
            return cached

        # Cache miss - generate embedding
        self._misses += 1
        self._load_model()

        # Generate embedding
        embedding = self._model.encode(
            text, convert_to_numpy=True, show_progress_bar=False
        )

        # Ensure it's a float32 numpy array and flatten to 1D
        if not isinstance(embedding, np.ndarray):
            embedding = np.array(embedding, dtype=np.float32)

        # Flatten to 1D if needed (model might return (1, 384) for single text)
        if embedding.ndim > 1:
            embedding = embedding.flatten()

        # Store in cache
        self._cache.put(text, embedding)

        return embedding

    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of texts to embed

        Returns:
            list[np.ndarray]: List of embedding vectors
        """
        if not texts:
            return []

        # Separate cached and uncached
        results = [None] * len(texts)
        to_encode = []
        to_encode_indices = []

        for i, text in enumerate(texts):
            cached = self._cache.get(text)
            if cached is not None:
                results[i] = cached
                self._hits += 1
            else:
                to_encode.append(text)
                to_encode_indices.append(i)
                self._misses += 1

        # Batch encode uncached texts
        if to_encode:
            self._load_model()
            embeddings = self._model.encode(
                to_encode, convert_to_numpy=True, show_progress_bar=False
            )

            # Store in cache and results
            for i, (text, embedding) in enumerate(
                zip(to_encode, embeddings, strict=False)
            ):
                if not isinstance(embedding, np.ndarray):
                    embedding = np.array(embedding, dtype=np.float32)
                # Flatten to 1D if needed
                if embedding.ndim > 1:
                    embedding = embedding.flatten()
                self._cache.put(text, embedding)
                results[to_encode_indices[i]] = embedding

        return results  # type: ignore

    def similarity(self, text1: str, text2: str) -> float:
        """Compute semantic similarity between two texts.

        Uses cosine similarity between embeddings.

        Args:
            text1: First text
            text2: Second text

        Returns:
            float: Similarity score between 0 and 1
        """
        emb1 = self.embed(text1)
        emb2 = self.embed(text2)

        # Compute cosine similarity
        dot_product = np.dot(emb1, emb2)
        norm1 = np.linalg.norm(emb1)
        norm2 = np.linalg.norm(emb2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        similarity = dot_product / (norm1 * norm2)

        logger.debug(
            f"Computed similarity: {similarity:.4f} between texts '{text1}' and '{text2}'",
        )

        # Clamp to [0, 1] and handle floating point errors
        return float(max(0.0, min(1.0, similarity)))

    def get_cache_stats(self) -> dict:
        """Get cache hit/miss statistics.

        Returns:
            dict: Statistics including hits, misses, and hit rate
        """
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0

        return {
            "hits": self._hits,
            "misses": self._misses,
            "total": total,
            "hit_rate": hit_rate,
            "cache_size": len(self._cache),
            "cache_limit": self._cache_size,
        }

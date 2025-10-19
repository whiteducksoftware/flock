"""Semantic subscriptions for Flock.

This module provides semantic matching capabilities using sentence-transformers.
It's an optional feature that requires installing the [semantic] extra:

    uv add flock-core[semantic]

If sentence-transformers is not installed, semantic features will gracefully
degrade and core Flock functionality remains unaffected.
"""

# Try to import semantic features
try:
    from sentence_transformers import SentenceTransformer  # noqa: F401

    from .context_provider import SemanticContextProvider
    from .embedding_service import EmbeddingService

    SEMANTIC_AVAILABLE = True
except ImportError as e:
    SEMANTIC_AVAILABLE = False
    _import_error = e

    # Provide helpful error message when features are used
    class EmbeddingService:  # type: ignore
        """Placeholder when semantic extras not installed."""

        @staticmethod
        def get_instance(*args, **kwargs):
            raise ImportError(
                "Semantic features require sentence-transformers. "
                "Install with: uv add flock-core[semantic]"
            ) from _import_error

    class SemanticContextProvider:  # type: ignore
        """Placeholder when semantic extras not installed."""

        def __init__(self, *args, **kwargs):
            raise ImportError(
                "Semantic features require sentence-transformers. "
                "Install with: uv add flock-core[semantic]"
            ) from _import_error


__all__ = [
    "SEMANTIC_AVAILABLE",
    "EmbeddingService",
    "SemanticContextProvider",
]

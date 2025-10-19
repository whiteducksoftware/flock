"""Tests for optional semantic dependency handling."""

import pytest


def test_embedding_service_imports_when_available():
    """EmbeddingService should import when sentence-transformers installed."""
    try:
        from flock.semantic import EmbeddingService

        # If we get here, import succeeded
        assert EmbeddingService is not None
    except ImportError as e:
        # If sentence-transformers not installed, should have clear message
        assert "sentence-transformers" in str(e) or "semantic" in str(e)


def test_embedding_service_raises_clear_error_when_missing():
    """Should raise ImportError with helpful message about [semantic] extra."""
    # Test the placeholder EmbeddingService that's created when library is missing
    # We test the actual error message users will see
    from flock.semantic import SEMANTIC_AVAILABLE

    if not SEMANTIC_AVAILABLE:
        # If semantic features not available, test the error message
        from flock.semantic import EmbeddingService

        with pytest.raises(ImportError) as exc_info:
            EmbeddingService.get_instance()

        # Should have helpful error message
        error_msg = str(exc_info.value).lower()
        assert "semantic" in error_msg or "sentence-transformers" in error_msg
    else:
        # If library is installed, just verify import works
        from flock.semantic import EmbeddingService

        assert EmbeddingService is not None


def test_graceful_degradation_without_semantic():
    """Core Flock features work without semantic extras installed."""
    # This test verifies that basic Flock functionality is unaffected
    # even if semantic features are unavailable

    from pydantic import BaseModel

    from flock import Flock, flock_type

    # Should be able to create Flock and define agents
    flock = Flock()

    @flock_type
    class TestArtifact(BaseModel):
        data: str

    # Basic subscription without semantic features should work
    test_agent = flock.agent("test_agent").consumes(TestArtifact)

    # No errors should occur during setup
    assert len(flock.agents) == 1
    assert flock.agents[0].name == "test_agent"
    assert test_agent is not None

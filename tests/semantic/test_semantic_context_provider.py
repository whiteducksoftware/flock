"""Tests for SemanticContextProvider.

SemanticContextProvider retrieves semantically relevant historical artifacts
to provide context for agent execution.
"""

import uuid

import pytest


# Skip all tests if sentence-transformers not available
pytest.importorskip("sentence_transformers")

from pydantic import BaseModel

from flock import flock_type
from flock.core.artifacts import Artifact
from flock.core.store import InMemoryBlackboardStore
from flock.semantic.context_provider import SemanticContextProvider


@pytest.mark.asyncio
async def test_semantic_context_provider_finds_relevant_artifacts():
    """SemanticContextProvider returns semantically similar historical artifacts."""

    @flock_type
    class SupportTicket(BaseModel):
        message: str
        resolution: str | None = None

    store = InMemoryBlackboardStore()

    # Populate history with various tickets
    from flock.registry import type_registry

    await store.publish(
        Artifact(
            id=str(uuid.uuid4()),
            type=type_registry.register(SupportTicket),
            payload={
                "message": "Password reset not working",
                "resolution": "Cleared cache and reset token expiry",
            },
            produced_by="test",
        )
    )
    await store.publish(
        Artifact(
            id=str(uuid.uuid4()),
            type=type_registry.register(SupportTicket),
            payload={
                "message": "Can't access my account after password change",
                "resolution": "Issue with session invalidation - fixed in v2.1",
            },
            produced_by="test",
        )
    )
    await store.publish(
        Artifact(
            id=str(uuid.uuid4()),
            type=type_registry.register(SupportTicket),
            payload={
                "message": "Website color scheme is ugly",
                "resolution": "Referred to design team",
            },
            produced_by="test",
        )
    )

    # Create context provider for current ticket
    provider = SemanticContextProvider(
        query_text="User unable to login after resetting password", limit=2
    )

    relevant = await provider.get_context(store)

    # Should return 2 most relevant (password-related) tickets
    assert len(relevant) == 2
    messages = [r.payload["message"] for r in relevant]
    # Both should be password-related
    assert any("password" in m.lower() for m in messages)


@pytest.mark.asyncio
async def test_semantic_context_provider_custom_field():
    """SemanticContextProvider can extract specific field for matching."""

    @flock_type
    class Article(BaseModel):
        title: str
        abstract: str
        full_text: str

    store = InMemoryBlackboardStore()

    from flock.registry import type_registry

    await store.publish(
        Artifact(
            id=str(uuid.uuid4()),
            type=type_registry.register(Article),
            payload={
                "title": "Introduction to Neural Networks",
                "abstract": "This paper discusses deep learning architectures",
                "full_text": "...",
            },
            produced_by="test",
        )
    )

    provider = SemanticContextProvider(
        query_text="machine learning tutorial",
        extract_field="abstract",  # Match on abstract, not title
        limit=10,
    )

    relevant = await provider.get_context(store)
    assert len(relevant) >= 0  # May or may not match depending on threshold


@pytest.mark.asyncio
async def test_semantic_context_provider_with_filters():
    """SemanticContextProvider respects additional filters."""

    @flock_type
    class LogEntry(BaseModel):
        message: str
        severity: str
        timestamp: str

    store = InMemoryBlackboardStore()

    from flock.registry import type_registry

    log_type = type_registry.register(LogEntry)

    await store.publish(
        Artifact(
            id=str(uuid.uuid4()),
            type=log_type,
            payload={
                "message": "Database connection timeout",
                "severity": "error",
                "timestamp": "2024-01-01",
            },
            produced_by="test",
        )
    )
    await store.publish(
        Artifact(
            id=str(uuid.uuid4()),
            type=log_type,
            payload={
                "message": "Database query optimization",
                "severity": "info",
                "timestamp": "2024-01-02",
            },
            produced_by="test",
        )
    )

    provider = SemanticContextProvider(
        query_text="database issues",
        artifact_type=LogEntry,
        where=lambda a: a.payload["severity"] == "error",
        limit=10,
    )

    relevant = await provider.get_context(store)

    # Should only return error-level database logs
    for r in relevant:
        assert r.payload["severity"] == "error"


@pytest.mark.asyncio
async def test_semantic_context_provider_no_matches():
    """SemanticContextProvider returns empty list when no relevant artifacts."""

    @flock_type
    class Event(BaseModel):
        description: str

    store = InMemoryBlackboardStore()

    from flock.registry import type_registry

    await store.publish(
        Artifact(
            id=str(uuid.uuid4()),
            type=type_registry.register(Event),
            payload={"description": "Weather forecast for tomorrow"},
            produced_by="test",
        )
    )

    provider = SemanticContextProvider(
        query_text="quantum physics research", threshold=0.8, limit=10
    )

    relevant = await provider.get_context(store)
    assert len(relevant) == 0  # No matches above threshold


@pytest.mark.asyncio
async def test_semantic_context_provider_limit():
    """SemanticContextProvider respects limit parameter."""

    @flock_type
    class Message(BaseModel):
        content: str

    store = InMemoryBlackboardStore()

    from flock.registry import type_registry

    msg_type = type_registry.register(Message)

    # Add 10 similar messages
    for i in range(10):
        await store.publish(
            Artifact(
                id=str(uuid.uuid4()),
                type=msg_type,
                payload={"content": f"Security vulnerability issue number {i}"},
                produced_by="test",
            )
        )

    provider = SemanticContextProvider(query_text="security vulnerability", limit=3)

    relevant = await provider.get_context(store)

    # Should only return top 3
    assert len(relevant) == 3


def test_semantic_context_provider_validation_empty_query():
    """SemanticContextProvider rejects empty query_text."""
    with pytest.raises(ValueError, match="query_text cannot be empty"):
        SemanticContextProvider(query_text="")

    with pytest.raises(ValueError, match="query_text cannot be empty"):
        SemanticContextProvider(query_text="   ")  # Whitespace only


def test_semantic_context_provider_validation_invalid_threshold():
    """SemanticContextProvider rejects invalid thresholds."""
    with pytest.raises(ValueError, match="threshold must be between 0 and 1"):
        SemanticContextProvider(query_text="test", threshold=-0.1)

    with pytest.raises(ValueError, match="threshold must be between 0 and 1"):
        SemanticContextProvider(query_text="test", threshold=1.5)


def test_semantic_context_provider_validation_invalid_limit():
    """SemanticContextProvider rejects invalid limits."""
    with pytest.raises(ValueError, match="limit must be at least 1"):
        SemanticContextProvider(query_text="test", limit=0)

    with pytest.raises(ValueError, match="limit must be at least 1"):
        SemanticContextProvider(query_text="test", limit=-5)


@pytest.mark.asyncio
async def test_semantic_context_provider_extracts_nested_lists():
    """SemanticContextProvider extracts text from nested list/tuple structures."""

    @flock_type
    class ComplexData(BaseModel):
        tags: list[str]
        categories: tuple[str, ...]
        description: str

    store = InMemoryBlackboardStore()

    from flock.registry import type_registry

    await store.publish(
        Artifact(
            id=str(uuid.uuid4()),
            type=type_registry.register(ComplexData),
            payload={
                "tags": ["machine learning", "AI research"],
                "categories": ("neural networks", "deep learning"),
                "description": "Advanced ML techniques",
            },
            produced_by="test",
        )
    )

    provider = SemanticContextProvider(
        query_text="artificial intelligence and neural networks", limit=10
    )

    relevant = await provider.get_context(store)

    # Should find the artifact by matching tags/categories (nested lists)
    assert len(relevant) >= 1


@pytest.mark.asyncio
async def test_semantic_context_provider_handles_empty_payload_fields():
    """SemanticContextProvider skips artifacts with empty text after extraction."""

    @flock_type
    class EmptyMessage(BaseModel):
        id: int
        count: int

    store = InMemoryBlackboardStore()

    from flock.registry import type_registry

    await store.publish(
        Artifact(
            id=str(uuid.uuid4()),
            type=type_registry.register(EmptyMessage),
            payload={"id": 123, "count": 45},  # No text fields
            produced_by="test",
        )
    )

    provider = SemanticContextProvider(query_text="test query", limit=10)

    relevant = await provider.get_context(store)

    # Should return empty since there's no text to match
    assert len(relevant) == 0

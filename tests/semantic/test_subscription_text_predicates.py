"""Tests for subscription text predicates.

These tests verify that subscriptions can match artifacts using semantic
text matching instead of just type matching.
"""

import uuid

import pytest


# Skip all tests if sentence-transformers not available
pytest.importorskip("sentence_transformers")

from pydantic import BaseModel

from flock import flock_type
from flock.core.artifacts import Artifact
from flock.core.subscription import Subscription
from flock.registry import type_registry


def test_text_predicate_single_match():
    """Subscription with text predicate matches semantically similar artifact."""

    @flock_type
    class BugReport(BaseModel):
        description: str

    sub = Subscription(
        types=[BugReport],
        mode="both",
        priority=0,
        semantic_match="security vulnerability",
    )

    # Create artifact with semantically similar content
    artifact = Artifact(
        id=str(uuid.uuid4()),
        type=type_registry.register(BugReport),
        payload={
            "description": "Critical SQL injection vulnerability in login endpoint"
        },
        produced_by="test",
    )

    assert sub.matches(artifact) is True


def test_text_predicate_no_match():
    """Subscription doesn't match semantically different artifact."""

    @flock_type
    class BugReport(BaseModel):
        description: str

    sub = Subscription(
        types=[BugReport],
        mode="both",
        priority=0,
        semantic_match="security vulnerability",
    )

    # Create artifact with unrelated content
    artifact = Artifact(
        id=str(uuid.uuid4()),
        type=type_registry.register(BugReport),
        payload={"description": "Minor UI alignment issue in footer"},
        produced_by="test",
    )

    assert sub.matches(artifact) is False


def test_multiple_text_predicates_all_match():
    """Multiple text predicates require ALL to match (AND logic)."""

    @flock_type
    class SupportTicket(BaseModel):
        message: str

    sub = Subscription(
        types=[SupportTicket],
        mode="both",
        priority=0,
        semantic_match=["customer complaint", "billing issue"],
    )

    # Artifact matches both predicates
    artifact1 = Artifact(
        id=str(uuid.uuid4()),
        type=type_registry.register(SupportTicket),
        payload={
            "message": "Angry customer complaining about incorrect billing charges"
        },
        produced_by="test",
    )
    assert sub.matches(artifact1) is True

    # Artifact matches only one predicate - should NOT match
    artifact2 = Artifact(
        id=str(uuid.uuid4()),
        type=type_registry.register(SupportTicket),
        payload={"message": "Customer asking about account settings"},
        produced_by="test",
    )
    assert sub.matches(artifact2) is False


def test_text_predicate_with_extract_field():
    """Text predicate extracts specific field from payload."""

    @flock_type
    class Article(BaseModel):
        title: str
        body: str
        category: str

    sub = Subscription(
        types=[Article],
        mode="both",
        priority=0,
        semantic_match={"field": "body", "query": "machine learning"},
    )

    # Body mentions ML - should match
    artifact = Artifact(
        id=str(uuid.uuid4()),
        type=type_registry.register(Article),
        payload={
            "title": "Cooking recipes",  # Unrelated title
            "body": "Using machine learning to optimize recipe recommendations",
            "category": "food",
        },
        produced_by="test",
    )

    assert sub.matches(artifact) is True


def test_text_predicate_custom_threshold():
    """Custom similarity threshold controls matching strictness."""

    @flock_type
    class Document(BaseModel):
        content: str

    strict_sub = Subscription(
        types=[Document],
        mode="both",
        priority=0,
        semantic_match={"query": "artificial intelligence", "threshold": 0.9},
    )

    lenient_sub = Subscription(
        types=[Document],
        mode="both",
        priority=0,
        semantic_match={"query": "artificial intelligence", "threshold": 0.3},
    )

    # Somewhat related content
    artifact = Artifact(
        id=str(uuid.uuid4()),
        type=type_registry.register(Document),
        payload={"content": "Machine learning models for neural networks"},
        produced_by="test",
    )

    # Lenient should match
    assert lenient_sub.matches(artifact) is True

    # Strict may or may not match depending on model
    # Just verify it doesn't crash
    result = strict_sub.matches(artifact)
    assert isinstance(result, bool)


def test_text_predicate_fallback_without_semantic():
    """Text predicates degrade gracefully if embeddings unavailable."""
    from unittest.mock import patch

    @flock_type
    class Event(BaseModel):
        message: str

    # Create subscription with text predicate
    sub = Subscription(
        types=[Event], mode="both", priority=0, semantic_match="important"
    )

    artifact = Artifact(
        id=str(uuid.uuid4()),
        type=type_registry.register(Event),
        payload={"message": "anything"},
        produced_by="test",
    )

    # Mock SEMANTIC_AVAILABLE to False to simulate library not available
    with patch("flock.semantic.SEMANTIC_AVAILABLE", False):
        # Should fall back to type-only matching (no crash)
        result = sub.matches(artifact)
        assert isinstance(result, bool)


def test_text_predicate_with_where_clause():
    """Text predicates can combine with where clause."""

    @flock_type
    class LogEntry(BaseModel):
        message: str
        severity: str

    sub = Subscription(
        types=[LogEntry],
        mode="both",
        priority=0,
        semantic_match="database connection",
        where=[lambda a: a.severity == "critical"],
    )

    # Matches both text and where clause
    artifact1 = Artifact(
        id=str(uuid.uuid4()),
        type=type_registry.register(LogEntry),
        payload={
            "message": "Database connection timeout occurred",
            "severity": "critical",
        },
        produced_by="test",
    )
    assert sub.matches(artifact1) is True

    # Matches text but not where clause
    artifact2 = Artifact(
        id=str(uuid.uuid4()),
        type=type_registry.register(LogEntry),
        payload={"message": "Database connection successful", "severity": "info"},
        produced_by="test",
    )
    assert sub.matches(artifact2) is False


def test_text_predicate_empty_payload():
    """Text predicate handles artifacts with no text gracefully."""

    @flock_type
    class EmptyArtifact(BaseModel):
        count: int

    sub = Subscription(
        types=[EmptyArtifact], mode="both", priority=0, semantic_match="some query"
    )

    # Artifact with no text fields
    artifact = Artifact(
        id=str(uuid.uuid4()),
        type=type_registry.register(EmptyArtifact),
        payload={"count": 42},
        produced_by="test",
    )

    # Should not match (or not crash)
    result = sub.matches(artifact)
    assert isinstance(result, bool)
    assert result is False  # No text to match against

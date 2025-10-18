"""Tests for subscription matching logic."""

import pytest
from pydantic import BaseModel, Field

from flock.core.artifacts import Artifact
from flock.core.subscription import Subscription
from flock.core.visibility import PublicVisibility
from flock.registry import flock_type


# Test artifact types - use explicit names to avoid module path issues
@flock_type(name="Movie")
class Movie(BaseModel):
    title: str = Field(description="Movie title")
    runtime: int = Field(description="Runtime in minutes")


@flock_type(name="Idea")
class Idea(BaseModel):
    topic: str = Field(description="Topic")


@pytest.mark.asyncio
async def test_subscription_matches_correct_type():
    """Test that subscription matches the correct artifact type."""
    # Arrange
    subscription = Subscription(agent_name="test_agent", types=[Movie])
    artifact = Artifact(
        type="Movie",
        payload={"title": "TEST MOVIE", "runtime": 120},
        produced_by="test_agent",
        visibility=PublicVisibility(),
    )

    # Act
    result = subscription.matches(artifact)

    # Assert
    assert result is True


@pytest.mark.asyncio
async def test_subscription_rejects_wrong_type():
    """Test that subscription rejects artifacts of wrong type."""
    # Arrange
    subscription = Subscription(agent_name="test_agent", types=[Movie])
    artifact = Artifact(
        type="Idea",
        payload={"topic": "test"},
        produced_by="test_agent",
        visibility=PublicVisibility(),
    )

    # Act
    result = subscription.matches(artifact)

    # Assert
    assert result is False


@pytest.mark.asyncio
async def test_subscription_matches_from_agents():
    """Test that subscription matches artifacts from specific agents."""
    # Arrange
    subscription = Subscription(
        agent_name="test_agent", types=[Movie], from_agents={"movie_agent"}
    )
    artifact = Artifact(
        type="Movie",
        payload={"title": "TEST", "runtime": 120},
        produced_by="movie_agent",
        visibility=PublicVisibility(),
    )

    # Act
    result = subscription.matches(artifact)

    # Assert
    assert result is True


@pytest.mark.asyncio
async def test_subscription_rejects_wrong_producer():
    """Test that subscription rejects artifacts from non-matching agents."""
    # Arrange
    subscription = Subscription(
        agent_name="test_agent", types=[Movie], from_agents={"movie_agent"}
    )
    artifact = Artifact(
        type="Movie",
        payload={"title": "TEST", "runtime": 120},
        produced_by="other_agent",
        visibility=PublicVisibility(),
    )

    # Act
    result = subscription.matches(artifact)

    # Assert
    assert result is False


@pytest.mark.asyncio
async def test_subscription_matches_with_predicate():
    """Test that subscription matches artifacts satisfying predicate."""
    # Arrange
    subscription = Subscription(
        agent_name="test_agent", types=[Movie], where=[lambda m: m.runtime > 120]
    )
    artifact = Artifact(
        type="Movie",
        payload={"title": "TEST", "runtime": 150},
        produced_by="test_agent",
        visibility=PublicVisibility(),
    )

    # Act
    result = subscription.matches(artifact)

    # Assert
    assert result is True


@pytest.mark.asyncio
async def test_subscription_rejects_failing_predicate():
    """Test that subscription rejects artifacts failing predicate."""
    # Arrange
    subscription = Subscription(
        agent_name="test_agent", types=[Movie], where=[lambda m: m.runtime > 120]
    )
    artifact = Artifact(
        type="Movie",
        payload={"title": "TEST", "runtime": 90},
        produced_by="test_agent",
        visibility=PublicVisibility(),
    )

    # Act
    result = subscription.matches(artifact)

    # Assert
    assert result is False


@pytest.mark.asyncio
async def test_subscription_matches_multiple_predicates():
    """Test that subscription matches artifacts satisfying all predicates (AND logic)."""
    # Arrange
    subscription = Subscription(
        agent_name="test_agent",
        types=[Movie],
        where=[lambda m: m.runtime > 120, lambda m: "ACTION" in m.title],
    )
    artifact = Artifact(
        type="Movie",
        payload={"title": "ACTION MOVIE", "runtime": 150},
        produced_by="test_agent",
        visibility=PublicVisibility(),
    )

    # Act
    result = subscription.matches(artifact)

    # Assert
    assert result is True


@pytest.mark.asyncio
async def test_subscription_matches_channel():
    """Test that subscription matches artifacts with intersecting tags."""
    # Arrange
    subscription = Subscription(agent_name="test_agent", types=[Movie], tags={"sci-fi"})
    artifact = Artifact(
        type="Movie",
        payload={"title": "TEST", "runtime": 120},
        produced_by="test_agent",
        visibility=PublicVisibility(),
        tags={"sci-fi", "action"},
    )

    # Act
    result = subscription.matches(artifact)

    # Assert
    assert result is True


# T055: Subscription Validation
def test_subscription_requires_at_least_one_type():
    """Test that Subscription raises ValueError when no types provided."""
    # Act & Assert
    with pytest.raises(ValueError, match="must declare at least one type"):
        Subscription(agent_name="test_agent", types=[])


# T056: Subscription Mode Filtering
def test_subscription_accepts_direct_mode():
    """Test subscription.accepts_direct() returns True for direct and both modes."""
    # Arrange & Act & Assert
    sub_direct = Subscription(agent_name="test", types=[Movie], mode="direct")
    assert sub_direct.accepts_direct() is True
    assert sub_direct.accepts_events() is False

    sub_both = Subscription(agent_name="test", types=[Movie], mode="both")
    assert sub_both.accepts_direct() is True
    assert sub_both.accepts_events() is True

    sub_events = Subscription(agent_name="test", types=[Movie], mode="events")
    assert sub_events.accepts_direct() is False
    assert sub_events.accepts_events() is True


# T057: Subscription Predicate Exception Handling
@pytest.mark.asyncio
async def test_subscription_predicate_exception_returns_false():
    """Test that subscription returns False when predicate raises exception."""

    # Arrange
    def bad_predicate(movie):
        raise AttributeError("Intentional error")

    subscription = Subscription(
        agent_name="test_agent", types=[Movie], where=[bad_predicate]
    )

    artifact = Artifact(
        type="Movie",
        payload={"title": "TEST", "runtime": 120},
        produced_by="test",
        visibility=PublicVisibility(),
    )

    # Act
    result = subscription.matches(artifact)

    # Assert - Should return False instead of propagating exception
    assert result is False


@pytest.mark.asyncio
async def test_subscription_predicate_missing_field_returns_false():
    """Test predicate accessing missing field returns False."""
    # Arrange
    subscription = Subscription(
        agent_name="test_agent",
        types=[Movie],
        where=[lambda m: m.nonexistent_field > 100],  # Will raise AttributeError
    )

    artifact = Artifact(
        type="Movie",
        payload={"title": "TEST", "runtime": 120},
        produced_by="test",
        visibility=PublicVisibility(),
    )

    # Act
    result = subscription.matches(artifact)

    # Assert
    assert result is False

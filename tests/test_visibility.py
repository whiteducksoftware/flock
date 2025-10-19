"""Tests for visibility enforcement."""

from datetime import UTC, timedelta

import pytest

from flock.agent import AgentIdentity
from flock.core.visibility import (
    AfterVisibility,
    LabelledVisibility,
    PrivateVisibility,
    PublicVisibility,
    TenantVisibility,
)


@pytest.mark.asyncio
async def test_public_visibility_allows_all_agents():
    """Test that PublicVisibility allows all agents."""
    # Arrange
    visibility = PublicVisibility()
    identity1 = AgentIdentity(name="agent1")
    identity2 = AgentIdentity(name="agent2")

    # Act & Assert
    assert visibility.allows(identity1) is True
    assert visibility.allows(identity2) is True


@pytest.mark.asyncio
async def test_private_visibility_allows_listed_agent():
    """Test that PrivateVisibility allows agents in allowlist."""
    # Arrange
    visibility = PrivateVisibility(agents={"agent_a", "agent_b"})
    identity = AgentIdentity(name="agent_a")

    # Act
    result = visibility.allows(identity)

    # Assert
    assert result is True


@pytest.mark.asyncio
async def test_private_visibility_denies_unlisted_agent():
    """Test that PrivateVisibility denies agents not in allowlist."""
    # Arrange
    visibility = PrivateVisibility(agents={"agent_a"})
    identity = AgentIdentity(name="agent_c")

    # Act
    result = visibility.allows(identity)

    # Assert
    assert result is False


@pytest.mark.asyncio
async def test_labelled_visibility_allows_agent_with_required_labels():
    """Test that LabelledVisibility allows agents with required labels."""
    # Arrange
    visibility = LabelledVisibility(required_labels={"clearance:secret"})
    identity = AgentIdentity(
        name="agent", labels={"clearance:secret", "department:finance"}
    )

    # Act
    result = visibility.allows(identity)

    # Assert
    assert result is True


@pytest.mark.asyncio
async def test_labelled_visibility_denies_agent_without_required_labels():
    """Test that LabelledVisibility denies agents without required labels."""
    # Arrange
    visibility = LabelledVisibility(required_labels={"clearance:secret"})
    identity = AgentIdentity(name="agent", labels={"clearance:public"})

    # Act
    result = visibility.allows(identity)

    # Assert
    assert result is False


@pytest.mark.asyncio
async def test_tenant_visibility_allows_same_tenant():
    """Test that TenantVisibility allows agents from same tenant."""
    # Arrange
    visibility = TenantVisibility(tenant_id="tenant_a")
    identity = AgentIdentity(name="agent", tenant_id="tenant_a")

    # Act
    result = visibility.allows(identity)

    # Assert
    assert result is True


@pytest.mark.asyncio
async def test_tenant_visibility_denies_different_tenant():
    """Test that TenantVisibility denies agents from different tenant."""
    # Arrange
    visibility = TenantVisibility(tenant_id="tenant_a")
    identity = AgentIdentity(name="agent", tenant_id="tenant_b")

    # Act
    result = visibility.allows(identity)

    # Assert
    assert result is False


@pytest.mark.asyncio
async def test_after_visibility_denies_before_ttl():
    """Test that AfterVisibility denies access before TTL expires."""
    # Arrange
    from datetime import datetime

    # Create visibility with TTL
    visibility = AfterVisibility(ttl=timedelta(hours=24))

    # Set the private _created_at to 1 hour ago
    visibility._created_at = datetime(2025, 9, 30, 11, 0, 0, tzinfo=UTC)

    identity = AgentIdentity(name="agent")

    # Current time is 1 hour after creation
    current_time = datetime(2025, 9, 30, 12, 0, 0, tzinfo=UTC)

    # Act
    result = visibility.allows(identity, now=current_time)

    # Assert
    assert result is False  # TTL not expired yet


@pytest.mark.asyncio
async def test_after_visibility_allows_after_ttl():
    """Test that AfterVisibility allows access after TTL expires."""
    # Arrange
    from datetime import datetime

    # Create visibility with TTL
    visibility = AfterVisibility(ttl=timedelta(hours=24))

    # Set the private _created_at to 25 hours ago
    visibility._created_at = datetime(2025, 9, 29, 11, 0, 0, tzinfo=UTC)

    identity = AgentIdentity(name="agent")

    # Current time is 25 hours after creation
    current_time = datetime(2025, 9, 30, 12, 0, 0, tzinfo=UTC)

    # Act
    result = visibility.allows(identity, now=current_time)

    # Assert
    assert result is True  # TTL expired


# T058: TenantVisibility with None
@pytest.mark.asyncio
async def test_tenant_visibility_with_none_allows_all():
    """Test that TenantVisibility with tenant_id=None allows all agents."""
    # Arrange
    visibility = TenantVisibility(tenant_id=None)
    identity_a = AgentIdentity(name="agent_a", tenant_id="tenant_a")
    identity_b = AgentIdentity(name="agent_b", tenant_id="tenant_b")
    identity_no_tenant = AgentIdentity(name="agent_c", tenant_id=None)

    # Act & Assert - All should be allowed when tenant_id is None
    assert visibility.allows(identity_a) is True
    assert visibility.allows(identity_b) is True
    assert visibility.allows(identity_no_tenant) is True


# T059: AfterVisibility Then Clause Delegation
@pytest.mark.asyncio
async def test_after_visibility_then_clause_allows_listed_agent(fixed_time, mocker):
    """Test AfterVisibility delegates to 'then' clause after TTL expires."""
    # Arrange
    then_clause = PrivateVisibility(agents={"agent_a"})
    visibility = AfterVisibility(ttl=timedelta(hours=1), then=then_clause)

    identity_a = AgentIdentity(name="agent_a")
    identity_b = AgentIdentity(name="agent_b")

    # Mock time to be 2 hours after creation (past TTL)
    future_time = fixed_time + timedelta(hours=2)

    # Act
    result_a = visibility.allows(identity_a, now=future_time)
    result_b = visibility.allows(identity_b, now=future_time)

    # Assert - Should delegate to then clause (PrivateVisibility)
    assert result_a is True  # agent_a is in allowlist
    assert result_b is False  # agent_b is NOT in allowlist


@pytest.mark.asyncio
async def test_after_visibility_then_clause_none_allows_all(fixed_time):
    """Test AfterVisibility without 'then' clause allows all after TTL."""
    # Arrange
    visibility = AfterVisibility(ttl=timedelta(hours=1), then=None)
    identity = AgentIdentity(name="any_agent")

    # Mock time to be after TTL
    future_time = fixed_time + timedelta(hours=2)

    # Act
    result = visibility.allows(identity, now=future_time)

    # Assert
    assert result is True

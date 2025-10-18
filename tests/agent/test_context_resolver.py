"""Tests for agent context resolution."""

from unittest.mock import Mock

import pytest

from flock.agent.context_resolver import ContextResolver
from flock.core.artifacts import Artifact
from flock.core.subscription import Subscription
from flock.utils.runtime import Context


@pytest.fixture
def resolver():
    """Create ContextResolver instance."""
    return ContextResolver(agent_name="test_agent")


@pytest.fixture
def mock_agent():
    """Create mock agent."""
    agent = Mock()
    agent.name = "test_agent"
    agent.context_provider = None
    return agent


@pytest.fixture
def mock_subscription():
    """Create mock subscription."""
    return Mock(spec=Subscription)


@pytest.fixture
def mock_provider():
    """Create mock context provider."""
    return Mock()


def test_get_provider_returns_agent_provider_when_set(
    resolver, mock_agent, mock_provider
):
    """Test that get_provider returns agent-specific provider first."""
    mock_agent.context_provider = mock_provider
    default_provider = Mock()

    result = resolver.get_provider(mock_agent, default_provider)

    assert result == mock_provider


def test_get_provider_returns_default_when_agent_has_none(
    resolver, mock_agent, mock_provider
):
    """Test that get_provider falls back to default provider."""
    mock_agent.context_provider = None

    result = resolver.get_provider(mock_agent, mock_provider)

    assert result == mock_provider


def test_get_provider_returns_none_when_both_none(resolver, mock_agent):
    """Test that get_provider returns None when no providers configured."""
    mock_agent.context_provider = None

    result = resolver.get_provider(mock_agent, None)

    assert result is None


def test_get_provider_prefers_agent_over_default(resolver, mock_agent):
    """Test that agent provider takes precedence over default."""
    agent_provider = Mock(name="agent_provider")
    default_provider = Mock(name="default_provider")
    mock_agent.context_provider = agent_provider

    result = resolver.get_provider(mock_agent, default_provider)

    # Agent provider should win
    assert result == agent_provider
    assert result != default_provider


@pytest.mark.asyncio
async def test_resolve_context_returns_basic_context(
    resolver, mock_agent, mock_subscription
):
    """Test that resolve_context returns a basic Context object."""
    trigger_artifacts = [
        Mock(spec=Artifact, id="art1"),
        Mock(spec=Artifact, id="art2"),
    ]

    context = await resolver.resolve_context(
        mock_agent, mock_subscription, trigger_artifacts, None
    )

    assert isinstance(context, Context)
    assert context.correlation_id is None
    assert context.task_id == ""
    assert context.state == {}
    assert context.is_batch is False
    assert context.artifacts == []
    assert context.agent_identity is None


@pytest.mark.asyncio
async def test_resolve_context_with_agent_provider(
    resolver, mock_agent, mock_subscription, mock_provider
):
    """Test that resolve_context uses agent provider when available."""
    mock_agent.context_provider = mock_provider
    trigger_artifacts = [Mock(spec=Artifact)]

    context = await resolver.resolve_context(
        mock_agent, mock_subscription, trigger_artifacts, None
    )

    # Currently returns basic context regardless of provider
    # (future implementation will use provider to fetch context artifacts)
    assert isinstance(context, Context)


@pytest.mark.asyncio
async def test_resolve_context_with_default_provider(
    resolver, mock_agent, mock_subscription, mock_provider
):
    """Test that resolve_context uses default provider when agent has none."""
    mock_agent.context_provider = None
    trigger_artifacts = [Mock(spec=Artifact)]

    context = await resolver.resolve_context(
        mock_agent, mock_subscription, trigger_artifacts, mock_provider
    )

    # Currently returns basic context
    assert isinstance(context, Context)


@pytest.mark.asyncio
async def test_resolve_context_with_no_provider(
    resolver, mock_agent, mock_subscription
):
    """Test that resolve_context works without any provider."""
    mock_agent.context_provider = None
    trigger_artifacts = [Mock(spec=Artifact)]

    context = await resolver.resolve_context(
        mock_agent, mock_subscription, trigger_artifacts, None
    )

    assert isinstance(context, Context)
    assert context.correlation_id is None
    assert context.task_id == ""


@pytest.mark.asyncio
async def test_resolve_context_with_empty_triggers(
    resolver, mock_agent, mock_subscription
):
    """Test that resolve_context works with empty trigger artifacts list."""
    trigger_artifacts = []

    context = await resolver.resolve_context(
        mock_agent, mock_subscription, trigger_artifacts, None
    )

    assert isinstance(context, Context)
    assert context.state == {}

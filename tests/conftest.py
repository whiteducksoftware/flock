# tests/conftest.py
import pytest
import asyncio
# Use AsyncMock for mocking async functions
from unittest.mock import MagicMock, AsyncMock

# --- Event Loop Policy ---
# Ensure the same event loop policy is used for all tests
# Necessary for some environments or if tests interfere with loop policies
@pytest.fixture(scope="session")
def event_loop_policy():
    # Use the default asyncio policy or uvloop if installed
    try:
        import uvloop
        policy = uvloop.EventLoopPolicy()
    except ImportError:
        policy = asyncio.DefaultEventLoopPolicy()
    return policy

# --- Basic Flock Fixtures (Placeholders) ---
@pytest.fixture
def mock_flock_instance():
    """Provides a basic, mocked Flock instance for unit tests."""
    # You might want to use MagicMock or create a minimal non-functional subclass
    mock_flock = MagicMock(name="MockFlock")
    mock_flock.model = "mock-model/test-v1"
    mock_flock.local_debug = True
    mock_flock.agents = {}
    mock_flock.registry = MagicMock(name="MockRegistry")
    mock_flock.context = MagicMock(name="MockContext")
    # Add mock methods as needed
    mock_flock.add_agent = MagicMock()
    mock_flock.add_tool = MagicMock()
    # Use AsyncMock for async methods
    mock_flock.run_async = AsyncMock(return_value={"result": "mocked"})
    return mock_flock

@pytest.fixture
def mock_flock_agent():
    """Provides a basic, mocked FlockAgent instance."""
    mock_agent = MagicMock(name="MockAgent")
    mock_agent.name = "mock_agent"
    mock_agent.model = "mock-model/test-v1"
    mock_agent.input = "query: str"
    mock_agent.output = "response: str"
    mock_agent.tools = []
    # Use AsyncMock for async methods
    mock_agent.evaluate = AsyncMock(return_value={"response": "mocked response"})
    mock_agent.run_async = AsyncMock(return_value={"response": "mocked response"})
    # Add other necessary attributes/methods
    return mock_agent

# --- Mocking Fixtures ---
@pytest.fixture
def mock_llm():
    """
    Provides a basic mock for LLM interactions (e.g., litellm.completion).
    Tests can configure its return value.
    """
    # This is a simple placeholder. You might make it more sophisticated later,
    # e.g., returning different responses based on the input prompt.
    mock = MagicMock(name="MockLLM")
    # This is the object that will be returned *after* awaiting the mock
    mock_completion_result = MagicMock()
    mock_completion_result.choices = [MagicMock(message=MagicMock(content='{"response": "mocked LLM output"}'))]

    # Use AsyncMock for the methods that need to be awaited
    mock.completion = AsyncMock(return_value=mock_completion_result)
    mock.acompletion = AsyncMock(return_value=mock_completion_result)
    return mock

@pytest.fixture(autouse=True) # Apply this mock to all tests automatically
def patch_litellm(mocker, mock_llm):
    """Automatically patch litellm.completion and acompletion for most tests."""
    # Use mocker fixture provided by pytest-mock
    mocker.patch("litellm.completion", mock_llm.completion)
    mocker.patch("litellm.acompletion", mock_llm.acompletion)
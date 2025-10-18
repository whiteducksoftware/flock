from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# Import framework classes
from flock.agent import AgentIdentity
from flock.core import Flock
from flock.core.artifacts import Artifact
from flock.core.store import InMemoryBlackboardStore
from flock.core.visibility import PublicVisibility
from flock.dashboard.collector import DashboardEventCollector


@pytest.fixture
def orchestrator():
    """Create clean orchestrator with in-memory store for each test.

    Note: DSPyEngine auto-detects pytest and disables streaming for clean test output.
    The default stream=False in tests is automatic - no manual configuration needed.
    """
    orch = Flock()
    # Disable console initialization to avoid Windows encoding issues with emojis in tests
    orch.is_dashboard = True  # Skips init_console() call in publish()
    return orch


@pytest.fixture
def sample_artifact():
    """Sample artifact for testing."""
    return Artifact(
        type="TestType",
        payload={"data": "test"},
        produced_by="test_agent",
        visibility=PublicVisibility(),
    )


@pytest.fixture
def sample_agent_identity():
    """Sample agent identity for testing."""
    return AgentIdentity(
        name="test_agent", labels={"test_label"}, tenant_id="test_tenant"
    )


@pytest.fixture(autouse=True)
def mock_llm(mocker):
    """Mock LLM API calls to avoid real requests.

    Each test gets a fresh mock to avoid state contamination.
    """

    async def mock_response(*args, **kwargs):
        return {"output": "mocked response"}

    # Mock DSPy Predict calls - use side_effect for async response
    mock_predict = mocker.patch("dspy.Predict.__call__", side_effect=mock_response)

    yield mock_response

    # Explicit cleanup to ensure mocks are reset
    mock_predict.reset_mock()


@pytest.fixture
def fixed_time(mocker):
    """Fix current time for deterministic tests."""
    fixed = datetime(2025, 9, 30, 12, 0, 0, tzinfo=UTC)
    mock_dt = mocker.patch("flock.core.visibility.datetime")
    mock_dt.now.return_value = fixed
    return fixed


@pytest.fixture
def fixed_uuid(mocker):
    """Fix UUID generation for deterministic tests."""
    fixed = UUID("12345678-1234-5678-1234-567812345678")
    mocker.patch("flock.core.artifacts.uuid4", return_value=fixed)
    return fixed


@pytest.fixture
def collector():
    """Create DashboardEventCollector instance for testing."""
    return DashboardEventCollector(store=InMemoryBlackboardStore())


@pytest.fixture
def orchestrator_with_collector(orchestrator, collector):
    """Create orchestrator with attached collector for specialized tests."""
    orchestrator._dashboard_collector = collector
    return orchestrator


def pytest_collection_modifyitems(config, items):
    """Reorder tests to run contamination-prone tests first sequentially.

    Tests in certain modules are sensitive to Rich/logging state pollution
    from other tests. By running them first before any contamination occurs,
    they pass reliably.
    """
    # Tests that must run first (in order) to avoid contamination
    priority_modules = [
        "test_unified_tracing.py",  # Tracing tests must run first - sensitive to trace state contamination
        "test_utilities.py",
        "test_cli.py",
        "test_engines.py",
        "test_orchestrator.py",
        "test_service.py",
    ]

    # Separate priority tests from others
    priority_tests = []
    other_tests = []

    for item in items:
        test_file = Path(item.fspath).name
        if test_file in priority_modules:
            priority_tests.append(item)
        else:
            other_tests.append(item)

    # Sort priority tests by module order
    def get_priority(item):
        test_file = Path(item.fspath).name
        try:
            return priority_modules.index(test_file)
        except ValueError:
            return 999

    priority_tests.sort(key=get_priority)

    # Reorder: priority tests first, then everything else
    items[:] = priority_tests + other_tests

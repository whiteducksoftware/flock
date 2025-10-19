"""
Unit tests for Logic Operations API state extraction helpers.

Phase 1.2: Helper Function Unit Tests (TDD Approach)

This module tests three helper functions that extract internal state from
CorrelationEngine and BatchEngine for API exposure:

1. _get_correlation_groups() - Extracts JoinSpec waiting state
2. _get_batch_state() - Extracts BatchSpec accumulator state
3. _compute_agent_status() - Determines agent ready/waiting/active status

**TDD Approach**: Tests are written FIRST, implementation SECOND.
These functions don't exist yet - tests will FAIL initially!

Architecture Reference:
  docs/internal/logic-operations-ux/03_backend_api_architecture.md lines 307-445

Related:
  - CorrelationEngine: src/flock/correlation_engine.py
  - BatchEngine: src/flock/batch_accumulator.py
  - Dashboard service: src/flock/dashboard/service.py
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import BaseModel

from flock.core import Flock
from flock.core.artifacts import Artifact
from flock.core.subscription import BatchSpec, JoinSpec
from flock.core.visibility import PublicVisibility
from flock.orchestrator.batch_accumulator import BatchAccumulator, BatchEngine
from flock.orchestrator.correlation_engine import CorrelationEngine, CorrelationGroup
from flock.registry import flock_type


# ============================================================================
# Test Artifact Types
# ============================================================================


@flock_type
class XRayImage(BaseModel):
    """Test artifact type for JoinSpec correlation tests."""

    patient_id: str
    image_data: str


@flock_type
class LabResults(BaseModel):
    """Test artifact type for JoinSpec correlation tests."""

    patient_id: str
    test_results: str


@flock_type
class Email(BaseModel):
    """Test artifact type for BatchSpec tests."""

    subject: str
    body: str


# ============================================================================
# Test Helper: _get_correlation_groups()
# ============================================================================


def test_get_correlation_groups_empty():
    """
    GIVEN: CorrelationEngine with no correlation groups
    WHEN: _get_correlation_groups() is called
    THEN: Should return empty list

    Test ensures function handles the empty/initial state correctly.
    """
    from flock.dashboard.routes.helpers import _get_correlation_groups

    engine = CorrelationEngine()
    agent_name = "radiologist"
    subscription_index = 0

    # Act
    result = _get_correlation_groups(engine, agent_name, subscription_index)

    # Assert
    assert result == [], "Empty engine should return empty list"


def test_get_correlation_groups_single_group_partial():
    """
    GIVEN: CorrelationGroup with 1 artifact collected, 1 waiting
    WHEN: _get_correlation_groups() is called
    THEN: Should return group state with correct counts and waiting types

    Scenario: XRayImage collected for patient_123, LabResults still waiting

    Expected structure:
    {
        "correlation_key": "patient_123",
        "created_at": ISO timestamp,
        "elapsed_seconds": ~0-1 (just created),
        "expires_in_seconds": ~299-300 (5 min window),
        "collected_types": {"XRayImage": 1, "LabResults": 0},
        "required_types": {"XRayImage": 1, "LabResults": 1},
        "waiting_for": ["LabResults"],
        "is_complete": False,
        "is_expired": False
    }
    """
    from flock.dashboard.routes.helpers import _get_correlation_groups

    # Setup: Create engine with partial correlation group
    engine = CorrelationEngine()
    agent_name = "radiologist"
    subscription_index = 0

    # Create correlation group manually
    pool_key = (agent_name, subscription_index)
    correlation_key = "patient_123"

    group = CorrelationGroup(
        correlation_key=correlation_key,
        required_types={"XRayImage", "LabResults"},
        type_counts={"XRayImage": 1, "LabResults": 1},
        window_spec=timedelta(minutes=5),
        created_at_sequence=1,
    )
    group.created_at_time = datetime.now(UTC)

    # Add one artifact (XRayImage)
    xray_artifact = Artifact(
        id=uuid4(),
        type="XRayImage",
        payload={"patient_id": "patient_123", "image_data": "scan.png"},
        produced_by="scanner",
        visibility=PublicVisibility(),
    )
    group.waiting_artifacts["XRayImage"].append(xray_artifact)

    # Store in engine
    engine.correlation_groups[pool_key][correlation_key] = group

    # Act
    result = _get_correlation_groups(engine, agent_name, subscription_index)

    # Assert
    assert len(result) == 1, "Should return 1 correlation group"

    group_state = result[0]
    assert group_state["correlation_key"] == "patient_123"
    assert group_state["collected_types"]["XRayImage"] == 1
    assert group_state["collected_types"]["LabResults"] == 0
    assert group_state["required_types"]["XRayImage"] == 1
    assert group_state["required_types"]["LabResults"] == 1
    assert "LabResults" in group_state["waiting_for"]
    assert "XRayImage" not in group_state["waiting_for"]
    assert group_state["is_complete"] is False
    assert group_state["is_expired"] is False

    # Check time calculations
    assert group_state["elapsed_seconds"] >= 0
    assert group_state["elapsed_seconds"] < 2  # Just created
    assert group_state["expires_in_seconds"] is not None
    assert 298 <= group_state["expires_in_seconds"] <= 300  # 5 min window
    assert group_state["created_at"] is not None


def test_get_correlation_groups_multiple_patients():
    """
    GIVEN: Multiple correlation groups for different patients
    WHEN: _get_correlation_groups() is called
    THEN: Should return all groups with independent state

    Scenario:
    - patient_123: XRayImage collected, waiting for LabResults
    - patient_456: Both XRayImage and LabResults collected (complete)
    - patient_789: Only LabResults collected, waiting for XRayImage
    """
    from flock.dashboard.routes.helpers import _get_correlation_groups

    engine = CorrelationEngine()
    agent_name = "radiologist"
    subscription_index = 0
    pool_key = (agent_name, subscription_index)

    # Group 1: patient_123 (partial - has XRay)
    group1 = CorrelationGroup(
        correlation_key="patient_123",
        required_types={"XRayImage", "LabResults"},
        type_counts={"XRayImage": 1, "LabResults": 1},
        window_spec=timedelta(minutes=5),
        created_at_sequence=1,
    )
    group1.created_at_time = datetime.now(UTC)
    xray1 = Artifact(
        id=uuid4(),
        type="XRayImage",
        payload={"patient_id": "patient_123", "image_data": "scan1.png"},
        produced_by="scanner",
        visibility=PublicVisibility(),
    )
    group1.waiting_artifacts["XRayImage"].append(xray1)

    # Group 2: patient_456 (complete - should not appear in waiting state)
    # Actually, in real implementation, complete groups are removed immediately
    # So this group wouldn't exist in the engine. Skip this scenario.

    # Group 3: patient_789 (partial - has LabResults)
    group3 = CorrelationGroup(
        correlation_key="patient_789",
        required_types={"XRayImage", "LabResults"},
        type_counts={"XRayImage": 1, "LabResults": 1},
        window_spec=timedelta(minutes=5),
        created_at_sequence=2,
    )
    group3.created_at_time = datetime.now(UTC)
    lab3 = Artifact(
        id=uuid4(),
        type="LabResults",
        payload={"patient_id": "patient_789", "test_results": "results3.pdf"},
        produced_by="lab",
        visibility=PublicVisibility(),
    )
    group3.waiting_artifacts["LabResults"].append(lab3)

    # Store in engine
    engine.correlation_groups[pool_key]["patient_123"] = group1
    engine.correlation_groups[pool_key]["patient_789"] = group3

    # Act
    result = _get_correlation_groups(engine, agent_name, subscription_index)

    # Assert
    assert len(result) == 2, "Should return 2 incomplete correlation groups"

    # Check patient_123
    group_123 = next(g for g in result if g["correlation_key"] == "patient_123")
    assert group_123["collected_types"]["XRayImage"] == 1
    assert group_123["collected_types"]["LabResults"] == 0
    assert "LabResults" in group_123["waiting_for"]

    # Check patient_789
    group_789 = next(g for g in result if g["correlation_key"] == "patient_789")
    assert group_789["collected_types"]["XRayImage"] == 0
    assert group_789["collected_types"]["LabResults"] == 1
    assert "XRayImage" in group_789["waiting_for"]


def test_get_correlation_groups_time_calculations():
    """
    GIVEN: CorrelationGroup created 30 seconds ago
    WHEN: _get_correlation_groups() is called
    THEN: elapsed_seconds should be ~30, expires_in_seconds ~270

    Tests time-based window calculations are accurate.
    """
    from flock.dashboard.routes.helpers import _get_correlation_groups

    engine = CorrelationEngine()
    agent_name = "radiologist"
    subscription_index = 0
    pool_key = (agent_name, subscription_index)

    # Create group 30 seconds ago
    group = CorrelationGroup(
        correlation_key="patient_123",
        required_types={"XRayImage", "LabResults"},
        type_counts={"XRayImage": 1, "LabResults": 1},
        window_spec=timedelta(minutes=5),  # 300 seconds
        created_at_sequence=1,
    )
    group.created_at_time = datetime.now(UTC) - timedelta(seconds=30)

    # Add artifact
    xray = Artifact(
        id=uuid4(),
        type="XRayImage",
        payload={"patient_id": "patient_123", "image_data": "scan.png"},
        produced_by="scanner",
        visibility=PublicVisibility(),
    )
    group.waiting_artifacts["XRayImage"].append(xray)

    engine.correlation_groups[pool_key]["patient_123"] = group

    # Act
    result = _get_correlation_groups(engine, agent_name, subscription_index)

    # Assert
    assert len(result) == 1
    group_state = result[0]

    # Allow 2 second tolerance for test execution time
    assert 28 <= group_state["elapsed_seconds"] <= 32, (
        f"Expected elapsed ~30s, got {group_state['elapsed_seconds']}"
    )
    assert 268 <= group_state["expires_in_seconds"] <= 272, (
        f"Expected expires_in ~270s, got {group_state['expires_in_seconds']}"
    )


def test_get_correlation_groups_count_window():
    """
    GIVEN: CorrelationGroup with count-based window (within=10 artifacts)
    WHEN: _get_correlation_groups() is called
    THEN: Should return expires_in_artifacts instead of expires_in_seconds

    Tests count-based window state extraction.
    """
    from flock.dashboard.routes.helpers import _get_correlation_groups

    engine = CorrelationEngine()
    engine.global_sequence = 5  # 5 artifacts published globally

    agent_name = "correlator"
    subscription_index = 0
    pool_key = (agent_name, subscription_index)

    # Create group with count window
    group = CorrelationGroup(
        correlation_key="batch-1",
        required_types={"XRayImage", "LabResults"},
        type_counts={"XRayImage": 1, "LabResults": 1},
        window_spec=10,  # Count window: 10 artifacts
        created_at_sequence=2,  # Created at sequence 2
    )
    group.created_at_time = datetime.now(UTC)

    # Add artifact
    xray = Artifact(
        id=uuid4(),
        type="XRayImage",
        payload={"patient_id": "patient_123", "image_data": "scan.png"},
        produced_by="scanner",
        visibility=PublicVisibility(),
    )
    group.waiting_artifacts["XRayImage"].append(xray)

    engine.correlation_groups[pool_key]["batch-1"] = group

    # Act
    result = _get_correlation_groups(engine, agent_name, subscription_index)

    # Assert
    assert len(result) == 1
    group_state = result[0]

    # Count window calculations:
    # created_at_sequence=2, global_sequence=5
    # artifacts_passed = 5 - 2 = 3
    # expires_in_artifacts = 10 - 3 = 7
    assert group_state["expires_in_seconds"] is None, (
        "Count window should not have time expiry"
    )
    assert group_state["expires_in_artifacts"] == 7, (
        f"Expected 7 artifacts remaining, got {group_state['expires_in_artifacts']}"
    )


# ============================================================================
# Test Helper: _get_batch_state()
# ============================================================================


def test_get_batch_state_no_accumulator():
    """
    GIVEN: BatchEngine with no batch accumulator
    WHEN: _get_batch_state() is called
    THEN: Should return None

    Tests function handles non-existent batch gracefully.
    """
    from flock.dashboard.routes.helpers import _get_batch_state

    engine = BatchEngine()
    agent_name = "email_processor"
    subscription_index = 0
    batch_spec = BatchSpec(size=25)

    # Act
    result = _get_batch_state(engine, agent_name, subscription_index, batch_spec)

    # Assert
    assert result is None, "No batch should return None"


def test_get_batch_state_size_based():
    """
    GIVEN: BatchSpec(size=25) with 10 artifacts collected
    WHEN: _get_batch_state() is called
    THEN: Should return items_collected=10, items_target=25, items_remaining=15

    Tests size-based batch state extraction.
    """
    from flock.dashboard.routes.helpers import _get_batch_state

    engine = BatchEngine()
    agent_name = "email_processor"
    subscription_index = 0
    batch_spec = BatchSpec(size=25)
    batch_key = (agent_name, subscription_index)

    # Create batch accumulator with 10 artifacts
    accumulator = BatchAccumulator(
        batch_spec=batch_spec,
        created_at=datetime.now(UTC),
    )
    for i in range(10):
        artifact = Artifact(
            id=uuid4(),
            type="Email",
            payload={"subject": f"Email {i}", "body": "test"},
            produced_by="mailer",
            visibility=PublicVisibility(),
        )
        accumulator.artifacts.append(artifact)

    engine.batches[batch_key] = accumulator

    # Act
    result = _get_batch_state(engine, agent_name, subscription_index, batch_spec)

    # Assert
    assert result is not None
    assert result["items_collected"] == 10
    assert result["items_target"] == 25
    assert result["items_remaining"] == 15
    assert result["elapsed_seconds"] >= 0
    assert result["will_flush"] == "on_size"


def test_get_batch_state_timeout_based():
    """
    GIVEN: BatchSpec(timeout=30s) created 18 seconds ago
    WHEN: _get_batch_state() is called
    THEN: Should return timeout_seconds=30, timeout_remaining_seconds=12

    Tests timeout-based batch state extraction.
    """
    from flock.dashboard.routes.helpers import _get_batch_state

    engine = BatchEngine()
    agent_name = "email_processor"
    subscription_index = 0
    batch_spec = BatchSpec(timeout=timedelta(seconds=30))
    batch_key = (agent_name, subscription_index)

    # Create batch accumulator 18 seconds ago
    accumulator = BatchAccumulator(
        batch_spec=batch_spec,
        created_at=datetime.now(UTC) - timedelta(seconds=18),
    )
    # Add at least one artifact (empty batches return None)
    artifact = Artifact(
        id=uuid4(),
        type="Email",
        payload={"subject": "Test", "body": "test"},
        produced_by="mailer",
        visibility=PublicVisibility(),
    )
    accumulator.artifacts.append(artifact)

    engine.batches[batch_key] = accumulator

    # Act
    result = _get_batch_state(engine, agent_name, subscription_index, batch_spec)

    # Assert
    assert result is not None
    assert result["timeout_seconds"] == 30

    # Allow 2 second tolerance
    assert 10 <= result["timeout_remaining_seconds"] <= 14, (
        f"Expected ~12s remaining, got {result['timeout_remaining_seconds']}"
    )
    assert 16 <= result["elapsed_seconds"] <= 20, (
        f"Expected ~18s elapsed, got {result['elapsed_seconds']}"
    )
    assert result["will_flush"] == "on_timeout"


def test_get_batch_state_dual_condition():
    """
    GIVEN: BatchSpec(size=25, timeout=30s) with both conditions
    WHEN: _get_batch_state() is called
    THEN: Should return both size AND timeout metrics

    Tests hybrid batch state extraction.
    """
    from flock.dashboard.routes.helpers import _get_batch_state

    engine = BatchEngine()
    agent_name = "email_processor"
    subscription_index = 0
    batch_spec = BatchSpec(size=25, timeout=timedelta(seconds=30))
    batch_key = (agent_name, subscription_index)

    # Create batch with 10 artifacts, 12 seconds ago
    accumulator = BatchAccumulator(
        batch_spec=batch_spec,
        created_at=datetime.now(UTC) - timedelta(seconds=12),
    )
    for i in range(10):
        artifact = Artifact(
            id=uuid4(),
            type="Email",
            payload={"subject": f"Email {i}", "body": "test"},
            produced_by="mailer",
            visibility=PublicVisibility(),
        )
        accumulator.artifacts.append(artifact)

    engine.batches[batch_key] = accumulator

    # Act
    result = _get_batch_state(engine, agent_name, subscription_index, batch_spec)

    # Assert
    assert result is not None

    # Size metrics
    assert result["items_collected"] == 10
    assert result["items_target"] == 25
    assert result["items_remaining"] == 15

    # Timeout metrics
    assert result["timeout_seconds"] == 30
    assert 16 <= result["timeout_remaining_seconds"] <= 20  # ~18s remaining

    # Prediction: Neither close to triggering, so "unknown"
    assert result["will_flush"] in ["unknown", "on_size", "on_timeout"]


def test_get_batch_state_group_count():
    """
    GIVEN: BatchAccumulator with _group_count attribute (group batching)
    WHEN: _get_batch_state() is called
    THEN: Should use _group_count instead of len(artifacts)

    Tests group batching scenario (JoinSpec + BatchSpec combination).

    Scenario: Batching correlated pairs (XRayImage + LabResults)
    - 3 correlated pairs collected = 6 total artifacts
    - But _group_count = 3 (counting pairs, not individual artifacts)
    - items_collected should be 3, not 6
    """
    from flock.dashboard.routes.helpers import _get_batch_state

    engine = BatchEngine()
    agent_name = "radiologist"
    subscription_index = 0
    batch_spec = BatchSpec(size=5)  # Batch 5 correlated pairs
    batch_key = (agent_name, subscription_index)

    # Create batch with 6 artifacts (3 pairs)
    accumulator = BatchAccumulator(
        batch_spec=batch_spec,
        created_at=datetime.now(UTC),
    )

    # Add 6 artifacts (3 correlated pairs)
    for i in range(3):
        xray = Artifact(
            id=uuid4(),
            type="XRayImage",
            payload={"patient_id": f"patient_{i}", "image_data": "scan.png"},
            produced_by="scanner",
            visibility=PublicVisibility(),
        )
        lab = Artifact(
            id=uuid4(),
            type="LabResults",
            payload={"patient_id": f"patient_{i}", "test_results": "results.pdf"},
            produced_by="lab",
            visibility=PublicVisibility(),
        )
        accumulator.artifacts.append(xray)
        accumulator.artifacts.append(lab)

    # Set group count (simulating add_artifact_group calls)
    accumulator._group_count = 3  # 3 pairs

    engine.batches[batch_key] = accumulator

    # Act
    result = _get_batch_state(engine, agent_name, subscription_index, batch_spec)

    # Assert
    assert result is not None
    assert result["items_collected"] == 3, "Should count groups (3), not artifacts (6)"
    assert result["items_target"] == 5
    assert result["items_remaining"] == 2


def test_get_batch_state_empty_batch_returns_none():
    """
    GIVEN: BatchAccumulator exists but has no artifacts
    WHEN: _get_batch_state() is called
    THEN: Should return None

    Tests function doesn't return state for empty batches.
    """
    from flock.dashboard.routes.helpers import _get_batch_state

    engine = BatchEngine()
    agent_name = "email_processor"
    subscription_index = 0
    batch_spec = BatchSpec(size=25)
    batch_key = (agent_name, subscription_index)

    # Create empty batch accumulator
    accumulator = BatchAccumulator(
        batch_spec=batch_spec,
        created_at=datetime.now(UTC),
    )
    # No artifacts added

    engine.batches[batch_key] = accumulator

    # Act
    result = _get_batch_state(engine, agent_name, subscription_index, batch_spec)

    # Assert
    assert result is None, "Empty batch should return None"


# ============================================================================
# Test Helper: _compute_agent_status()
# ============================================================================


def test_compute_agent_status_ready():
    """
    GIVEN: Agent with no correlation groups or batches
    WHEN: _compute_agent_status() is called
    THEN: Should return "ready"

    Tests default/idle state.
    """
    from flock.dashboard.routes.helpers import _compute_agent_status

    orchestrator = Flock()

    # Create agent with no JoinSpec or BatchSpec
    agent = orchestrator.agent("simple_agent").consumes(Email)

    # Act
    status = _compute_agent_status(agent.agent, orchestrator)

    # Assert
    assert status == "ready", "Agent with no waiting state should be ready"


def test_compute_agent_status_waiting_correlation():
    """
    GIVEN: Agent with active correlation groups
    WHEN: _compute_agent_status() is called
    THEN: Should return "waiting"

    Tests waiting state for JoinSpec correlation.
    """
    from flock.dashboard.routes.helpers import _compute_agent_status

    orchestrator = Flock()

    # Create agent with JoinSpec
    agent = orchestrator.agent("radiologist").consumes(
        XRayImage,
        LabResults,
        join=JoinSpec(by=lambda x: x.patient_id, within=timedelta(minutes=5)),
    )

    # Manually create correlation group in orchestrator's engine
    pool_key = (agent.agent.name, 0)
    group = CorrelationGroup(
        correlation_key="patient_123",
        required_types={"XRayImage", "LabResults"},
        type_counts={"XRayImage": 1, "LabResults": 1},
        window_spec=timedelta(minutes=5),
        created_at_sequence=1,
    )
    group.created_at_time = datetime.now(UTC)

    # Add one artifact to make it incomplete
    xray = Artifact(
        id=uuid4(),
        type="XRayImage",
        payload={"patient_id": "patient_123", "image_data": "scan.png"},
        produced_by="scanner",
        visibility=PublicVisibility(),
    )
    group.waiting_artifacts["XRayImage"].append(xray)

    orchestrator._correlation_engine.correlation_groups[pool_key]["patient_123"] = group

    # Act
    status = _compute_agent_status(agent.agent, orchestrator)

    # Assert
    assert status == "waiting", "Agent with correlation groups should be waiting"


def test_compute_agent_status_waiting_batch():
    """
    GIVEN: Agent with batch accumulating
    WHEN: _compute_agent_status() is called
    THEN: Should return "waiting"

    Tests waiting state for BatchSpec accumulation.
    """
    from flock.dashboard.routes.helpers import _compute_agent_status

    orchestrator = Flock()

    # Create agent with BatchSpec
    agent = orchestrator.agent("email_processor").consumes(
        Email, batch=BatchSpec(size=25)
    )

    # Manually create batch accumulator in orchestrator's engine
    batch_key = (agent.agent.name, 0)
    accumulator = BatchAccumulator(
        batch_spec=BatchSpec(size=25),
        created_at=datetime.now(UTC),
    )
    # Add some artifacts
    for i in range(10):
        artifact = Artifact(
            id=uuid4(),
            type="Email",
            payload={"subject": f"Email {i}", "body": "test"},
            produced_by="mailer",
            visibility=PublicVisibility(),
        )
        accumulator.artifacts.append(artifact)

    orchestrator._batch_engine.batches[batch_key] = accumulator

    # Act
    status = _compute_agent_status(agent.agent, orchestrator)

    # Assert
    assert status == "waiting", "Agent with batch accumulating should be waiting"


def test_compute_agent_status_no_joinspec_or_batchspec():
    """
    GIVEN: Agent has subscriptions but no JoinSpec or BatchSpec
    WHEN: _compute_agent_status() is called
    THEN: Should always return "ready"

    Tests agents without logic operations are always ready.
    """
    from flock.dashboard.routes.helpers import _compute_agent_status

    orchestrator = Flock()

    # Create simple agent (no join/batch)
    agent = orchestrator.agent("simple_consumer").consumes(Email)

    # Act
    status = _compute_agent_status(agent.agent, orchestrator)

    # Assert
    assert status == "ready", "Simple agent should always be ready"


def test_compute_agent_status_multiple_subscriptions_mixed():
    """
    GIVEN: Agent with multiple subscriptions, one waiting, one ready
    WHEN: _compute_agent_status() is called
    THEN: Should return "waiting" (any subscription waiting = agent waiting)

    Tests agents with mixed subscription states.
    """
    from flock.dashboard.routes.helpers import _compute_agent_status

    orchestrator = Flock()

    # Create agent with TWO subscriptions:
    # 1. JoinSpec subscription (will be waiting)
    # 2. Simple subscription (no join/batch)
    agent = (
        orchestrator.agent("multi_subscriber")
        .consumes(
            XRayImage,
            LabResults,
            join=JoinSpec(by=lambda x: x.patient_id, within=timedelta(minutes=5)),
        )
        .consumes(Email)  # Second subscription (simple)
    )

    # Create waiting state for first subscription (JoinSpec)
    pool_key = (agent.agent.name, 0)
    group = CorrelationGroup(
        correlation_key="patient_123",
        required_types={"XRayImage", "LabResults"},
        type_counts={"XRayImage": 1, "LabResults": 1},
        window_spec=timedelta(minutes=5),
        created_at_sequence=1,
    )
    group.created_at_time = datetime.now(UTC)
    xray = Artifact(
        id=uuid4(),
        type="XRayImage",
        payload={"patient_id": "patient_123", "image_data": "scan.png"},
        produced_by="scanner",
        visibility=PublicVisibility(),
    )
    group.waiting_artifacts["XRayImage"].append(xray)
    orchestrator._correlation_engine.correlation_groups[pool_key]["patient_123"] = group

    # Act
    status = _compute_agent_status(agent.agent, orchestrator)

    # Assert
    assert status == "waiting", "Agent with any waiting subscription should be waiting"


def test_compute_agent_status_batch_empty_should_be_ready():
    """
    GIVEN: Agent with BatchSpec but accumulator is empty
    WHEN: _compute_agent_status() is called
    THEN: Should return "ready" (not waiting)

    Tests edge case: batch accumulator exists but has no artifacts.
    """
    from flock.dashboard.routes.helpers import _compute_agent_status

    orchestrator = Flock()

    # Create agent with BatchSpec
    agent = orchestrator.agent("email_processor").consumes(
        Email, batch=BatchSpec(size=25)
    )

    # Create EMPTY batch accumulator
    batch_key = (agent.agent.name, 0)
    accumulator = BatchAccumulator(
        batch_spec=BatchSpec(size=25),
        created_at=datetime.now(UTC),
    )
    # No artifacts added

    orchestrator._batch_engine.batches[batch_key] = accumulator

    # Act
    status = _compute_agent_status(agent.agent, orchestrator)

    # Assert
    assert status == "ready", "Agent with empty batch should be ready (not waiting)"


# ============================================================================
# Integration Tests: All Helpers Together
# ============================================================================


@pytest.mark.asyncio
async def test_integration_correlation_and_batch_together():
    """
    GIVEN: Agent with BOTH JoinSpec AND BatchSpec
    WHEN: State extraction helpers are called
    THEN: Should correctly report both correlation and batch state

    Scenario: Agent batches correlated pairs
    - JoinSpec correlates XRayImage + LabResults by patient_id
    - BatchSpec batches 5 correlated pairs before processing

    This tests the complex case of combined logic operations.
    """
    from flock.dashboard.routes.helpers import (
        _compute_agent_status,
        _get_batch_state,
        _get_correlation_groups,
    )

    orchestrator = Flock()

    # Create agent with BOTH JoinSpec and BatchSpec
    agent = orchestrator.agent("radiologist").consumes(
        XRayImage,
        LabResults,
        join=JoinSpec(by=lambda x: x.patient_id, within=timedelta(minutes=5)),
        batch=BatchSpec(size=5),  # Batch 5 correlated pairs
    )

    agent_name = agent.agent.name
    subscription_index = 0

    # Setup correlation state: 2 patients waiting for correlations
    pool_key = (agent_name, subscription_index)

    # Patient 1: Has XRay, waiting for Labs
    group1 = CorrelationGroup(
        correlation_key="patient_123",
        required_types={"XRayImage", "LabResults"},
        type_counts={"XRayImage": 1, "LabResults": 1},
        window_spec=timedelta(minutes=5),
        created_at_sequence=1,
    )
    group1.created_at_time = datetime.now(UTC)
    xray1 = Artifact(
        id=uuid4(),
        type="XRayImage",
        payload={"patient_id": "patient_123", "image_data": "scan.png"},
        produced_by="scanner",
        visibility=PublicVisibility(),
    )
    group1.waiting_artifacts["XRayImage"].append(xray1)

    # Patient 2: Has Labs, waiting for XRay
    group2 = CorrelationGroup(
        correlation_key="patient_456",
        required_types={"XRayImage", "LabResults"},
        type_counts={"XRayImage": 1, "LabResults": 1},
        window_spec=timedelta(minutes=5),
        created_at_sequence=2,
    )
    group2.created_at_time = datetime.now(UTC)
    lab2 = Artifact(
        id=uuid4(),
        type="LabResults",
        payload={"patient_id": "patient_456", "test_results": "results.pdf"},
        produced_by="lab",
        visibility=PublicVisibility(),
    )
    group2.waiting_artifacts["LabResults"].append(lab2)

    orchestrator._correlation_engine.correlation_groups[pool_key]["patient_123"] = (
        group1
    )
    orchestrator._correlation_engine.correlation_groups[pool_key]["patient_456"] = (
        group2
    )

    # Setup batch state: 2 correlated pairs already batched
    batch_key = (agent_name, subscription_index)
    accumulator = BatchAccumulator(
        batch_spec=BatchSpec(size=5),
        created_at=datetime.now(UTC),
    )
    # Simulate 2 correlated pairs (4 artifacts total)
    for i in range(2):
        xray = Artifact(
            id=uuid4(),
            type="XRayImage",
            payload={"patient_id": f"patient_batch_{i}", "image_data": "scan.png"},
            produced_by="scanner",
            visibility=PublicVisibility(),
        )
        lab = Artifact(
            id=uuid4(),
            type="LabResults",
            payload={"patient_id": f"patient_batch_{i}", "test_results": "results.pdf"},
            produced_by="lab",
            visibility=PublicVisibility(),
        )
        accumulator.artifacts.extend([xray, lab])
    accumulator._group_count = 2  # 2 pairs batched

    orchestrator._batch_engine.batches[batch_key] = accumulator

    # Act: Extract all state
    correlation_groups = _get_correlation_groups(
        orchestrator._correlation_engine, agent_name, subscription_index
    )
    batch_state = _get_batch_state(
        orchestrator._batch_engine, agent_name, subscription_index, BatchSpec(size=5)
    )
    agent_status = _compute_agent_status(agent.agent, orchestrator)

    # Assert: Correlation state
    assert len(correlation_groups) == 2, "Should have 2 waiting correlation groups"
    assert any(g["correlation_key"] == "patient_123" for g in correlation_groups)
    assert any(g["correlation_key"] == "patient_456" for g in correlation_groups)

    # Assert: Batch state
    assert batch_state is not None
    assert batch_state["items_collected"] == 2, "Should count groups, not artifacts"
    assert batch_state["items_target"] == 5
    assert batch_state["items_remaining"] == 3

    # Assert: Agent status
    assert agent_status == "waiting", (
        "Agent should be waiting (both correlation and batch active)"
    )


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


def test_get_correlation_groups_handles_missing_pool_key():
    """
    GIVEN: CorrelationEngine with no entry for agent+subscription
    WHEN: _get_correlation_groups() is called
    THEN: Should return empty list (not crash)
    """
    from flock.dashboard.routes.helpers import _get_correlation_groups

    engine = CorrelationEngine()
    agent_name = "nonexistent_agent"
    subscription_index = 99

    # Act
    result = _get_correlation_groups(engine, agent_name, subscription_index)

    # Assert
    assert result == [], "Missing pool key should return empty list"


def test_get_batch_state_handles_missing_batch_key():
    """
    GIVEN: BatchEngine with no entry for agent+subscription
    WHEN: _get_batch_state() is called
    THEN: Should return None (not crash)
    """
    from flock.dashboard.routes.helpers import _get_batch_state

    engine = BatchEngine()
    agent_name = "nonexistent_agent"
    subscription_index = 99
    batch_spec = BatchSpec(size=25)

    # Act
    result = _get_batch_state(engine, agent_name, subscription_index, batch_spec)

    # Assert
    assert result is None, "Missing batch key should return None"


def test_compute_agent_status_handles_agent_with_no_subscriptions():
    """
    GIVEN: Agent with empty subscriptions list
    WHEN: _compute_agent_status() is called
    THEN: Should return "ready" (not crash)

    Edge case: Newly created agent before subscriptions are added.
    """
    from flock.dashboard.routes.helpers import _compute_agent_status

    orchestrator = Flock()

    # Create mock agent with no subscriptions
    mock_agent = Mock()
    mock_agent.name = "empty_agent"
    mock_agent.subscriptions = []

    # Act
    status = _compute_agent_status(mock_agent, orchestrator)

    # Assert
    assert status == "ready", "Agent with no subscriptions should be ready"


# ============================================================================
# Documentation and Usage Examples
# ============================================================================


def test_readme_example_correlation_state_extraction():
    """
    Example showing how _get_correlation_groups() exposes internal state.

    This is a documentation test that demonstrates typical usage.
    """
    from flock.dashboard.routes.helpers import _get_correlation_groups

    # Setup: Healthcare diagnostic agent waiting for patient data
    engine = CorrelationEngine()
    agent_name = "diagnostician"
    subscription_index = 0
    pool_key = (agent_name, subscription_index)

    # Patient 123 has X-ray, waiting for lab results
    group = CorrelationGroup(
        correlation_key="patient_123",
        required_types={"XRayImage", "LabResults"},
        type_counts={"XRayImage": 1, "LabResults": 1},
        window_spec=timedelta(minutes=5),
        created_at_sequence=1,
    )
    group.created_at_time = datetime.now(UTC)
    xray = Artifact(
        id=uuid4(),
        type="XRayImage",
        payload={"patient_id": "patient_123", "image_data": "scan.png"},
        produced_by="scanner",
        visibility=PublicVisibility(),
    )
    group.waiting_artifacts["XRayImage"].append(xray)
    engine.correlation_groups[pool_key]["patient_123"] = group

    # Extract state for API
    groups = _get_correlation_groups(engine, agent_name, subscription_index)

    # Verify structure matches API spec
    assert len(groups) == 1
    patient_state = groups[0]

    # This structure will be exposed via /api/agents endpoint
    assert "correlation_key" in patient_state
    assert "collected_types" in patient_state
    assert "waiting_for" in patient_state
    assert "elapsed_seconds" in patient_state
    assert "expires_in_seconds" in patient_state

    # Frontend can now display:
    # "Waiting for LabResults for patient_123 (45s elapsed, 255s remaining)"
    print(
        f"Waiting for {patient_state['waiting_for']} for {patient_state['correlation_key']}"
    )
    print(
        f"Elapsed: {patient_state['elapsed_seconds']}s, Expires in: {patient_state['expires_in_seconds']}s"
    )

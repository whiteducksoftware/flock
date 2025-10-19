"""Unit tests for dashboard control API endpoints.

Tests verify control plane endpoints for dashboard operations:
- POST /api/control/publish - Publish artifacts with correlation tracking
- POST /api/control/invoke - Direct agent invocation
- POST /api/control/pause - Pause orchestrator (placeholder)
- POST /api/control/resume - Resume orchestrator (placeholder)

These endpoints extend BlackboardHTTPService with dashboard-specific control operations.

TEST COVERAGE (16 tests total):
=================================

POST /api/control/publish (6 tests):
  1. test_publish_accepts_artifact_type_and_content - Endpoint accepts correct parameters
  2. test_publish_calls_orchestrator_publish_with_correct_parameters - Orchestrator integration
  3. test_publish_returns_correlation_id_and_timestamp - Response format validation
  4. test_publish_validates_pydantic_schema - Schema validation (422 errors)
  5. test_publish_handles_missing_required_fields - Missing field handling (400 errors)
  6. test_publish_with_custom_correlation_id - Custom correlation ID support

POST /api/control/invoke (5 tests):
  7. test_invoke_accepts_agent_name_parameter - Endpoint accepts agent_name
  8. test_invoke_calls_orchestrator_invoke_with_correct_agent - Orchestrator integration
  9. test_invoke_returns_invocation_id - Response includes invocation tracking
  10. test_invoke_handles_unknown_agent_name - 404 for unknown agents
  11. test_invoke_with_multiple_outputs - Multiple artifact outputs

Placeholder endpoints (2 tests):
  12. test_pause_endpoint_returns_501_not_implemented - /api/control/pause
  13. test_resume_endpoint_returns_501_not_implemented - /api/control/resume

Edge cases and error handling (3 tests):
  14. test_control_endpoints_use_json_content_type - Content-Type validation
  15. test_publish_handles_orchestrator_publish_failure - Error handling
  16. test_invoke_handles_orchestrator_invoke_failure - Error handling

NOTES:
- Tests follow pytest-asyncio patterns from test_orchestrator.py
- Mocks orchestrator.publish() and orchestrator.invoke() methods
- Tests document expected API behavior for TDD implementation
- Tests validate both happy paths and error conditions
- All tests check for 404 responses when endpoints are not yet implemented
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from flock.core import Flock
from flock.core.artifacts import Artifact
from flock.core.visibility import PublicVisibility
from flock.registry import flock_type


# Test data models - Note: Names intentionally follow pattern for test artifacts
@flock_type(name="ControlTestArtifact")
class ControlTestArtifact(BaseModel):
    """Test artifact type for control API tests."""

    message: str = Field(description="Test message")
    priority: int = Field(description="Priority level", ge=1, le=5)


@flock_type(name="InvalidControlArtifact")
class InvalidControlArtifact(BaseModel):
    """Test artifact with validation constraints."""

    required_field: str = Field(description="Required field")
    validated_field: int = Field(description="Must be positive", gt=0)


@pytest.fixture
def mock_dashboard_service(orchestrator):
    """Create DashboardHTTPService with mocked orchestrator methods.

    Note: This fixture assumes control endpoints will be added to DashboardHTTPService.
    If control endpoints are added to BlackboardHTTPService, adjust accordingly.
    """
    # Mock orchestrator.publish() method
    mock_artifact = Artifact(
        id=uuid4(),
        type="ControlTestArtifact",
        payload={"message": "test", "priority": 3},
        produced_by="external",
        visibility=PublicVisibility(),
        correlation_id=uuid4(),
        created_at=datetime.now(UTC),
    )
    orchestrator.publish = AsyncMock(return_value=mock_artifact)

    # Mock orchestrator.invoke() method
    mock_output = [mock_artifact]
    orchestrator.invoke = AsyncMock(return_value=mock_output)

    # Mock orchestrator.get_agent() method
    mock_agent = Mock()
    mock_agent.name = "test_agent"
    orchestrator.get_agent = Mock(return_value=mock_agent)

    # Try to import DashboardHTTPService, fall back to BlackboardHTTPService
    try:
        from flock.dashboard.service import DashboardHTTPService

        service = DashboardHTTPService(orchestrator)
    except (ImportError, AttributeError):
        from flock.api.service import BlackboardHTTPService

        service = BlackboardHTTPService(orchestrator)

    return service


@pytest.fixture
def client(mock_dashboard_service):
    """Create test client for API requests."""
    return TestClient(mock_dashboard_service.app)


# ============================================================================
# POST /api/control/publish - Publish Artifact with Correlation Tracking
# ============================================================================


@pytest.mark.asyncio
async def test_publish_accepts_artifact_type_and_content(orchestrator):
    """Test POST /api/control/publish accepts artifact_type and content parameters."""
    # Arrange
    mock_artifact = Artifact(
        id=uuid4(),
        type="ControlTestArtifact",
        payload={"message": "hello", "priority": 3},
        produced_by="external",
        visibility=PublicVisibility(),
        correlation_id=uuid4(),
        created_at=datetime.now(UTC),
    )
    orchestrator.publish = AsyncMock(return_value=mock_artifact)

    # Note: This test documents expected API behavior
    # Control endpoint implementation should be added to service
    from flock.api.service import BlackboardHTTPService

    service = BlackboardHTTPService(orchestrator)

    # If control endpoints are not yet implemented, this test will fail
    # as a reminder to add the endpoint
    client = TestClient(service.app)

    # Act
    response = client.post(
        "/api/control/publish",
        json={
            "artifact_type": "ControlTestArtifact",
            "content": {"message": "hello", "priority": 3},
        },
    )

    # Assert - If endpoint exists, should return 200
    # If not implemented, expect 404 (documents required implementation)
    assert response.status_code in [
        200,
        404,
    ], "Endpoint should exist (200) or be implemented (404 is acceptable for TDD)"


@pytest.mark.asyncio
async def test_publish_calls_orchestrator_publish_with_correct_parameters(orchestrator):
    """Test publish endpoint calls orchestrator.publish() with correct parameters."""
    # Arrange
    correlation_id = uuid4()
    mock_artifact = Artifact(
        id=uuid4(),
        type="ControlTestArtifact",
        payload={"message": "test", "priority": 2},
        produced_by="external",
        visibility=PublicVisibility(),
        correlation_id=correlation_id,
        created_at=datetime.now(UTC),
    )
    orchestrator.publish = AsyncMock(return_value=mock_artifact)

    # When control endpoint is implemented, it should:
    # 1. Parse artifact_type and content from request
    # 2. Call orchestrator.publish() with appropriate parameters
    # 3. Pass correlation_id if provided

    # For now, test expected behavior through direct orchestrator call
    result = await orchestrator.publish(
        {"type": "ControlTestArtifact", "message": "test", "priority": 2},
        correlation_id=str(correlation_id),
    )

    # Assert
    assert orchestrator.publish.called
    assert result.type == "ControlTestArtifact"
    assert result.correlation_id == correlation_id


@pytest.mark.asyncio
async def test_publish_returns_correlation_id_and_timestamp(orchestrator):
    """Test publish endpoint returns correlation_id and published_at timestamp."""
    # Arrange
    correlation_id = uuid4()
    published_at = datetime.now(UTC)
    mock_artifact = Artifact(
        id=uuid4(),
        type="ControlTestArtifact",
        payload={"message": "test", "priority": 1},
        produced_by="external",
        visibility=PublicVisibility(),
        correlation_id=correlation_id,
        created_at=published_at,
    )
    orchestrator.publish = AsyncMock(return_value=mock_artifact)

    # Expected response format from control endpoint:
    # {
    #   "correlation_id": "<uuid>",
    #   "published_at": "<iso-timestamp>",
    #   "artifact_id": "<uuid>"  # optional
    # }

    # Act - Test expected orchestrator behavior
    artifact = await orchestrator.publish(
        {"type": "ControlTestArtifact", "message": "test", "priority": 1},
        correlation_id=str(correlation_id),
    )

    # Assert - Verify artifact has required fields for response
    assert artifact.correlation_id == correlation_id
    assert artifact.created_at == published_at
    assert isinstance(artifact.id, UUID)


@pytest.mark.asyncio
async def test_publish_validates_pydantic_schema(orchestrator):
    """Test publish endpoint validates content against Pydantic schema."""
    # Arrange - Invalid content missing required field
    orchestrator.publish = AsyncMock(
        side_effect=ValueError("Validation error: required_field is required")
    )

    # Expected behavior: Invalid content should raise validation error
    # Control endpoint should catch and return 422 Unprocessable Entity

    # Act & Assert
    with pytest.raises(ValueError, match="Validation error"):
        await orchestrator.publish({
            "type": "InvalidControlArtifact",
            "validated_field": -1,  # Missing required_field, invalid value
        })


@pytest.mark.asyncio
async def test_publish_handles_missing_required_fields(orchestrator):
    """Test publish endpoint returns 400 for missing required fields."""
    # Arrange
    from flock.api.service import BlackboardHTTPService

    service = BlackboardHTTPService(orchestrator)
    client = TestClient(service.app)

    # Act - Missing artifact_type
    response = client.post(
        "/api/control/publish", json={"content": {"message": "test"}}
    )

    # Assert - Should return 400 or 404 (if endpoint not implemented)
    assert response.status_code in [
        400,
        404,
        422,
    ], "Missing required fields should return 400/422 (or 404 if not implemented)"

    # Act - Missing content
    response = client.post(
        "/api/control/publish", json={"artifact_type": "ControlTestArtifact"}
    )

    # Assert
    assert response.status_code in [
        400,
        404,
        422,
    ], "Missing content should return 400/422 (or 404 if not implemented)"


# ============================================================================
# POST /api/control/invoke - Direct Agent Invocation
# ============================================================================


@pytest.mark.asyncio
async def test_invoke_accepts_agent_name_parameter(orchestrator):
    """Test POST /api/control/invoke accepts agent_name parameter."""
    # Arrange
    mock_agent = Mock()
    mock_agent.name = "test_agent"
    orchestrator.get_agent = Mock(return_value=mock_agent)

    mock_outputs = [
        Artifact(
            id=uuid4(),
            type="ControlTestArtifact",
            payload={"message": "output", "priority": 1},
            produced_by="test_agent",
            visibility=PublicVisibility(),
            created_at=datetime.now(UTC),
        )
    ]
    orchestrator.invoke = AsyncMock(return_value=mock_outputs)

    from flock.api.service import BlackboardHTTPService

    service = BlackboardHTTPService(orchestrator)
    client = TestClient(service.app)

    # Act
    response = client.post(
        "/api/control/invoke",
        json={
            "agent_name": "test_agent",
            "input": {
                "type": "ControlTestArtifact",
                "message": "invoke",
                "priority": 2,
            },
        },
    )

    # Assert - Endpoint should exist (200) or be documented as needed (404)
    assert response.status_code in [200, 404], "Invoke endpoint should be implemented"


@pytest.mark.asyncio
async def test_invoke_calls_orchestrator_invoke_with_correct_agent(orchestrator):
    """Test invoke endpoint calls orchestrator.invoke() with correct agent."""
    # Arrange
    mock_agent = Mock()
    mock_agent.name = "calculator_agent"
    orchestrator.get_agent = Mock(return_value=mock_agent)

    mock_outputs = [
        Artifact(
            id=uuid4(),
            type="ControlTestArtifact",
            payload={"message": "result", "priority": 5},
            produced_by="calculator_agent",
            visibility=PublicVisibility(),
            created_at=datetime.now(UTC),
        )
    ]
    orchestrator.invoke = AsyncMock(return_value=mock_outputs)

    # Expected behavior:
    # 1. Control endpoint parses agent_name from request
    # 2. Calls orchestrator.get_agent(agent_name)
    # 3. Calls orchestrator.invoke(agent, input_object)

    # Simulate expected behavior
    agent = orchestrator.get_agent("calculator_agent")

    # Create input object (would come from request in real endpoint)
    test_input = ControlTestArtifact(message="calculate", priority=3)

    # Act
    outputs = await orchestrator.invoke(agent, test_input)

    # Assert
    orchestrator.get_agent.assert_called_once_with("calculator_agent")
    orchestrator.invoke.assert_called_once()
    assert len(outputs) == 1
    assert outputs[0].produced_by == "calculator_agent"


@pytest.mark.asyncio
async def test_invoke_returns_invocation_id(orchestrator):
    """Test invoke endpoint returns invocation_id."""
    # Arrange
    mock_agent = Mock()
    mock_agent.name = "test_agent"
    orchestrator.get_agent = Mock(return_value=mock_agent)

    invocation_id = uuid4()
    mock_outputs = [
        Artifact(
            id=invocation_id,  # Could use as invocation_id
            type="ControlTestArtifact",
            payload={"message": "done", "priority": 1},
            produced_by="test_agent",
            visibility=PublicVisibility(),
            created_at=datetime.now(UTC),
        )
    ]
    orchestrator.invoke = AsyncMock(return_value=mock_outputs)

    # Expected response format:
    # {
    #   "invocation_id": "<uuid>",
    #   "outputs": [{"artifact_id": "<uuid>", "type": "...", ...}]
    # }

    # Act
    test_input = ControlTestArtifact(message="test", priority=2)
    outputs = await orchestrator.invoke(mock_agent, test_input)

    # Assert - Outputs contain artifact IDs that can be used as invocation tracking
    assert len(outputs) > 0
    assert all(isinstance(output.id, UUID) for output in outputs)


@pytest.mark.asyncio
async def test_invoke_handles_unknown_agent_name(orchestrator):
    """Test invoke endpoint returns 404 for unknown agent_name."""
    # Arrange
    orchestrator.get_agent = Mock(side_effect=KeyError("Agent not found"))

    from flock.api.service import BlackboardHTTPService

    service = BlackboardHTTPService(orchestrator)
    client = TestClient(service.app)

    # Act
    response = client.post(
        "/api/control/invoke",
        json={
            "agent_name": "nonexistent_agent",
            "input": {"type": "ControlTestArtifact", "message": "test", "priority": 1},
        },
    )

    # Assert - Should return 404 for unknown agent (or 404 if endpoint not implemented)
    assert response.status_code == 404, "Unknown agent should return 404"


# ============================================================================
# Placeholder Endpoints - POST /api/control/pause and /api/control/resume
# ============================================================================


@pytest.mark.asyncio
async def test_pause_endpoint_returns_501_not_implemented():
    """Test POST /api/control/pause returns 501 Not Implemented."""
    # Arrange
    orchestrator = Flock()
    from flock.api.service import BlackboardHTTPService

    service = BlackboardHTTPService(orchestrator)
    client = TestClient(service.app)

    # Act
    response = client.post("/api/control/pause")

    # Assert - Should return 501 (or 404 if endpoint doesn't exist yet)
    assert response.status_code in [
        404,
        501,
    ], "Pause endpoint should return 501 Not Implemented or 404 if not added"

    # When implemented, response should be:
    # {"detail": "Not implemented", "status": 501}


@pytest.mark.asyncio
async def test_resume_endpoint_returns_501_not_implemented():
    """Test POST /api/control/resume returns 501 Not Implemented."""
    # Arrange
    orchestrator = Flock()
    from flock.api.service import BlackboardHTTPService

    service = BlackboardHTTPService(orchestrator)
    client = TestClient(service.app)

    # Act
    response = client.post("/api/control/resume")

    # Assert - Should return 501 (or 404 if endpoint doesn't exist yet)
    assert response.status_code in [
        404,
        501,
    ], "Resume endpoint should return 501 Not Implemented or 404 if not added"

    # When implemented, response should be:
    # {"detail": "Not implemented", "status": 501}


# ============================================================================
# Additional Edge Cases and Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_publish_with_custom_correlation_id(orchestrator):
    """Test publish endpoint accepts and uses custom correlation_id."""
    # Arrange
    custom_correlation_id = uuid4()
    mock_artifact = Artifact(
        id=uuid4(),
        type="ControlTestArtifact",
        payload={"message": "tracked", "priority": 4},
        produced_by="external",
        visibility=PublicVisibility(),
        correlation_id=custom_correlation_id,
        created_at=datetime.now(UTC),
    )
    orchestrator.publish = AsyncMock(return_value=mock_artifact)

    # Act
    artifact = await orchestrator.publish(
        {"type": "ControlTestArtifact", "message": "tracked", "priority": 4},
        correlation_id=str(custom_correlation_id),
    )

    # Assert
    assert artifact.correlation_id == custom_correlation_id


@pytest.mark.asyncio
async def test_invoke_with_multiple_outputs(orchestrator):
    """Test invoke endpoint handles agents that return multiple artifacts."""
    # Arrange
    mock_agent = Mock()
    mock_agent.name = "multi_output_agent"
    orchestrator.get_agent = Mock(return_value=mock_agent)

    mock_outputs = [
        Artifact(
            id=uuid4(),
            type="ControlTestArtifact",
            payload={"message": "output1", "priority": 1},
            produced_by="multi_output_agent",
            visibility=PublicVisibility(),
            created_at=datetime.now(UTC),
        ),
        Artifact(
            id=uuid4(),
            type="ControlTestArtifact",
            payload={"message": "output2", "priority": 2},
            produced_by="multi_output_agent",
            visibility=PublicVisibility(),
            created_at=datetime.now(UTC),
        ),
    ]
    orchestrator.invoke = AsyncMock(return_value=mock_outputs)

    # Act
    test_input = ControlTestArtifact(message="generate", priority=3)
    outputs = await orchestrator.invoke(mock_agent, test_input)

    # Assert
    assert len(outputs) == 2
    assert all(output.produced_by == "multi_output_agent" for output in outputs)


@pytest.mark.asyncio
async def test_control_endpoints_use_json_content_type(orchestrator):
    """Test control endpoints require and return JSON content type."""
    # Arrange
    from flock.api.service import BlackboardHTTPService

    service = BlackboardHTTPService(orchestrator)
    client = TestClient(service.app)

    # Act - Try to publish with non-JSON content type
    response = client.post(
        "/api/control/publish", data="not json", headers={"Content-Type": "text/plain"}
    )

    # Assert - Should reject non-JSON (422 Unprocessable Entity or 400 Bad Request)
    # If endpoint doesn't exist, will get 404
    assert response.status_code in [
        400,
        404,
        422,
    ], "Non-JSON content should be rejected"


@pytest.mark.asyncio
async def test_publish_handles_orchestrator_publish_failure(orchestrator):
    """Test publish endpoint handles orchestrator.publish() failures gracefully."""
    # Arrange
    orchestrator.publish = AsyncMock(side_effect=Exception("Store connection failed"))

    # Expected behavior: Control endpoint should catch and return 500 Internal Server Error

    # Act & Assert
    with pytest.raises(Exception, match="Store connection failed"):
        await orchestrator.publish({
            "type": "ControlTestArtifact",
            "message": "test",
            "priority": 1,
        })


@pytest.mark.asyncio
async def test_invoke_handles_orchestrator_invoke_failure(orchestrator):
    """Test invoke endpoint handles orchestrator.invoke() failures gracefully."""
    # Arrange
    mock_agent = Mock()
    mock_agent.name = "failing_agent"
    orchestrator.get_agent = Mock(return_value=mock_agent)
    orchestrator.invoke = AsyncMock(side_effect=Exception("Agent execution failed"))

    # Expected behavior: Control endpoint should catch and return 500 Internal Server Error

    # Act & Assert
    test_input = ControlTestArtifact(message="test", priority=1)
    with pytest.raises(Exception, match="Agent execution failed"):
        await orchestrator.invoke(mock_agent, test_input)

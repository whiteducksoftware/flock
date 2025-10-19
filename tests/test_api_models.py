"""Comprehensive tests for API response models with edge cases.

Tests the new Pydantic response models to ensure they handle all edge cases
properly, including None values, empty lists, and validation errors.
"""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from flock import Flock
from flock.api.models import (
    Agent,
    AgentListResponse,
    AgentSubscription,
    ArtifactListResponse,
    ArtifactPublishResponse,
    ArtifactTypesResponse,
    HealthResponse,
    PaginationInfo,
)
from flock.api.service import BlackboardHTTPService
from flock.examples import Idea, Movie


class TestAgentModels:
    """Test Agent-related response models."""

    def test_agent_with_empty_description(self):
        """Agent should accept empty string description."""
        agent = Agent(
            name="test_agent",
            description="",
            subscriptions=[],
            outputs=[],
        )
        assert agent.description == ""

    def test_agent_with_none_description_converts_to_empty(self):
        """Test that None description is handled in endpoint (not in model)."""
        # The model requires a string, so we test the endpoint handles None
        flock = Flock()

        # Create agent with None description
        flock.agent("test_agent").consumes(Idea).publishes(Movie)

        service = BlackboardHTTPService(flock)
        client = TestClient(service.app)

        response = client.get("/api/v1/agents")
        assert response.status_code == 200
        data = response.json()

        # Should have converted None to empty string
        agent_data = next(a for a in data["agents"] if a["name"] == "test_agent")
        assert agent_data["description"] == ""

    def test_agent_with_empty_subscriptions(self):
        """Agent should accept empty subscriptions list."""
        agent = Agent(
            name="test_agent",
            description="Test",
            subscriptions=[],
            outputs=["OutputType"],
        )
        assert agent.subscriptions == []

    def test_agent_with_empty_outputs(self):
        """Agent should accept empty outputs list."""
        agent = Agent(
            name="test_agent",
            description="Test",
            subscriptions=[],
            outputs=[],
        )
        assert agent.outputs == []

    def test_agent_list_response_empty(self):
        """AgentListResponse should handle empty agent list."""
        response = AgentListResponse(agents=[])
        assert response.agents == []

    def test_agent_subscription_model(self):
        """Test AgentSubscription model."""
        subscription = AgentSubscription(
            types=["TypeA", "TypeB"],
            mode="both",
        )
        assert subscription.types == ["TypeA", "TypeB"]
        assert subscription.mode == "both"


class TestArtifactModels:
    """Test Artifact-related response models."""

    def test_artifact_publish_response(self):
        """Test ArtifactPublishResponse model."""
        response = ArtifactPublishResponse(status="accepted")
        assert response.status == "accepted"

    def test_artifact_publish_response_only_accepts_accepted(self):
        """Test that ArtifactPublishResponse only accepts 'accepted'."""
        # Should work
        response = ArtifactPublishResponse(status="accepted")
        assert response.status == "accepted"

        # Should fail with wrong value
        with pytest.raises(ValidationError):
            ArtifactPublishResponse(status="rejected")

    def test_artifact_list_response_empty(self):
        """Test ArtifactListResponse with empty items."""
        response = ArtifactListResponse(
            items=[],
            pagination=PaginationInfo(limit=50, offset=0, total=0),
        )
        assert response.items == []
        assert response.pagination.total == 0

    def test_pagination_info(self):
        """Test PaginationInfo model."""
        pagination = PaginationInfo(limit=50, offset=100, total=500)
        assert pagination.limit == 50
        assert pagination.offset == 100
        assert pagination.total == 500


class TestHealthModel:
    """Test Health response model."""

    def test_health_response(self):
        """Test HealthResponse model."""
        response = HealthResponse(status="ok")
        assert response.status == "ok"

    def test_health_response_only_accepts_ok(self):
        """Test that HealthResponse only accepts 'ok'."""
        # Should work
        response = HealthResponse(status="ok")
        assert response.status == "ok"

        # Should fail with wrong value
        with pytest.raises(ValidationError):
            HealthResponse(status="error")


class TestArtifactTypesResponse:
    """Test ArtifactTypesResponse model."""

    def test_artifact_types_response_empty(self):
        """Test with empty artifact types list."""
        response = ArtifactTypesResponse(artifact_types=[])
        assert response.artifact_types == []

    def test_artifact_type_schema_with_alias(self):
        """Test that 'schema' field alias works properly."""
        from flock.api.models import ArtifactTypeSchema

        # Should work with 'schema' key
        type_schema = ArtifactTypeSchema(
            name="TestType",
            schema={"type": "object", "properties": {}},
        )
        assert type_schema.name == "TestType"
        assert type_schema.schema_ == {"type": "object", "properties": {}}


class TestEndToEndAPIResponses:
    """Test actual API endpoints return proper response models."""

    def test_get_agents_endpoint_returns_proper_model(self):
        """Test GET /api/v1/agents returns AgentListResponse."""
        flock = Flock()

        flock.agent("test_agent").consumes(Idea).publishes(Movie)

        service = BlackboardHTTPService(flock)
        client = TestClient(service.app)

        response = client.get("/api/v1/agents")
        assert response.status_code == 200

        # Validate against Pydantic model
        data = AgentListResponse(**response.json())
        assert len(data.agents) == 1
        assert data.agents[0].name == "test_agent"

    def test_post_artifacts_endpoint_returns_proper_model(self):
        """Test POST /api/v1/artifacts returns ArtifactPublishResponse."""
        flock = Flock()
        service = BlackboardHTTPService(flock)
        client = TestClient(service.app)

        response = client.post(
            "/api/v1/artifacts",
            json={
                "type": "flock.examples.Idea",
                "payload": {"genre": "action", "topic": "Test"},
            },
        )
        assert response.status_code == 200

        # Validate against Pydantic model
        data = ArtifactPublishResponse(**response.json())
        assert data.status == "accepted"

    def test_get_artifacts_endpoint_returns_proper_model(self):
        """Test GET /api/v1/artifacts returns ArtifactListResponse."""
        flock = Flock()
        service = BlackboardHTTPService(flock)
        client = TestClient(service.app)

        response = client.get("/api/v1/artifacts?limit=10")
        assert response.status_code == 200

        # Validate against Pydantic model
        data = ArtifactListResponse(**response.json())
        assert isinstance(data.items, list)
        assert isinstance(data.pagination, PaginationInfo)

    def test_get_health_endpoint_returns_proper_model(self):
        """Test GET /health returns HealthResponse."""
        flock = Flock()
        service = BlackboardHTTPService(flock)
        client = TestClient(service.app)

        response = client.get("/health")
        assert response.status_code == 200

        # Validate against Pydantic model
        data = HealthResponse(**response.json())
        assert data.status == "ok"

    def test_openapi_schema_has_proper_refs(self):
        """Test that OpenAPI schema has proper $ref to response models."""
        flock = Flock()
        service = BlackboardHTTPService(flock)

        openapi_schema = service.app.openapi()

        # Check /api/v1/agents
        agents_schema = openapi_schema["paths"]["/api/v1/agents"]["get"]["responses"][
            "200"
        ]
        assert "$ref" in agents_schema["content"]["application/json"]["schema"]
        assert (
            "AgentListResponse"
            in agents_schema["content"]["application/json"]["schema"]["$ref"]
        )

        # Check /api/v1/artifacts POST
        artifacts_post_schema = openapi_schema["paths"]["/api/v1/artifacts"]["post"][
            "responses"
        ]["200"]
        assert "$ref" in artifacts_post_schema["content"]["application/json"]["schema"]
        assert (
            "ArtifactPublishResponse"
            in artifacts_post_schema["content"]["application/json"]["schema"]["$ref"]
        )

        # Check /health
        health_schema = openapi_schema["paths"]["/health"]["get"]["responses"]["200"]
        assert "$ref" in health_schema["content"]["application/json"]["schema"]
        assert (
            "HealthResponse"
            in health_schema["content"]["application/json"]["schema"]["$ref"]
        )

    def test_openapi_schema_components_defined(self):
        """Test that all response model components are properly defined."""
        flock = Flock()
        service = BlackboardHTTPService(flock)

        openapi_schema = service.app.openapi()
        schemas = openapi_schema["components"]["schemas"]

        # Check that our models are defined
        required_schemas = [
            "AgentListResponse",
            "Agent",
            "AgentSubscription",
            "ArtifactListResponse",
            "ArtifactPublishResponse",
            "HealthResponse",
            "PaginationInfo",
        ]

        for schema_name in required_schemas:
            assert schema_name in schemas, (
                f"Schema {schema_name} not found in components"
            )

            # Ensure no generic additionalProperties: true
            schema_def = schemas[schema_name]
            if "additionalProperties" in schema_def:
                # It's ok if it's False or a schema, but not True
                assert schema_def["additionalProperties"] != True, (
                    f"Schema {schema_name} has additionalProperties: true"
                )


class TestEdgeCasesAndValidation:
    """Test edge cases and validation errors."""

    def test_agent_requires_name(self):
        """Test that Agent model requires name field."""
        with pytest.raises(ValidationError) as exc_info:
            Agent(
                description="Test",
                subscriptions=[],
                outputs=[],
            )
        assert "name" in str(exc_info.value)

    def test_artifact_list_response_requires_pagination(self):
        """Test that ArtifactListResponse requires pagination."""
        with pytest.raises(ValidationError) as exc_info:
            ArtifactListResponse(items=[])
        assert "pagination" in str(exc_info.value)

    def test_health_response_only_literal_ok(self):
        """Test that HealthResponse only accepts literal 'ok'."""
        # Valid
        HealthResponse(status="ok")

        # Invalid
        with pytest.raises(ValidationError):
            HealthResponse(status="healthy")

    def test_artifact_publish_response_only_literal_accepted(self):
        """Test that ArtifactPublishResponse only accepts literal 'accepted'."""
        # Valid
        ArtifactPublishResponse(status="accepted")

        # Invalid
        with pytest.raises(ValidationError):
            ArtifactPublishResponse(status="pending")

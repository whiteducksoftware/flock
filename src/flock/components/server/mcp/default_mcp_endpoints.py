from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pydantic import ValidationError

from flock.api.models import (
    Agent,
    AgentListResponse,
    AgentSubscription,
    ArtifactPublishRequest,
    ArtifactSummaryRequest,
    ArtifactValidationResponse,
    ConsumptionRecord,
)
from flock.api.websocket import WebSocketManager
from flock.components.server.artifacts.models import (
    ArtifactListRequest,
)
from flock.components.server.models.events import MessagePublishedEvent, VisibilitySpec
from flock.components.server.models.models import (
    AgentInvokation,
    ArtifactResult,
    MCPAgentInvokationResponse,
    MCPArtifactListResponse,
    MCPArtifactPublishResponse,
    MCPArtifactResponse,
    MCPArtifactSchemaResponse,
    MCPArtifactSummaryResponse,
    MCPArtifactTypeNamesResponse,
    MCPWorkflowStatusResponse,
)
from flock.core.store import ArtifactEnvelope, FilterConfig
from flock.logging.logging import FlockLogger
from flock.registry import type_registry


if TYPE_CHECKING:
    from fastapi import FastAPI

    from flock.core import Flock


def _make_filter_config(filter: ArtifactListRequest) -> FilterConfig:
    return FilterConfig(
        type_names=set(filter.type_names) if filter.type_names else None,
        produced_by=set(filter.produced_by) if filter.produced_by else None,
        correlation_id=filter.correlation_id,
        tags=None,
        visibility=["Public"],
        start=None,
        end=None,
    )


def _serialize_artifact(
    artifact, consumptions: list[ConsumptionRecord] | None = None
) -> dict[str, Any]:
    data = {
        "id": str(artifact.id),
        "type": artifact.type,
        "payload": artifact.payload,
        "produced_by": artifact.produced_by,
        "visibility": artifact.visibility.model_dump(mode="json"),
        "visibility_kind": getattr(artifact.visibility, "kind", "Unknown"),
        "created_at": artifact.created_at.isoformat(),
        "correlation_id": str(artifact.correlation_id)
        if artifact.correlation_id
        else None,
        "partition_key": artifact.partition_key,
        "tags": sorted(artifact.tags),
        "version": artifact.version,
    }
    if consumptions is not None:
        data["consumptions"] = [
            {
                "artifact_id": str(record.artifact_id),
                "consumer": record.consumer,
                "run_id": record.run_id,
                "correlation_id": record.correlation_id,
                "consumed_at": record.consumed_at.isoformat(),
            }
            for record in consumptions
        ]
        data["consumed_by"] = sorted({record.consumer for record in consumptions})
    return data


def register_default_validate_artifact_schema_route(
    app: "FastAPI",
    orchestrator: "Flock",
    path: str,
    tags: list[str],
    operation_id: str,
    logger: FlockLogger,
):
    """Register the default validate artifact route."""

    @app.post(
        path,
        tags=tags,
        operation_id=operation_id,
        summary="Validate artifact schema before publishing to the blackboard",
        description=(
            "Validates that an artifact conforms to its registered schema in the Flock system. "
            "Use this to verify artifact structure before publishing to prevent errors."
        ),
        response_model=ArtifactValidationResponse,
    )
    async def validate_artifact_schema(
        body: ArtifactPublishRequest,
    ) -> ArtifactValidationResponse:
        """Validate an artifact schema before publishing to the Blackboard.

        **About Flock's Blackboard System:**
        Flock uses a blackboard architecture where AI agents collaborate through a shared workspace.
        Agents publish typed artifacts (structured data objects) to the blackboard, and other agents
        subscribe to specific artifact types they can process. This creates emergent workflows without
        direct agent-to-agent coupling.

        **What This Tool Does:**
        Validates that a proposed artifact:
        1. Has a type name that is registered in the Flock type registry
        2. Contains a valid payload with all required fields
        3. Has correct field types according to the Pydantic schema
        4. Would be accepted if published to the blackboard

        **When to Use:**
        - Before publishing artifacts to avoid validation errors
        - To verify you have the correct field names and types
        - To test artifact construction without triggering agent workflows
        - To reduce failed publish attempts and improve reliability

        **Args:**
            body: ArtifactPublishRequest containing:
                - type: The artifact type name (e.g., "MyDreamPizza")
                - payload: Dictionary of field values matching the schema

        **Returns:**
            ArtifactValidationResponse with:
                - acceptable (bool): Whether the artifact is valid
                - reason (str): Explanation of validation result or error details
        """
        try:
            artifact_type = body.type
            payload = body.payload
            if not artifact_type or artifact_type == "":
                logger.exception("MCPServerComponent: Validation")
                return ArtifactValidationResponse(
                    acceptable=False,
                    reason="TypeName must be included. Cannot be null/None or empty string.",
                )
            if payload is None:
                return ArtifactValidationResponse(
                    acceptable=False, reason="Payload cannot be null/None."
                )
            try:
                # Resolve type from registry
                model_class = type_registry.resolve(artifact_type)
            except KeyError:
                logger.exception(
                    f"MCPServerComponent: Unable to resolve artifact type for type_name: {artifact_type}"
                )
                return ArtifactValidationResponse(
                    acceptable=False,
                    reason=f"Unable to resolve TypeName for artifact. TypeName {artifact_type} not known.",
                )
            # Validate instance creation
            try:
                _ = model_class(**payload)
            except ValidationError as valex:
                logger.exception(
                    f"Unable to validate payload for type: {artifact_type}: {valex!s}"
                )
                return ArtifactValidationResponse(
                    acceptable=False,
                    reason=f"Validation error for payload for ArtifactType: {artifact_type}: {valex!s}",
                )
            return ArtifactValidationResponse(
                acceptable=True,
                reason="Validation successful. Artifact would be acceptable in given form.",
            )
        except Exception as ex:
            logger.exception(
                f"MCPServerComponent: Exception occurred during TypeValidation for Artifact: {artifact_type}: {ex!s}"
            )
            return ArtifactValidationResponse(
                acceptable=False, reason=f"Validation failed. Error: {ex!s}"
            )


def register_default_get_artifact_schema_route(
    app: "FastAPI",
    orchestrator: "Flock",
    path: str,
    tags: list[str],
    operation_id: str,
    logger: FlockLogger,
):
    """Register the default get artifact schema route."""

    @app.post(
        path,
        tags=tags,
        operation_id=operation_id,
        summary="Get the Pydantic schema for a registered artifact type",
        description=(
            "Retrieves the complete JSON schema for any artifact type registered in the Flock system. "
            "Essential for understanding what fields and types an artifact requires."
        ),
        response_model=MCPArtifactSchemaResponse,
    )
    async def get_artifact_schema(artifact_type_name: str) -> MCPArtifactSchemaResponse:
        """Get the complete schema for a registered artifact type.

        **About Artifact Types in Flock:**
        Artifacts are strongly-typed data objects (Pydantic models) that agents produce and consume.
        Each artifact type has a schema that defines:
        - Required and optional fields
        - Field types (string, integer, nested objects, etc.)
        - Validation rules and constraints
        - Documentation for each field

        **What This Tool Does:**
        Returns the full JSON Schema (based on Pydantic models) for a given artifact type name.
        This schema shows you exactly what structure the artifact expects, which is essential for:
        - Understanding what data to provide when publishing artifacts
        - Knowing what fields will be available when consuming artifacts
        - Discovering the structure of agent inputs and outputs

        **Workflow:**
        1. Use `get_artifact_type_names` to see all available types
        2. Use this tool to get the schema for specific types of interest
        3. Use the schema to construct valid artifact payloads
        4. Use `validate_artifact_schema` to verify your payload before publishing

        **Args:**
            artifact_type_name: The registered type name (e.g., "Pizza", "Review", "CustomerRequest")

        **Returns:**
            On success:
                {
                    "artifact_schema": {
                        "type_name": "TypeName",
                        "schema": {<JSON Schema object with properties, required fields, etc.>}
                    }
                }
            On error:
                {
                    "error": true,
                    "reason": "Unable to resolve Artifact-Schema for TypeName: ... No such Type is known."
                }
        """
        # Registry look-up to determine if TypeName is actually registered
        try:
            registered_type = type_registry.resolve(type_name=artifact_type_name)
            schema = registered_type.model_json_schema()
            return MCPArtifactSchemaResponse(
                success=True,
                type_name=artifact_type_name,
                artifact_schema=schema,
                error_message=None,
            )
        except KeyError as ex:
            logger.exception(
                f"MCPServerComponent: No Type with TypeName {artifact_type_name} registered: {ex!s}"
            )
            return MCPArtifactSchemaResponse(
                success=False,
                type_name=None,
                artifact_schema=None,
                error_message=f"Unable to resolve Artifact-Schema for TypeName: {artifact_type_name}. No such Type is known.",
            )


def register_default_list_artifact_type_names_route(
    app: "FastAPI",
    orchestrator: "Flock",
    path: str,
    tags: list[str],
    operation_id: str,
    logger: FlockLogger,
):
    """Register the default list artifact type names route."""

    @app.get(
        path,
        tags=tags,
        operation_id=operation_id,
        summary="List all publicly available artifact type names in the system",
        description=(
            "Returns a list of all artifact type names that can be published to the blackboard. "
            "Use this to discover what types of data the system accepts."
        ),
        response_model=MCPArtifactTypeNamesResponse,
    )
    async def get_artifact_type_names() -> MCPArtifactTypeNamesResponse:
        """Get all registered artifact type names available in the Flock system.

        **About the Type Registry:**
        Flock maintains a registry of all artifact types (Pydantic models) that agents can produce
        and consume. This registry ensures type safety and enables automatic agent subscription
        matching based on types.

        **What This Tool Does:**
        Returns a list of all artifact type names that are:
        - Publicly visible (can be used by external clients)
        - Registered in the type registry
        - Available for publishing to the blackboard
        - Consumable by one or more agents

        This is typically the first tool you'll use when exploring a Flock system, as it shows
        you what types of data you can work with.

        **Workflow:**
        1. Call this tool to get all available type names
        2. Use `get_artifact_schema` to examine specific types that interest you
        3. Use `list_available_agents` to see which agents consume/produce these types
        4. Construct and publish artifacts of the appropriate types

        **Note:**
        Internal system types (like WorkflowError) are filtered out, as these are used
        internally and should not be published by external clients.

        **Returns:**
            On success:
                {
                    "type_names": ["Pizza", "Review", "CustomerRequest", ...]
                }
            On error:
                {
                    "reason": "Unable to retrieve Artifact type names. Error: ..."
                }
        """
        try:
            # Get all registered Artifact Types
            type_names_dict = type_registry._by_name
            type_names = list(type_names_dict.keys())

            from flock.models.system_artifacts import WorkflowError

            workflow_error_type = type_registry.name_for(WorkflowError)

            # filter artifacts
            filtered_names = [
                name for name in type_names if name != workflow_error_type
            ]
            return MCPArtifactTypeNamesResponse(
                success=True,
                type_names=filtered_names,
                error_message=None,
            )
        except Exception as ex:
            logger.exception(
                f"MCPServerComponent: Unable to retireve Artifact type names: {ex!s}"
            )
            return MCPArtifactTypeNamesResponse(
                success=False,
                type_names=None,
                error_message=f"Unable to retrieve Artifact type names. Error: {ex!s}",
            )


def register_default_get_artifact_by_id_route(
    app: "FastAPI",
    orchestrator: "Flock",
    path: str,
    tags: list[str],
    operation_id: str,
    logger: FlockLogger,
):
    """Register the default get_artifact endpoint."""

    @app.post(
        path,
        tags=tags,
        operation_id=operation_id,
        summary="Retrieve a specific artifact from the blackboard by its ID",
        description=(
            "Fetches the complete artifact data including payload, metadata, and consumption history. "
            "Use this to inspect artifacts produced during workflow execution."
        ),
        response_model=MCPArtifactResponse,
    )
    async def get_artifact(artifact_id: str) -> MCPArtifactResponse:
        """Get a specific artifact by its unique ID.

        **About Artifacts on the Blackboard:**
        Every artifact published to the blackboard receives a unique ID and is stored with:
        - Full payload data
        - Metadata (producer, timestamp, visibility, tags)
        - Correlation ID linking it to a workflow
        - Consumption records showing which agents processed it

        **What This Tool Does:**
        Retrieves the complete artifact data by ID, including:
        - id: Unique identifier
        - type: Artifact type name
        - payload: The actual data (fields and values)
        - produced_by: Which agent created it (or "external" if published by a client)
        - visibility: Access control settings
        - created_at: Timestamp when published
        - correlation_id: Workflow UUID this artifact belongs to
        - tags: Optional labels for filtering/categorization
        - consumed_by: List of agents that processed this artifact

        **When to Use:**
        - After getting workflow status, to retrieve final results
        - To inspect intermediate artifacts in a workflow
        - To debug why certain agents triggered or didn't trigger
        - To examine the exact data that was produced by an agent

        **Args:**
            artifact_id: The unique ID of the artifact (obtained from publish responses,
                        workflow queries, or artifact listings)

        **Returns:**
            On success: Full artifact object with all fields
            On error:
                {
                    "error": true,
                    "reason": "Artifact with id ... not Found" | "Unable to retrieve artifact..."
                }
        """
        try:
            artifact = await orchestrator.store.get(artifact_id)
            if artifact is None:
                return MCPArtifactResponse(
                    success=False,
                    artifact=None,
                    error_message=f"Artifact with id {artifact_id} not Found",
                )
            return MCPArtifactResponse(
                success=True,
                artifact=_serialize_artifact(artifact=artifact),
                error_message=None,
            )
        except Exception as ex:
            logger.exception(
                f"MCPServerComponent: Unable to retrieve artifact with id {artifact_id}. Error: {ex!s}"
            )
            return MCPArtifactResponse(
                success=False,
                artifact=None,
                error_message=f"Unable to retrieve artifact with id {artifact_id}. Error: {ex!s}",
            )


def register_default_summarize_artifacts_route(
    app: "FastAPI",
    orchestrator: "Flock",
    path: str,
    tags: list[str],
    operation_id: str,
    logger: FlockLogger,
):
    """Register the default summarize artifacts endpoint."""

    @app.post(
        path,
        tags=tags,
        operation_id=operation_id,
        summary="Get aggregated statistics about artifacts on the blackboard",
        description=(
            "Returns summary statistics (counts by type, producer, etc.) for artifacts matching "
            "the filter criteria. Useful for understanding workflow progress without fetching all data."
        ),
        response_model=MCPArtifactSummaryResponse,
    )
    async def summarize_artifacts(
        summary_request: ArtifactSummaryRequest,
    ) -> MCPArtifactSummaryResponse:
        """Get aggregated statistics about artifacts on the blackboard.

        **About Workflow Tracking:**
        As agents execute in a Flock workflow, they produce artifacts that accumulate on the
        blackboard. Instead of retrieving all artifacts (which can be large), this tool provides
        summary statistics to understand workflow progress and scope.

        **What This Tool Does:**
        Returns aggregated counts and statistics for artifacts matching your filter criteria:
        - Count of artifacts by type
        - Count of artifacts by producing agent
        - Total artifact count
        - Distribution across correlation IDs (workflows)

        **Filter Options:**
        - type_names: Only count artifacts of specific types (e.g., ["Pizza", "Review"])
        - produced_by: Only count artifacts from specific agents (e.g., ["pizza_master", "reviewer"])
        - correlation_id: Only count artifacts from a specific workflow

        **When to Use:**
        - To check workflow progress without downloading full artifact payloads
        - To see how many artifacts of each type have been produced
        - To verify which agents have executed in a workflow
        - To get an overview before deciding which artifacts to fetch in detail

        **Performance:**
        This is much faster than `list_artifacts` when you only need counts, as it doesn't
        transfer full payload data.

        **Args:**
            summary_request: ArtifactSummaryRequest with optional filters:
                - type_names (optional): List of type names to include
                - produced_by (optional): List of agent names to include
                - correlation_id (optional): Specific workflow UUID

        **Returns:**
            On success:
                {
                    "summary": {
                        "total_count": 42,
                        "by_type": {"Pizza": 10, "Review": 20, ...},
                        "by_producer": {"pizza_master": 10, "reviewer": 20, ...}
                    }
                }
            On error:
                {
                    "reason": "Unable to summarize artifacts: ..."
                }
        """
        try:
            filters = _make_filter_config(
                ArtifactListRequest(
                    type_names=summary_request.type_names,
                    produced_by=summary_request.produced_by,
                    correlation_id=summary_request.correlation_id
                    if summary_request.correlation_id
                    else "",
                )
            )
            summary = await orchestrator.store.summarize_artifacts(filters)
            return MCPArtifactSummaryResponse(
                success=True,
                summary=summary,
                error_message=None,
            )
        except Exception as ex:
            logger.exception(
                f"MCPServerComponent: Unable to summarize artifacts: {ex!s}"
            )
            return MCPArtifactSummaryResponse(
                success=False,
                summary=None,
                error_message=f"Unable to summarize artifacts: {ex!s}",
            )


def register_default_list_artifacts_route(
    app: "FastAPI",
    orchestrator: "Flock",
    path: str,
    tags: list[str],
    operation_id: str,
    logger: FlockLogger,
):
    """Register the list artifacts endpoint."""

    @app.post(
        path,
        response_model=MCPArtifactListResponse,
        tags=tags,
        operation_id=operation_id,
        summary="Query and retrieve artifacts from the blackboard with filtering and pagination",
        description=(
            "Returns a filtered, paginated list of artifacts with their full payloads and metadata. "
            "Use this to retrieve actual artifact data after checking workflow status."
        ),
    )
    async def list_artifacts(
        artifact_filter: ArtifactListRequest,
    ) -> MCPArtifactListResponse:
        """Query and retrieve artifacts from the blackboard with comprehensive filtering.

        **About Blackboard Persistence:**
        All artifacts published to the blackboard are persisted and can be queried later.
        This enables you to:
        - Retrieve workflow results after completion
        - Inspect intermediate processing steps
        - Analyze which agents participated in a workflow
        - Debug why certain behaviors occurred

        **What This Tool Does:**
        Returns a list of artifacts matching your filter criteria, with full payload data
        and metadata. Unlike `summarize_artifacts` which only returns counts, this tool
        provides the actual artifact data you can use.

        **Filter Criteria (all optional, combine with AND logic):**
        - type_names: Only artifacts of these types (e.g., ["Pizza", "Review"])
        - produced_by: Only artifacts from these agents (e.g., ["pizza_master"])
        - correlation_id: Only artifacts from a specific workflow UUID

        **Pagination:**
        - limit: Maximum number of artifacts to return (default: 100)
        - offset: Number of artifacts to skip (for subsequent pages)

        **Each Artifact Includes:**
        - id: Unique identifier
        - type: Artifact type name
        - payload: Full data with all fields
        - produced_by: Creating agent name (or "external")
        - visibility: Access control settings
        - created_at: ISO timestamp
        - correlation_id: Workflow UUID
        - tags: Optional labels
        - consumed_by: List of agents that processed this artifact
        - consumptions: Detailed consumption records with timestamps

        **Common Workflows:**
        1. Publish artifact → Get correlation_id
        2. Poll workflow status until "completed"
        3. List artifacts with correlation_id filter
        4. Process results from final artifacts

        **Args:**
            artifact_filter: ArtifactListRequest with:
                - type_names (optional): Filter by type
                - produced_by (optional): Filter by producer
                - correlation_id (optional): Filter by workflow
                - limit (default: 100): Max results to return
                - offset (default: 0): Results to skip

        **Returns:**
            On success:
                {
                    "items": [<artifact objects with full data>],
                    "pagination": {
                        "limit": 100,
                        "offset": 0,
                        "total": 250  // Total matching artifacts
                    }
                }
            On error:
                {
                    "reason": "Error while trying to create list for artifacts: ..."
                }
        """
        filters = _make_filter_config(artifact_filter)
        try:
            artifacts, total = await orchestrator.store.query_artifacts(
                filters,
                limit=artifact_filter.limit,
                offset=artifact_filter.offset,
                embed_meta=False,
            )
            items: list[dict[str, Any]] = []
            for artifact in artifacts:
                if isinstance(artifact, ArtifactEnvelope):
                    items.append(
                        _serialize_artifact(artifact.artifact, artifact.consumptions)
                    )
                else:
                    items.append(_serialize_artifact(artifact))
            return MCPArtifactListResponse(
                success=True,
                items=items,
                total=total,
                limit=artifact_filter.limit,
                offset=artifact_filter.offset,
                error_message=None,
            )
        except Exception as ex:
            logger.exception(
                f"MCPServerComponent: Error while calling list_artifacts: {ex!s}"
            )
            return MCPArtifactListResponse(
                success=False,
                items=None,
                total=None,
                limit=None,
                offset=None,
                error_message=f"Error while trying to create list for artifacts: {ex!s}",
            )


def register_default_get_workflow_status_route(
    app: "FastAPI",
    orchestrator: "Flock",
    path: str,
    tags: list[str],
    logger: FlockLogger,
    operation_id: str,
):
    """Register the get workflow status endpoint."""

    @app.post(
        path,
        tags=tags,
        operation_id=operation_id,
        summary="Check the execution status of a workflow by its correlation ID",
        description=(
            "Returns whether a workflow is active, completed, or failed. Essential for tracking "
            "asynchronous agent execution after publishing artifacts to the blackboard."
        ),
        response_model=MCPWorkflowStatusResponse,
    )
    async def get_workflow_status(
        correlation_id: str,
    ) -> MCPWorkflowStatusResponse:
        """Get the current execution status of a workflow by its correlation ID.

        **About Workflows in Flock:**
        When you publish an artifact to the blackboard, Flock creates a workflow identified by
        a unique correlation UUID. This workflow tracks all subsequent agent executions triggered
        by that initial artifact and any cascading downstream processing.

        A workflow emerges from:
        1. Initial artifact publication → Gets correlation_id
        2. Agents subscribed to that type activate
        3. They produce output artifacts (with same correlation_id)
        4. Downstream agents trigger on those outputs
        5. Process continues until no more agents can execute

        **What This Tool Does:**
        Checks the current state of a workflow without retrieving all artifact data.
        This is the primary way to know when asynchronous processing has completed.

        **Workflow States:**
        - "active": Agents are currently executing or work is pending
        - "completed": All agents have finished, no more work pending (success)
        - "failed": An error occurred during execution
        - "not_found": No artifacts exist with this correlation_id

        **Additional Information:**
        - has_pending_work: Boolean indicating if the orchestrator has scheduled agents
        - artifact_count: Number of artifacts produced in this workflow
        - agent_executions: Count of how many times agents have executed

        **Typical Usage Pattern:**
        ```
        1. Publish artifact → Receive correlation_id
        2. Poll get_workflow_status(correlation_id) every few seconds
        3. When status == "completed" and has_pending_work == false:
           → Workflow is done, retrieve results with list_artifacts
        4. If status == "failed":
           → Check artifacts for error details
        ```

        **Args:**
            correlation_id: UUID string returned from publish_artifact

        **Returns:**
            On success:
                {
                    "status": "active" | "completed" | "failed" | "not_found",
                    "has_pending_work": true | false,
                    "correlation_id": "uuid-string",
                    "artifact_count": 42,
                    "agent_executions": 15
                }
            On error:
                {
                    "reason": "Failed to retrieve correlation status: ..."
                }
        """
        try:
            status = await orchestrator.get_correlation_status(
                correlation_id=correlation_id
            )
            return MCPWorkflowStatusResponse(
                success=True,
                correlation_id=status.get("correlation_id"),
                state=status.get("state"),
                has_pending_work=status.get("has_pending_work"),
                artifact_count=status.get("artifact_count"),
                error_count=status.get("error_count"),
                started_at=status.get("started_at"),
                last_activity_at=status.get("last_activity_at"),
                error_message=None,
            )
        except ValueError as exc:
            logger.exception(
                f"MCPServerComponent: failed to retrieve correlation status: {exc!s}"
            )
            return MCPWorkflowStatusResponse(
                success=False,
                correlation_id=None,
                state=None,
                has_pending_work=None,
                artifact_count=None,
                error_count=None,
                started_at=None,
                last_activity_at=None,
                error_message=f"Failed to retrieve correlation status: {exc!s}",
            )


def register_default_publish_artifact_route(
    app: "FastAPI",
    orchestrator: "Flock",
    path: str,
    tags: list[str],
    logger: FlockLogger,
    operation_id: str,
    websocket_manager: WebSocketManager,
):
    """Register the publish artifacts endpoint"""

    @app.post(
        path,
        tags=tags,
        operation_id=operation_id,
        summary="Publish an artifact to the blackboard and initiate agent workflow",
        description=(
            "Publishes a typed artifact to Flock's blackboard, triggering all subscribed agents "
            "to process it asynchronously. Returns a correlation ID for tracking the workflow. "
            "This is the primary way to interact with the Flock agent system."
        ),
        response_model=MCPArtifactPublishResponse,
    )
    async def publish_artifact(
        body: ArtifactPublishRequest,
    ) -> MCPArtifactPublishResponse:
        """Publish an artifact to the blackboard and trigger agent workflow execution.

        **FLOCK'S CORE CONCEPT - THE BLACKBOARD PATTERN:**
        Flock uses a blackboard architecture, a pattern from AI research where:
        - A shared workspace (blackboard) holds data (artifacts)
        - Specialized agents monitor the blackboard
        - Agents activate when they see data they can process
        - Agents publish their results back to the blackboard
        - Other agents react to those results, creating emergent workflows
        - No direct agent-to-agent communication needed

        **How Publishing Works:**
        1. You publish a typed artifact (e.g., CustomerRequest, PizzaIdea)
        2. Flock generates a correlation_id to track this workflow
        3. The artifact appears on the blackboard
        4. ALL agents subscribed to that type are triggered automatically
        5. Agents execute in parallel (no sequential bottleneck)
        6. Each agent publishes its output artifacts (with same correlation_id)
        7. Downstream agents trigger on those outputs
        8. Process cascades until no more agents can execute
        9. Workflow reaches "completed" state

        **Why This Pattern:**
        - ✅ Decoupled: Agents don't know about each other
        - ✅ Scalable: New agents can be added without changing existing ones
        - ✅ Parallel: Multiple agents process simultaneously
        - ✅ Emergent: Complex workflows emerge from simple subscriptions
        - ✅ Resilient: Failed agents don't block others

        **Publishing is Asynchronous:**
        This endpoint returns immediately with a correlation_id. It does NOT wait for
        agents to complete processing. Use the correlation_id to:
        - Poll with `get_workflow_status` to know when processing completes
        - Retrieve results with `list_artifacts` when workflow is done

        **Type Safety:**
        The artifact must match a registered Pydantic schema. Use these tools to ensure correctness:
        - `get_artifact_type_names` - See what types are available
        - `get_artifact_schema` - Get the schema for a type
        - `validate_artifact_schema` - Verify before publishing

        **Args:**
            body: ArtifactPublishRequest containing:
                - type: Registered artifact type name (e.g., "CustomerRequest")
                - payload: Dictionary with fields matching the schema

        **Returns:**
            On success:
                {
                    "correlation_id": "uuid-string",  // Use this to track the workflow
                    "published_at": "2025-11-13T10:30:00Z"
                }
            On error:
                {
                    "reason": "No artifact_type has been provided." |
                             "Payload was None." |
                             "Unable to validate payload for type '...':" |
                             "Unknown artifact_type: ..."
                }

        **Example Workflow:**
        ```
        # 1. Publish artifact
        response = publish_artifact({
            "type": "CustomerRequest",
            "payload": {"customer_id": "123", "request": "Order pizza"}
        })
        correlation_id = response["correlation_id"]

        # 2. Poll for completion
        while True:
            status = get_workflow_status(correlation_id)
            if status["status"] == "completed" and not status["has_pending_work"]:
                break
            time.sleep(2)

        # 3. Get results
        results = list_artifacts({
            "correlation_id": correlation_id,
            "limit": 100
        })
        ```
        """
        # Validate required fields
        artifact_type = body.type
        payload = body.payload
        if not artifact_type or artifact_type == "":
            return MCPArtifactPublishResponse(
                success=False,
                correlation_id=None,
                published_at=None,
                error_message="No artifact_type has been provided.",
            )
        if payload is None:
            return MCPArtifactPublishResponse(
                success=False,
                correlation_id=None,
                published_at=None,
                error_message="Payload was None.",
            )
        try:
            # Resolve type from registry
            model_class = type_registry.resolve(artifact_type)
            # Validate payload against pydantic schema
            try:
                instance = model_class(**payload)
            except ValidationError as ex:
                logger.exception(
                    f"MCPServerComponent: failed to validate payload for type '{artifact_type}': {ex!s}"
                )
                return MCPArtifactPublishResponse(
                    success=False,
                    correlation_id=None,
                    published_at=None,
                    error_message=f"Unable to validate payload for type '{artifact_type}': {ex!s}",
                )
            # Generate correlation ID
            correlation_id = str(uuid4())
            # Publish to orchestrator
            artifact = await orchestrator.publish(
                instance,
                correlation_id=correlation_id,
                is_dashboard=True,
            )
            # Phase 11 Fix: Emit message_published event for dashboard visibility
            # This enables virtual "orchestrator" agent to appear in both AgentView and BlackBoardView
            event = MessagePublishedEvent(
                correlation_id=str(artifact.correlation_id),
                artifact_id=str(artifact.id),
                artifact_type=artifact.type,
                produced_by=artifact.produced_by,
                payload=artifact.payload,
                visibility=VisibilitySpec(
                    kind="Public",
                ), # MCP-Published Artifacts are public by default
                tags=list(artifact.tags) if artifact.tags else [],
                version=artifact.version,
                consumers=[],  # Will be populated by subscription matching in frontend
            )
            await websocket_manager.broadcast(event=event)
            return MCPArtifactPublishResponse(
                success=True,
                correlation_id=str(artifact.correlation_id),
                published_at=artifact.created_at.isoformat(),
                error_message=None,
            )
        except KeyError as ke:
            logger.exception(
                f"MCPServerComponent: Unknown artifact type: {artifact_type}: {ke!s}"
            )
            return MCPArtifactPublishResponse(
                success=False,
                correlation_id=None,
                published_at=None,
                error_message=f"Unknown artifact_type: {artifact_type}",
            )
        except Exception as ex:
            logger.exception(f"MCPServerComponent: Error publishing artifact: {ex!s}")
            return MCPArtifactPublishResponse(
                success=False,
                correlation_id=None,
                published_at=None,
                error_message=f"Error publishing artifact: {ex!s}",
            )


def register_default_list_available_agents_route(
    app: "FastAPI",
    orchestrator: "Flock",
    path: str,
    tags: list[str],
    logger: FlockLogger,
    operation_id: str,
    exposed_agents: list[str],
) -> None:
    """Register the list agent endpoint."""

    @app.get(
        path,
        tags=tags,
        operation_id=operation_id,
        summary="List all available agents with their capabilities and subscriptions",
        description=(
            "Returns metadata about all agents in the system, including what artifact types "
            "they consume, what they produce, and their descriptions. Essential for understanding "
            "the agent ecosystem and planning workflows."
        ),
        response_model=AgentListResponse,
    )
    async def list_available_agents() -> AgentListResponse:
        """List all available agents with their input/output types and subscriptions.

        **About Agents in Flock:**
        Agents are autonomous AI components that:
        - Subscribe to specific artifact types they can process (inputs)
        - Execute LLM-based logic to transform data
        - Publish output artifacts of specific types (outputs)
        - Can have multiple subscriptions (consume multiple types)
        - Can produce multiple output types
        - Execute automatically when matching artifacts appear

        **What This Tool Does:**
        Returns comprehensive metadata about all agents available in the system, including:
        - Agent name (unique identifier)
        - Description (what the agent does)
        - Subscriptions (what artifact types trigger this agent)
        - Output types (what artifact types this agent produces)
        - Subscription mode (single vs batch processing)

        **Why This Matters:**
        Understanding the agent ecosystem helps you:
        - Know what artifact types will trigger workflows
        - Predict what outputs you'll get from publishing certain types
        - Plan multi-step workflows by chaining agent capabilities
        - Discover what the system can do without reading source code

        **Agent Subscription Modes:**
        - "single": Agent processes one artifact at a time
        - "batch": Agent can process multiple artifacts together
        - "join": Agent waits for multiple related artifacts before executing

        **Example Response Structure:**
        ```json
        {
            "agents": [
                {
                    "name": "pizza_master",
                    "description": "Transforms pizza ideas into detailed pizza recipes",
                    "subscriptions": [
                        {
                            "types": ["MyDreamPizza"],
                            "mode": "single"
                        }
                    ],
                    "outputs": ["Pizza"]
                },
                {
                    "name": "reviewer",
                    "description": "Reviews and rates pizzas",
                    "subscriptions": [
                        {
                            "types": ["Pizza"],
                            "mode": "single"
                        }
                    ],
                    "outputs": ["Review"]
                }
            ]
        }
        ```

        **How to Use This Information:**
        1. Find agents that consume the artifact types you want to publish
        2. Check what outputs they produce
        3. Trace the chain: Your input → Agent A → Intermediate type → Agent B → Final output
        4. Use `get_artifact_schema` on the input types to understand required fields

        **Note:**
        Only agents exposed through the MCP server configuration are returned.
        Internal system agents may be hidden for security or simplicity.

        **Returns:**
            AgentListResponse with array of agent metadata objects
        """
        logger.info("MCPServerComponent: Client requested a list of available agents.")
        return AgentListResponse(
            agents=[
                Agent(
                    name=agent.name,
                    description=agent.description or "no explicit description found",
                    subscriptions=[
                        AgentSubscription(
                            types=list(subscription.type_names),
                            mode=subscription.mode,
                        )
                        for subscription in agent.subscriptions
                    ],
                    outputs=[output.spec.type_name for output in agent.outputs],
                )
                for agent in orchestrator.agents
                if agent.name in exposed_agents
            ]
        )


def register_default_invokation_route(
    app: "FastAPI",
    orchestrator: "Flock",
    path: str,
    tags: list[str],
    logger: FlockLogger,
    operation_id: str,
) -> None:
    """Register the agent_invokation endpoint."""

    @app.post(
        path,
        tags=tags,
        operation_id=operation_id,
        summary="Directly invoke a specific agent bypassing the blackboard workflow system",
        description=(
            "Executes a single agent synchronously with provided inputs, returning results immediately. "
            "Unlike publish_artifact, this bypasses subscription matching and workflow cascades. "
            "Use for direct request-response patterns or testing individual agents."
        ),
        response_model=MCPAgentInvokationResponse,
    )
    async def invoke_agent(
        invokation: AgentInvokation,
    ) -> MCPAgentInvokationResponse:
        """Directly invoke a specific agent synchronously, bypassing the blackboard system.

        **Direct Invocation vs. Blackboard Publishing:**

        This tool provides a DIFFERENT execution model than `publish_artifact`:

        **publish_artifact (Recommended for workflows):**
        - ✅ Asynchronous, non-blocking
        - ✅ Triggers ALL matching agents automatically
        - ✅ Creates cascading workflows
        - ✅ Parallel agent execution
        - ✅ Persistent correlation tracking
        - ❌ Requires polling for results

        **invoke_agent (Use for direct calls):**
        - ✅ Synchronous, immediate response
        - ✅ Execute one specific agent only
        - ✅ No subscription matching or predicates checked
        - ✅ No workflow tracking or cascades
        - ✅ Simple request-response pattern
        - ❌ No parallel multi-agent processing
        - ❌ Downstream agents don't trigger automatically

        **When to Use Direct Invocation:**
        - Testing individual agent behavior in isolation
        - Simple request-response patterns (like API endpoints)
        - You need immediate synchronous results
        - You want to call a specific agent, not trigger a workflow
        - Debugging agent logic without workflow complexity

        **When to Use Publish Instead:**
        - You want multiple agents to process the same data
        - You need cascading multi-step workflows
        - Asynchronous processing is acceptable
        - You want the full power of the blackboard pattern

        **How Direct Invocation Works:**
        1. You specify the exact agent name
        2. You provide input artifacts (must match agent's expected types)
        3. Agent executes immediately with those inputs
        4. Results are returned synchronously
        5. No other agents are triggered
        6. No workflow tracking or correlation_id

        **Important Notes:**
        - Agent subscription predicates are NOT evaluated (agent runs regardless of filters)
        - Visibility rules are NOT enforced (agent sees provided inputs directly)
        - No cascading to downstream agents (outputs are returned, not published)
        - Useful for testing but bypasses Flock's core architectural benefits

        **Args:**
            invokation: AgentInvokation containing:
                - name: Exact agent name (from list_available_agents)
                - inputs: Array of artifacts with:
                    - type: Artifact type name
                    - payload: Field values matching schema

        **Returns:**
            {
                "success": true,  // or false if failed
                "artifacts": [  // only present when success=true
                    {
                        "id": "uuid",
                        "type": "OutputTypeName",
                        "payload": {<output data>},
                        "produced_by": "agent_name"
                    },
                    ...
                ],
                "error_message": null  // or string explaining error when success=false
            }

        **Example Success:**
        ```json
        // Request
        {
            "name": "pizza_master",
            "inputs": [
                {
                    "type": "MyDreamPizza",
                    "payload": {"pizza_idea": "Spicy Hawaiian with jalapeños"}
                }
            ]
        }

        // Response
        {
            "success": true,
            "artifacts": [
                {
                    "id": "550e8400-...",
                    "type": "Pizza",
                    "payload": {
                        "name": "Spicy Hawaiian Delight",
                        "ingredients": ["pineapple", "ham", "jalapeños", ...],
                        ...
                    },
                    "produced_by": "pizza_master"
                }
            ],
            "error_message": null
        }
        ```

        **Example Error:**
        ```json
        {
            "success": false,
            "artifacts": null,
            "error_message": "Unknown Agent: No Agent with name 'unknown_agent' registered."
        }
        ```
        """
        try:
            logger.info(f"Agent: '{invokation.name}' invoked via MCP.")
            agent = orchestrator.get_agent(name=invokation.name)
            inputs = []
            for item in invokation.inputs:
                try:
                    model = type_registry.resolve(item.type)
                    instance = model(**item.payload)
                    inputs.append(instance)
                    try:
                        outputs = await orchestrator.direct_invoke(
                            agent=agent,
                            inputs=inputs,
                        )
                        return MCPAgentInvokationResponse(
                            success=True,
                            artifacts=[
                                ArtifactResult(
                                    id=str(artifact.id),
                                    type=artifact.type,
                                    payload=artifact.payload,
                                    produced_by=artifact.produced_by,
                                )
                                for artifact in outputs
                            ],
                            error_message=None,
                        )
                    except Exception as execex:
                        logger.exception(
                            f"MCPServerComponent: Agent execution for agent {agent.name} failed: {execex!s}"
                        )
                        return MCPAgentInvokationResponse(
                            success=False,
                            artifacts=None,
                            error_message=f"Agent Execution failed for agent {agent.name}: {execex!s}",
                        )
                except Exception as exc:
                    logger.exception(
                        f"MCPServerComponent: Failed to resolve input type for '{item.type}': {exc!s}"
                    )
                    return MCPAgentInvokationResponse(
                        success=False,
                        artifacts=None,
                        error_message=f"Unable to parse inputs for input: '{item.type}' for agent '{invokation.name}'",
                    )
        except KeyError as ex:
            logger.exception(
                f"MCPServerComponent: Failed to get agent '{invokation.name}': {ex!s}"
            )
            # return an error response to the caller.
            return MCPAgentInvokationResponse(
                success=False,
                artifacts=None,
                error_message=f"Unkown Agent: No Agent with name '{invokation.name}' registered.",
            )

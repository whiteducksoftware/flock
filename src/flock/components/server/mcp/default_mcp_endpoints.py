from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pydantic import ValidationError

from flock.api.models import (
    AgentListResponse,
    ArtifactPublishErrorResponse,
    ArtifactPublishRequest,
    ArtifactPublishTrackingResponse,
    ArtifactSummaryErrorResponse,
    ArtifactSummaryRequest,
    ArtifactSummaryResponse,
    ArtifactTypeNamesErrorResponse,
    ArtifactTypeNamesResponse,
    ArtifactValidationResponse,
    ConsumptionRecord,
    CorrelationStatusErrorResponse,
    CorrelationStatusResponse,
)
from flock.api.websocket import WebSocketManager
from flock.components.server.artifacts.models import (
    ArtifactListRequest,
    ArtifactListRequestError,
    ArtifactListResponse,
)
from flock.components.server.models.events import MessagePublishedEvent, VisibilitySpec
from flock.components.server.models.models import (
    Agent,
    AgentInvokation,
    AgentInvokationError,
    AgentInvokationResult,
    AgentRunResponse,
    AgentSubscription,
    ArtifactResult,
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
        summary="Validate the schema for an artifact.",
        description="Validate the schema for an artifact.",
        response_model=ArtifactValidationResponse,
    )
    async def validate_artifact_schema(
        body: ArtifactPublishRequest,
    ) -> ArtifactValidationResponse:
        """Validate an artifact schema before publishing the Artifact to the BlackBoard.

        This tool can be used to check if a given artifact would be acceptable in its given form.
        This checks if the BlackBoard: a) knows the given Artifact Type, and b) all fields contain
        the correct types and values.
        This Tool can therefore be used to validate a request before publishing it to the BlackBoard,
        allowing the caller to refine and validate calls and reduce the amount of errors.
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
        summary="Get the schema for a given artifact.",
        description="Get the schema for a given artifact.",
        response_model=dict[str, Any],
    )
    async def get_artifact_schema(artifact_type_name: str) -> dict[str, Any]:
        """Get the schema for a registered Artifact by name.

        This tool returns the schema for a Artifact by its TypeName
        that is being used on the BlackBoard.
        Artifacts can be Types that Agents connected to the BlackBoard
        accept (listen to if they are published) and/or produce.

        This tool is useful if the list of available Agents
        and the Artifacts/Events they accept is known, and/or
        the list of ArtifactTypes that are accepted by the BlackBoard
        is known and the schema for a given Artifact needs to be retrieved
        before either invoking an Agent directly or publishing (recommended) an
        Artifact to the BlackBoard for async processing.
        This way, a client/caller/agent does not have to guess or infer
        the ArtifactSchema before publishing to the BlackBoard.

        Returns:
            {
                "artifact_schema": {
                    "type_name": "TypeName",
                    "schema": {...}
                }
            }
        """
        # Registry look-up to determine if TypeName is actually registered
        try:
            registered_type = type_registry.resolve(type_name=artifact_type_name)
            schema = registered_type.model_json_schema()
            return {
                "artifact_schema": {
                    "type_name": artifact_type_name,
                    "schema": schema,
                }
            }
        except KeyError as ex:
            logger.exception(
                f"MCPServerComponent: No Type with TypeName {artifact_type_name} registered: {ex!s}"
            )
            return {
                "error": True,
                "reason": f"Unable to resolve Artifact-Schema for TypeName: {artifact_type_name}. No such Type is known.",
            }


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
        summary="Get all names for publicly visible artifact types.",
        description="Get all names for publicly visible artifact types",
        response_model=ArtifactTypeNamesResponse | ArtifactTypeNamesErrorResponse,
    )
    async def get_artifact_type_names() -> (
        ArtifactTypeNamesResponse | ArtifactTypeNamesErrorResponse
    ):
        """Get all names for the registered types.

        This helper-tool allows the retrieval of a list of all available
        ArtifactTypeNames. This helps in figuring out the schemas
        Artifacts that Agents react to and produce.

        The returned TypeNames list can then be used to look up
        the schema for a specific Artifact Type that a given Agent
        accepts.

        The list of TypeNames returned contains all names for
        ArtifactTypes that are publicly visible, where 'publicly visible'
        means that these types of Artifacts/Events can be retrieved
        by external clients/agents. Internally used types are not returned
        and should not be used by external systems.
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
            return ArtifactTypeNamesResponse(
                type_names=filtered_names,
            )
        except Exception as ex:
            logger.exception(
                f"MCPServerComponent: Unable to retireve Artifact type names: {ex!s}"
            )
            return ArtifactTypeNamesErrorResponse(
                reason=f"Unable to retrieve Artifact type names. Error: {ex!s}"
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
        summary="Get a specific artifact by its artifact ID",
        description="Get a specific artifact by its artifact ID",
    )
    async def get_artifact(artifact_id: str) -> dict[str, Any]:
        """Get a specific artifact by its artifact ID.

        Args:
            artifact_id: the id of the artifact in question.
        """
        try:
            artifact = await orchestrator.store.get(artifact_id)
            if artifact is None:
                return {
                    "error": True,
                    "reason": f"Artifact with id {artifact_id} not Found",
                }
            return _serialize_artifact(artifact=artifact)
        except Exception as ex:
            logger.exception(
                f"MCPServerComponent: Unable to retrieve artifact with id {artifact_id}. Error: {ex!s}"
            )
            return {
                "error": True,
                "reason": f"Unable to retrieve artifact with id {artifact_id}. Error: {ex!s}",
            }


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
        summary="Summarize available artifacts",
        description="Summarize available artifacts",
        response_model=ArtifactSummaryResponse | ArtifactSummaryErrorResponse,
    )
    async def summarize_artifacts(
        summary_request: ArtifactSummaryRequest,
    ) -> ArtifactSummaryResponse | ArtifactSummaryErrorResponse:
        """Summarize Artifacts.

        Allows to optionally filter for type_names, which agents where involved in producing the artifacts, which workflow the artifacts are associated with.
        Returns a summary of all Artifacts matching the provided filter parameters.
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
            return ArtifactSummaryResponse(summary=summary)
        except Exception as ex:
            logger.exception(
                f"MCPServerComponent: Unable to summarize artifacts: {ex!s}"
            )
            return ArtifactSummaryErrorResponse(
                reason=f"Unable to summarize artifacts: {ex!s}"
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
        response_model=ArtifactListResponse | ArtifactListRequestError,
        tags=tags,
        operation_id=operation_id,
        summary="List all artifacts with a given filter.",
    )
    async def list_artifacts(
        artifact_filter: ArtifactListRequest,
    ) -> ArtifactListResponse | ArtifactListRequestError:
        """List all Artifacts that match the filter-criteria."""
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
            return ArtifactListResponse(
                items=items,
                pagination={
                    "limit": artifact_filter.limit,
                    "offset": artifact_filter.offset,
                    "total": total,
                },
            )
        except Exception as ex:
            logger.exception(
                f"MCPServerComponent: Error while calling list_artifacts: {ex!s}"
            )
            return ArtifactListRequestError(
                reason=f"Error while trying to create list for artifacts: {ex!s}"
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
        summary="Get the status of a Workflow with its Correlation UUID.",
        response_model=CorrelationStatusResponse | CorrelationStatusErrorResponse,
    )
    async def get_workflow_status(
        correlation_id: str,
    ) -> CorrelationStatusResponse | CorrelationStatusErrorResponse:
        """Get the status of a workflow by correlation ID.

        Once an artifact is published, a workflow is created with a unique UUID
        that can be used to track the work of the agents as they react to the publication.
        A single Workflow is identified by its UUID and is triggered through the publication
        of an event the the BlackBoard. Individual Agents react to the publication of that
        Event and publish results themselves in turn, which may trigger other agents.

        A Workflow can have several states:
            - 'active' - work is still pending. Agents are actively processing events associated with this Workflow
            - 'completed' - (success) All possible processing steps are completed and there are no more Agents left that could process/publish in the context of the given Workflow
            - 'failed' - An Error occurred during the Workflow
            - 'not_found' - There are no Artifacts associated with the given Workflow UUID
        In addition, the has_pending_work property of the response indicates if the BlackBoard Orchestrator has work (Agents) scheduled for the given Workflow
        This tool is useful for polling to check if a workflow has completed.

        Request-Body:
            {
                "correlation_id": "<uuid>",
            }
        """
        try:
            status = await orchestrator.get_correlation_status(
                correlation_id=correlation_id
            )
            return CorrelationStatusResponse(**status)
        except ValueError as exc:
            logger.exception(
                f"MCPServerComponent: failed to retrieve correlation status: {exc!s}"
            )
            return CorrelationStatusErrorResponse(
                reason=f"Failed to retrieve correlation status: {exc!s}"
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
        summary="Publish an artifact to the blackboard.",
        response_model=ArtifactPublishTrackingResponse | ArtifactPublishErrorResponse,
    )
    async def publish_artifact(
        body: ArtifactPublishRequest,
    ) -> ArtifactPublishTrackingResponse:
        """Publish an artifact to the Blackboard.

        The Blackboard is a shared data store where agents publish and consume artifacts.
        - Agents or External Clients publish Artifacts
        - Agents subscribe to Artifacts they can process
        - Workflows emerge from type-based subscriptions
        - Execution is automatic (matching agents trigger when their data appears.)

        How the blackboard works:
        1. Artifact published -> Appears on Blackboard and a Correlation ID is generated
        2. Matching Agents triggered -> All agents subscribed to that type activate.
        3. Parallel execution -> Multiple agents work concurrently
        4. Results published -> Output artifacts appear on the Blackboard
        5. Cascade continues -> Downstream Agents trigger automatically

        The state of a Workflow that has been created by the publication of
        an Artifact can be queried with its corresponding Correlation ID.
        This method returns such a Correlation ID upon a successful publication
        to the Blackboard which can be used to query the blackboard to get the
        state of a workflow.

        Processing of a published Artifact is asynchronous and does not
        produce a result right away. Use the correlation-id to query the
        blackboard about the status of the workflow triggered by a Artifact publication
        and retrieve relevant produced artifacts upon workflow completion.

        Returns:
            ArtifactPublishTrackingResponse containing the uuid of the workflow and creation date
            ArtifactPublishErrorResponse on error, this contains a reason as to why publication failed

        Example:
            Request-body:
                {
                    "type": "TypeName",
                    "payload": {"field": "value", ...}
                }
            Response:
                {
                    "correlation_id": "uuid-str",
                    "published_at": "iso-timestamp",
                }
        """
        # Validate required fields
        artifact_type = body.type
        payload = body.payload
        if not artifact_type or artifact_type == "":
            return ArtifactPublishErrorResponse(
                reason="No artifact_type has been provided."
            )
        if payload is None:
            return ArtifactPublishErrorResponse(reason="Payload was None.")
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
                return ArtifactPublishErrorResponse(
                    reason=f"Unable to validate payload for type '{artifact_type}': {ex!s}"
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
                artifact_type=artifact_type,
                produced_by=artifact.produced_by,
                visibility=VisibilitySpec(
                    kind="Public",
                ),
                tags=list(artifact.tags) if artifact.tags else [],
                version=artifact.version,
                consumers=[],  # Will be populated by subscription matching in frontend
            )
            await websocket_manager.broadcast(event=event)
            return ArtifactPublishTrackingResponse(
                correlation_id=str(artifact.correlation_id),
                published_at=artifact.created_at.isoformat(),
            )
        except KeyError as ke:
            logger.exception(
                f"MCPServerComponent: Unknown artifact type: {artifact_type}: {ke!s}"
            )
            return ArtifactPublishErrorResponse(
                reason=f"Unknown artifact_type: {artifact_type}"
            )
        except Exception as ex:
            logger.exception(f"MCPServerComponent: Error publishing artifact: {ex!s}")
            return ArtifactPublishErrorResponse(
                reason=f"Error publishing artifact: {ex!s}"
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
        summary="List all available agents along with their descriptions.",
        response_model=AgentListResponse,
    )
    async def list_available_agents() -> AgentListResponse:
        """Lists all available agents that can be used.

        Returns:
            AgentListResponse, a list of all available agents.
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
        summary="Invoke a specific agent directly by its given name.",
        response_model=AgentRunResponse | AgentInvokationError,  # noqa: F821
    )
    async def invoke_agent(
        invokation: AgentInvokation,
    ) -> AgentRunResponse | AgentInvokationError:
        """Directly invoke a specific agent.
        This bypasses the blackboard-system and complex workflows.
        This executes the agent immediately without checking
        subscriptions or predicates.
        Useful for directly using an Agent to complete a task
        in a synchronous request-response pattern.

        Args:
            name: name of the agent (each Agent has a unique name)
            body: AgentRunRequest, containing the data the agent needs to do its job.
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
                        return AgentInvokationResult(
                            artifacts=[
                                ArtifactResult(
                                    id=str(artifact.id),
                                    type=artifact.type,
                                    payload=artifact.payload,
                                    produced_by=artifact.produced_by,
                                )
                                for artifact in outputs
                            ]
                        )
                    except Exception as execex:
                        logger.exception(
                            f"MCPServerComponent: Agent execution for agent {agent.name} failed: {execex!s}"
                        )
                        return AgentInvokationError(
                            message=f"Agent Execution failed for agent {agent.name}: {execex!s}"
                        )
                except Exception as exc:
                    logger.exception(
                        f"MCPServerComponent: Failed to resolve input type for '{item.type}': {exc!s}"
                    )
                    return AgentInvokationError(
                        message=f"Unable to parse inputs for input: '{item.type}' for agent '{invokation.name}'"
                    )
        except KeyError as ex:
            logger.exception(
                f"MCPServerComponent: Failed to get agent '{invokation.name}': {ex!s}"
            )
            # return an error response to the caller.
            return AgentInvokationError(
                message=f"Unkown Agent: No Agent with name '{invokation.name}' registered."
            )

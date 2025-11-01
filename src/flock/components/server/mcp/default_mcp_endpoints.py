from typing import TYPE_CHECKING

from flock.api.models import AgentListResponse
from flock.components.server.models.models import (
    Agent,
    AgentInvokation,
    AgentInvokationError,
    AgentInvokationResult,
    AgentRunResponse,
    AgentSubscription,
    ArtifactResult,
)
from flock.logging.logging import FlockLogger
from flock.registry import type_registry


if TYPE_CHECKING:
    from fastapi import FastAPI

    from flock.core import Flock


def register_list_available_agent_route(
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

        Example Response:
            {
                "agents": [
                    {
                        "name": "agent_name_1",
                        "description": "description of what agent_name_1 does",
                    },
                    {
                        "name": "agent_name_2",
                        "description": "description of what agent_name_2 does",
                    }
                ]
            }
        """
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


def register_agent_invokation_route(
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
            body: AgentRunRequest
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

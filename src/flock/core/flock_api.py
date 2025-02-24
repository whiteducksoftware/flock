"""REST API server for Flock."""

import uuid
from datetime import datetime
from typing import Any

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, Field

from flock.core.flock import Flock
from flock.core.logging.logging import get_logger

logger = get_logger("api")


class FlockAPIRequest(BaseModel):
    """Request model for running an agent."""

    agent_name: str = Field(..., description="Name of the agent to run")
    inputs: dict[str, Any] = Field(
        default_factory=dict, description="Input data for the agent"
    )
    async_run: bool = Field(
        default=False, description="Whether to run asynchronously"
    )


class FlockAPIResponse(BaseModel):
    """Response model for run requests."""

    run_id: str = Field(..., description="Unique ID for this run")
    status: str = Field(..., description="Status of the run")
    result: dict[str, Any] | None = Field(
        None, description="Run result if completed"
    )
    started_at: datetime = Field(..., description="When the run started")
    completed_at: datetime | None = Field(
        None, description="When the run completed"
    )
    error: str | None = Field(None, description="Error message if failed")


class FlockAPI:
    """REST API server for Flock.

    Provides HTTP endpoints for:
    - Running agents
    - Checking run status
    - Getting run results
    """

    def __init__(self, flock: Flock):
        self.flock = flock
        self.app = FastAPI(title="Flock API")
        self.runs: dict[str, FlockAPIResponse] = {}

        # Register routes
        self._setup_routes()

    def _setup_routes(self):
        """Set up API routes."""

        @self.app.post("/run/flock", response_model=FlockAPIResponse)
        async def run_flock(
            request: FlockAPIRequest, background_tasks: BackgroundTasks
        ):
            """Run an agent with the provided inputs."""
            try:
                # Generate run ID
                run_id = str(uuid.uuid4())

                # Create initial response
                response = FlockAPIResponse(
                    run_id=run_id, status="starting", started_at=datetime.now()
                )
                self.runs[run_id] = response

                if request.async_run:
                    # Start run in background
                    background_tasks.add_task(
                        self._run_flock,
                        run_id,
                        request.agent_name,
                        request.inputs,
                    )
                    response.status = "running"
                else:
                    # Run synchronously
                    await self._run_flock(
                        run_id, request.agent_name, request.inputs
                    )

                return self.runs[run_id]

            except Exception as e:
                logger.error(f"Error starting run: {e!s}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/run/agent", response_model=FlockAPIResponse)
        async def run_agent(
            request: FlockAPIRequest, background_tasks: BackgroundTasks
        ):
            """Run an agent with the provided inputs."""
            try:
                # Generate run ID
                run_id = str(uuid.uuid4())

                # Create initial response
                response = FlockAPIResponse(
                    run_id=run_id, status="starting", started_at=datetime.now()
                )
                self.runs[run_id] = response

                if request.async_run:
                    # Start run in background
                    background_tasks.add_task(
                        self._run_agent,
                        run_id,
                        request.agent_name,
                        request.inputs,
                    )
                    response.status = "running"
                else:
                    # Run synchronously
                    await self._run_agent(
                        run_id, request.agent_name, request.inputs
                    )

                return self.runs[run_id]

            except Exception as e:
                logger.error(f"Error starting run: {e!s}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/run/{run_id}", response_model=FlockAPIResponse)
        async def get_run_status(run_id: str):
            """Get the status of a run."""
            if run_id not in self.runs:
                raise HTTPException(status_code=404, detail="Run not found")
            return self.runs[run_id]

        @self.app.get("/agents")
        async def list_agents():
            """List all available agents."""
            return {
                "agents": [
                    {
                        "name": agent.name,
                        "description": agent.description,
                        "input_schema": agent.input,
                        "output_schema": agent.output,
                        "hand_off": agent.hand_off,
                    }
                    for agent in self.flock.agents.values()
                ]
            }

    async def _run_agent(
        self, run_id: str, agent_name: str, inputs: dict[str, Any]
    ):
        """Execute an agent run."""
        try:
            # Get the agent
            if agent_name not in self.flock.agents:
                raise ValueError(f"Agent '{agent_name}' not found")

            agent = self.flock.agents[agent_name]

            # Run the agent
            result = await agent.run_async(inputs)

            # Update run status
            self.runs[run_id].status = "completed"
            self.runs[run_id].result = result
            self.runs[run_id].completed_at = datetime.now()

        except Exception as e:
            logger.error(f"Error in run {run_id}: {e!s}")
            self.runs[run_id].status = "failed"
            self.runs[run_id].error = str(e)
            self.runs[run_id].completed_at = datetime.now()

    async def _run_flock(
        self, run_id: str, agent_name: str, inputs: dict[str, Any]
    ):
        """Execute an agent run."""
        try:
            # Get the agent
            if agent_name not in self.flock.agents:
                raise ValueError(f"Agent '{agent_name}' not found")

            result = await self.flock.run_async(
                start_agent=agent_name, input=inputs
            )

            # Update run status
            self.runs[run_id].status = "completed"
            self.runs[run_id].result = result
            self.runs[run_id].completed_at = datetime.now()

        except Exception as e:
            logger.error(f"Error in run {run_id}: {e!s}")
            self.runs[run_id].status = "failed"
            self.runs[run_id].error = str(e)
            self.runs[run_id].completed_at = datetime.now()

    def start(self, host: str = "0.0.0.0", port: int = 8344):
        """Start the API server."""
        uvicorn.run(self.app, host=host, port=port)

    async def stop(self):
        """Stop the API server."""
        # Cleanup if needed
        pass

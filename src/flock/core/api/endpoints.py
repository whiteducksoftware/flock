# src/flock/core/api/endpoints.py
"""FastAPI endpoints for the Flock API, using FastAPI's dependency injection."""

import uuid
from typing import TYPE_CHECKING

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,  # Crucial import for dependency injection
    HTTPException,
)

from flock.core.logging.logging import get_logger

# Import the dependency provider functions
# This assumes you'll create 'src/flock/webapp/app/dependencies.py' (or similar)
# with get_flock_instance and get_run_store functions.
# For now, to make this file runnable in isolation for generation,
# we might need temporary stubs or to adjust the import path later.
# Let's assume a common location for dependencies.
from flock.webapp.app.dependencies import get_flock_instance, get_run_store

from .models import (
    FlockAPIRequest,
    FlockAPIResponse,
    FlockBatchRequest,
    FlockBatchResponse,
)

if TYPE_CHECKING:
    from flock.core.flock import Flock

    from .run_store import RunStore
    # We also need the _run_flock, _run_batch, _type_convert_inputs methods.
    # These will be part of the Flock instance itself or helper functions
    # that take Flock/RunStore as arguments. For now, let's assume they
    # are methods on the Flock instance or can be called statically with it.

logger = get_logger("api.endpoints")

# The create_api_router function no longer needs to be passed the FlockAPI instance
# as dependencies will be injected directly into the route handlers.
def create_api_router() -> APIRouter:
    """Creates the APIRouter for core Flock API endpoints."""
    router = APIRouter()

    # --- API Endpoints ---
    @router.post("/run/flock", response_model=FlockAPIResponse, tags=["Flock API Core"])
    async def run_flock_workflow(
        request_model: FlockAPIRequest, # Renamed from 'request' to avoid conflict with FastAPI's Request
        background_tasks: BackgroundTasks,
        flock_instance: "Flock" = Depends(get_flock_instance), # Injected
        run_store: "RunStore" = Depends(get_run_store)          # Injected
    ):
        """Run a flock workflow starting with the specified agent."""
        run_id = None
        try:
            run_id = str(uuid.uuid4())
            run_store.create_run(run_id)
            response_data = run_store.get_run(run_id)

            if not response_data:
                logger.error(f"Failed to create run record for run_id: {run_id}")
                raise HTTPException(status_code=500, detail="Failed to initialize run.")

            processed_inputs = request_model.inputs if request_model.inputs else {}
            logger.info(
                f"API request: run flock '{request_model.agent_name}' (run_id: {run_id})",
                inputs=processed_inputs,
            )

            # The _run_flock logic now needs to be called. It could be a method on
            # flock_instance, or a static/helper function that takes flock_instance.
            # Let's assume it's a method on flock_instance for now.
            # To avoid direct calls to private-like methods from router,
            # Flock class would expose a public method that handles this internal logic.
            # For this refactoring step, let's assume a helper `_execute_flock_run` exists
            # that we can call.

            async def _execute_flock_run_task(run_id_task, agent_name_task, inputs_task):
                # This is a simplified version of what was in FlockAPI._run_flock
                try:
                    if agent_name_task not in flock_instance.agents:
                        raise ValueError(f"Starting agent '{agent_name_task}' not found")
                    # Type conversion would ideally be part of the Flock's run logic
                    # or a utility. For now, assume it's handled or simple.
                    # typed_inputs = flock_instance._type_convert_inputs(agent_name_task, inputs_task) # Example if kept on Flock
                    typed_inputs = inputs_task # Simplified for now

                    result = await flock_instance.run_async(
                        agent=agent_name_task, input=typed_inputs
                    )
                    run_store.update_run_result(run_id_task, result)
                except Exception as e_task:
                    logger.error(f"Error in background flock run {run_id_task}: {e_task!s}", exc_info=True)
                    run_store.update_run_status(run_id_task, "failed", str(e_task))


            if request_model.async_run:
                logger.debug(
                    f"Running flock '{request_model.agent_name}' asynchronously (run_id: {run_id})"
                )
                background_tasks.add_task(
                    _execute_flock_run_task,
                    run_id,
                    request_model.agent_name,
                    processed_inputs,
                )
                run_store.update_run_status(run_id, "running")
                response_data.status = "running"
            else:
                logger.debug(
                    f"Running flock '{request_model.agent_name}' synchronously (run_id: {run_id})"
                )
                await _execute_flock_run_task(
                     run_id, request_model.agent_name, processed_inputs
                )
                response_data = run_store.get_run(run_id)

            if not response_data:
                 logger.error(f"Run data lost for run_id: {run_id} after execution.")
                 raise HTTPException(status_code=500, detail="Run data lost after execution.")

            return response_data
        except ValueError as ve:
            logger.error(f"Value error starting run for agent '{request_model.agent_name}': {ve}", exc_info=True)
            if run_id: run_store.update_run_status(run_id, "failed", str(ve))
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            error_msg = f"Internal server error during flock run: {type(e).__name__}"
            logger.error(f"Error starting flock run: {e!s}", exc_info=True)
            if run_id: run_store.update_run_status(run_id, "failed", error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

    @router.post("/run/batch", response_model=FlockBatchResponse, tags=["Flock API Core"])
    async def run_batch_workflow(
        request_model: FlockBatchRequest, # Renamed from 'request'
        background_tasks: BackgroundTasks,
        flock_instance: "Flock" = Depends(get_flock_instance),
        run_store: "RunStore" = Depends(get_run_store)
    ):
        """Run a batch of inputs through the flock workflow."""
        batch_id = None
        try:
            if request_model.agent_name not in flock_instance.agents:
                raise ValueError(f"Agent '{request_model.agent_name}' not found in current Flock.")

            if isinstance(request_model.batch_inputs, list) and not request_model.batch_inputs:
                raise ValueError("Batch inputs list cannot be empty if provided as a list.")

            batch_id = str(uuid.uuid4())
            run_store.create_batch(batch_id)
            response_data = run_store.get_batch(batch_id)

            if not response_data:
                logger.error(f"Failed to create batch record for batch_id: {batch_id}")
                raise HTTPException(status_code=500, detail="Failed to initialize batch run.")

            batch_size = (
                len(request_model.batch_inputs)
                if isinstance(request_model.batch_inputs, list)
                else "CSV/DataFrame"
            )
            logger.info(
                f"API request: run batch with '{request_model.agent_name}' (batch_id: {batch_id})",
                batch_size=batch_size,
            )

            async def _execute_flock_batch_task(batch_id_task, batch_request_task: FlockBatchRequest):
                # This is a simplified version of what was in FlockAPI._run_batch
                try:
                    # Directly use the flock_instance's run_batch_async method
                    results = await flock_instance.run_batch_async(
                        start_agent=batch_request_task.agent_name,
                        batch_inputs=batch_request_task.batch_inputs,
                        input_mapping=batch_request_task.input_mapping,
                        static_inputs=batch_request_task.static_inputs,
                        parallel=batch_request_task.parallel,
                        max_workers=batch_request_task.max_workers,
                        use_temporal=batch_request_task.use_temporal,
                        box_results=batch_request_task.box_results,
                        return_errors=batch_request_task.return_errors,
                        silent_mode=True, # API batch runs should be internally silent
                        write_to_csv=None # API handles CSV writing based on request if needed, not here
                    )
                    run_store.update_batch_result(batch_id_task, results)
                    logger.info(f"Batch run completed (batch_id: {batch_id_task})", num_results=len(results))
                except Exception as e_task:
                    logger.error(f"Error in background flock batch {batch_id_task}: {e_task!s}", exc_info=True)
                    run_store.update_batch_status(batch_id_task, "failed", str(e_task))

            logger.debug(
                f"Running batch with '{request_model.agent_name}' asynchronously (batch_id: {batch_id})"
            )
            background_tasks.add_task(
                _execute_flock_batch_task,
                batch_id,
                request_model, # Pass the Pydantic request model
            )
            run_store.update_batch_status(batch_id, "running")
            response_data.status = "running"

            return response_data
        except ValueError as ve:
            error_msg = f"Value error starting batch for agent '{request_model.agent_name}': {ve}"
            logger.error(error_msg, exc_info=True)
            if batch_id: run_store.update_batch_status(batch_id, "failed", str(ve))
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            error_msg = f"Internal server error during batch run: {type(e).__name__}: {e!s}"
            logger.error(error_msg, exc_info=True)
            if batch_id: run_store.update_batch_status(batch_id, "failed", error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

    @router.get("/run/{run_id}", response_model=FlockAPIResponse, tags=["Flock API Core"])
    async def get_run_status(
        run_id: str,
        run_store: "RunStore" = Depends(get_run_store)
    ):
        """Get the status of a specific run."""
        logger.debug(f"API request: get status for run_id: {run_id}")
        run_data = run_store.get_run(run_id)
        if not run_data:
            logger.warning(f"Run ID not found: {run_id}")
            raise HTTPException(status_code=404, detail="Run not found")
        return run_data

    @router.get("/batch/{batch_id}", response_model=FlockBatchResponse, tags=["Flock API Core"])
    async def get_batch_status(
        batch_id: str,
        run_store: "RunStore" = Depends(get_run_store)
    ):
        """Get the status and results of a specific batch run."""
        logger.debug(f"API request: get status for batch_id: {batch_id}")
        batch_data = run_store.get_batch(batch_id)
        if not batch_data:
            logger.warning(f"Batch ID not found: {batch_id}")
            raise HTTPException(status_code=404, detail="Batch not found")
        return batch_data

    @router.get("/agents", tags=["Flock API Core"])
    async def list_agents(
        flock_instance: "Flock" = Depends(get_flock_instance)
    ):
        """List all available agents in the currently loaded Flock."""
        logger.debug("API request: list agents")
        agents_list = [
            agent.to_dict()
            for agent in flock_instance.agents.values()
        ]
        return {"agents": agents_list}

    return router

# src/flock/core/api/endpoints.py
"""FastAPI endpoints for the Flock API."""

import html  # For escaping
import uuid
from typing import TYPE_CHECKING  # Added Any for type hinting clarity

from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    Request as FastAPIRequest,
)

# Import HTMLResponse for the UI form endpoint
from fastapi.responses import HTMLResponse

from flock.core.logging.logging import get_logger

# Import models and UI utils
from .models import (
    FlockAPIRequest,
    FlockAPIResponse,
    FlockBatchRequest,
    FlockBatchResponse,
)

# Import UI utils - assuming they are now in ui/utils.py

# Use TYPE_CHECKING to avoid circular imports for type hints
if TYPE_CHECKING:
    from flock.core.flock import Flock

    from .main import FlockAPI
    from .run_store import RunStore

logger = get_logger("api.endpoints")


# Factory function to create the router with dependencies
def create_api_router(flock_api: "FlockAPI") -> APIRouter:
    """Creates the APIRouter and defines endpoints, injecting dependencies."""
    router = APIRouter()
    # Get dependencies from the main FlockAPI instance passed in
    run_store: RunStore = flock_api.run_store
    flock_instance: Flock = flock_api.flock

    # --- API Endpoints ---
    @router.post("/run/flock", response_model=FlockAPIResponse, tags=["API"])
    async def run_flock_json(
        request: FlockAPIRequest, background_tasks: BackgroundTasks
    ):
        """Run a flock workflow starting with the specified agent (expects JSON)."""
        run_id = None
        try:
            run_id = str(uuid.uuid4())
            run_store.create_run(run_id)  # Use RunStore
            response = run_store.get_run(
                run_id
            )  # Get initial response from store

            processed_inputs = request.inputs if request.inputs else {}
            logger.info(
                f"API request: run flock '{request.agent_name}' (run_id: {run_id})",
                inputs=processed_inputs,
            )

            if request.async_run:
                logger.debug(
                    f"Running flock '{request.agent_name}' asynchronously (run_id: {run_id})"
                )
                # Call the helper method on the passed FlockAPI instance
                background_tasks.add_task(
                    flock_api._run_flock,
                    run_id,
                    request.agent_name,
                    processed_inputs,
                )
                run_store.update_run_status(run_id, "running")
                response.status = "running"  # Update local response copy too
            else:
                logger.debug(
                    f"Running flock '{request.agent_name}' synchronously (run_id: {run_id})"
                )
                # Call the helper method on the passed FlockAPI instance
                await flock_api._run_flock(
                    run_id, request.agent_name, processed_inputs
                )
                response = run_store.get_run(
                    run_id
                )  # Fetch updated status/result

            return response
        except ValueError as ve:
            logger.error(f"Value error starting run: {ve}")
            if run_id:
                run_store.update_run_status(run_id, "failed", str(ve))
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            error_msg = f"Internal server error: {type(e).__name__}"
            logger.error(f"Error starting run: {e!s}", exc_info=True)
            if run_id:
                run_store.update_run_status(run_id, "failed", error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

    @router.post("/run/batch", response_model=FlockBatchResponse, tags=["API"])
    async def run_batch_json(
        request: FlockBatchRequest, background_tasks: BackgroundTasks
    ):
        """Run a batch of inputs through the flock workflow (expects JSON)."""
        batch_id = None
        try:
            # Validate agent exists
            if request.agent_name not in flock_instance.agents:
                raise ValueError(f"Agent '{request.agent_name}' not found")

            # Validate batch inputs
            if (
                isinstance(request.batch_inputs, list)
                and not request.batch_inputs
            ):
                raise ValueError("Batch inputs list cannot be empty")

            batch_id = str(uuid.uuid4())
            run_store.create_batch(batch_id)  # Use RunStore
            response = run_store.get_batch(
                batch_id
            )  # Get initial response from store

            # Log batch size for monitoring
            batch_size = (
                len(request.batch_inputs)
                if isinstance(request.batch_inputs, list)
                else "CSV/DataFrame"
            )
            logger.info(
                f"API request: run batch with '{request.agent_name}' (batch_id: {batch_id})",
                batch_size=batch_size,
            )

            # Always run batch processing asynchronously
            logger.debug(
                f"Running batch with '{request.agent_name}' asynchronously (batch_id: {batch_id})"
            )
            # Call the helper method on the passed FlockAPI instance
            background_tasks.add_task(
                flock_api._run_batch,
                batch_id,
                request,
            )
            run_store.update_batch_status(batch_id, "running")
            response.status = "running"  # Update local response copy too

            return response
        except ValueError as ve:
            error_msg = f"Value error starting batch: {ve}"
            logger.error(error_msg)
            if batch_id:
                run_store.update_batch_status(batch_id, "failed", str(ve))
            raise HTTPException(status_code=400, detail=str(ve))
        except Exception as e:
            error_msg = f"Internal server error: {type(e).__name__}: {e!s}"
            logger.error(error_msg, exc_info=True)
            if batch_id:
                run_store.update_batch_status(batch_id, "failed", error_msg)
            raise HTTPException(status_code=500, detail=error_msg)

    @router.get("/run/{run_id}", response_model=FlockAPIResponse, tags=["API"])
    async def get_run_status(run_id: str):
        """Get the status of a specific run."""
        logger.debug(f"API request: get status for run_id: {run_id}")
        run_data = run_store.get_run(run_id)
        if not run_data:
            logger.warning(f"Run ID not found: {run_id}")
            raise HTTPException(status_code=404, detail="Run not found")
        return run_data

    @router.get(
        "/batch/{batch_id}", response_model=FlockBatchResponse, tags=["API"]
    )
    async def get_batch_status(batch_id: str):
        """Get the status of a specific batch run.

        Returns details including:
        - Total number of items in the batch
        - Number of completed items
        - Percentage of completion
        - Any partial results available (for running batches)
        - Complete results (for completed batches)
        """
        logger.debug(f"API request: get status for batch_id: {batch_id}")
        batch_data = run_store.get_batch(batch_id)
        if not batch_data:
            logger.warning(f"Batch ID not found: {batch_id}")
            raise HTTPException(status_code=404, detail="Batch not found")

        # Add useful info for client display
        extra_info = {
            "status": batch_data.status,
            "completed_items": batch_data.completed_items,
            "total_items": batch_data.total_items,
            "progress_percentage": round(batch_data.progress_percentage, 1),
            "has_partial_results": len(batch_data.results) > 0
            and batch_data.status == "running",
            "has_error": batch_data.error is not None,
        }
        logger.debug(f"Returning batch status: {extra_info}")

        return batch_data

    @router.get("/agents", tags=["API"])
    async def list_agents():
        """List all available agents."""
        logger.debug("API request: list agents")
        # Access flock instance via factory closure
        agents_list = [
            {"name": agent.name, "description": agent.description or agent.name}
            for agent in flock_instance.agents.values()
        ]
        return {"agents": agents_list}

    # --- UI Form Endpoint ---
    @router.post("/ui/run-agent-form", response_class=HTMLResponse, tags=["UI"])
    async def run_flock_form(fastapi_req: FastAPIRequest):
        """Endpoint to handle form submissions from the UI."""
        run_id = None
        try:
            form_data = await fastapi_req.form()
            agent_name = form_data.get("agent_name")
            if not agent_name:
                logger.warning("UI form submission missing agent_name")
                return HTMLResponse(
                    '<div id="result-content" class="error-message">Error: Agent name not provided.</div>',
                    status_code=400,
                )

            logger.info(f"UI Form submission for agent: {agent_name}")
            form_inputs = {}
            # Access flock instance via factory closure
            agent_def = flock_instance.agents.get(agent_name)
            # Use helper from flock_api instance for parsing
            defined_input_fields = (
                flock_api._parse_input_spec(agent_def.input or "")
                if agent_def
                else []
            )

            for key, value in form_data.items():
                if key.startswith("inputs."):
                    form_inputs[key[len("inputs.") :]] = value
            for field in defined_input_fields:  # Handle checkboxes
                if (
                    field["html_type"] == "checkbox"
                    and field["name"] not in form_inputs
                ):
                    form_inputs[field["name"]] = False
                elif (
                    field["html_type"] == "checkbox"
                    and field["name"] in form_inputs
                ):
                    form_inputs[field["name"]] = True

            logger.debug(f"Parsed form inputs for UI run: {form_inputs}")
            run_id = str(uuid.uuid4())
            run_store.create_run(run_id)
            logger.debug(
                f"Running flock '{agent_name}' synchronously from UI (run_id: {run_id})"
            )

            # Call helper method on flock_api instance
            await flock_api._run_flock(run_id, agent_name, form_inputs)

            final_status = run_store.get_run(run_id)
            if final_status and final_status.status == "completed":
                # Use helper from flock_api instance for formatting
                formatted_html = flock_api._format_result_to_html(
                    final_status.result
                )
                logger.info(f"UI run completed successfully (run_id: {run_id})")
                return HTMLResponse(
                    f"<div id='result-content'>{formatted_html}</div>"
                )  # Wrap in target div
            elif final_status and final_status.status == "failed":
                logger.error(
                    f"UI run failed (run_id: {run_id}): {final_status.error}"
                )
                error_msg = html.escape(final_status.error or "Unknown error")
                return HTMLResponse(
                    f"<div id='result-content' class='error-message'>Run Failed: {error_msg}</div>",
                    status_code=500,
                )
            else:
                status_str = (
                    final_status.status if final_status else "Not Found"
                )
                logger.warning(
                    f"UI run {run_id} ended in unexpected state: {status_str}"
                )
                return HTMLResponse(
                    f"<div id='result-content' class='error-message'>Run ended unexpectedly. Status: {status_str}</div>",
                    status_code=500,
                )

        except ValueError as ve:
            logger.error(f"Value error processing UI form run: {ve}")
            if run_id:
                run_store.update_run_status(run_id, "failed", str(ve))
            return HTMLResponse(
                f"<div id='result-content' class='error-message'>Error: {html.escape(str(ve))}</div>",
                status_code=400,
            )
        except Exception as e:
            error_msg = f"Internal server error: {type(e).__name__}"
            logger.error(f"Error processing UI form run: {e!s}", exc_info=True)
            if run_id:
                run_store.update_run_status(run_id, "failed", error_msg)
            return HTMLResponse(
                f"<div id='result-content' class='error-message'>{html.escape(error_msg)}</div>",
                status_code=500,
            )

    return router

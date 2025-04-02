# src/flock/core/api/main.py
"""Main Flock API server class and setup."""

from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

# Flock core imports
from flock.core.flock import Flock
from flock.core.logging.logging import get_logger

from .endpoints import create_api_router

# Import components from the api package
from .run_store import RunStore
from .ui.routes import FASTHTML_AVAILABLE, create_ui_app
from .ui.utils import format_result_to_html, parse_input_spec  # Import UI utils

logger = get_logger("api.main")


class FlockAPI:
    """Coordinates the Flock API server, including endpoints and UI."""

    def __init__(self, flock: Flock):
        self.flock = flock
        self.app = FastAPI(title="Flock API")
        self.run_store = RunStore()  # Create the run store instance
        self._setup_routes()

    def _setup_routes(self):
        """Includes API routers."""
        # Create and include the API router, passing self
        api_router = create_api_router(self)
        self.app.include_router(api_router)

        # Root redirect (if UI is enabled later) will be added in start()

    # --- Core Execution Helper Methods ---
    # These remain here as they need access to self.flock and self.run_store

    async def _run_agent(
        self, run_id: str, agent_name: str, inputs: dict[str, Any]
    ):
        """Executes a single agent run (internal helper)."""
        try:
            if agent_name not in self.flock.agents:
                raise ValueError(f"Agent '{agent_name}' not found")
            agent = self.flock.agents[agent_name]
            # Type conversion (remains important)
            typed_inputs = self._type_convert_inputs(agent_name, inputs)

            logger.debug(
                f"Executing single agent '{agent_name}' (run_id: {run_id})",
                inputs=typed_inputs,
            )
            result = await agent.run_async(typed_inputs)
            logger.info(
                f"Single agent '{agent_name}' completed (run_id: {run_id})"
            )

            # Use RunStore to update
            self.run_store.update_run_result(run_id, result)

        except Exception as e:
            logger.error(
                f"Error in single agent run {run_id} ('{agent_name}'): {e!s}",
                exc_info=True,
            )
            # Update store status
            self.run_store.update_run_status(run_id, "failed", str(e))
            raise  # Re-raise for the endpoint handler

    async def _run_flock(
        self, run_id: str, agent_name: str, inputs: dict[str, Any]
    ):
        """Executes a flock workflow run (internal helper)."""
        try:
            if agent_name not in self.flock.agents:
                raise ValueError(f"Starting agent '{agent_name}' not found")

            # Type conversion
            typed_inputs = self._type_convert_inputs(agent_name, inputs)

            logger.debug(
                f"Executing flock workflow starting with '{agent_name}' (run_id: {run_id})",
                inputs=typed_inputs,
            )
            result = await self.flock.run_async(
                start_agent=agent_name, input=typed_inputs
            )
            # Result is potentially a Box object

            # Use RunStore to update
            self.run_store.update_run_result(run_id, result)

            # Log using the local result variable
            final_agent_name = (
                result.get("agent_name", "N/A") if result is not None else "N/A"
            )
            logger.info(
                f"Flock workflow completed (run_id: {run_id})",
                final_agent=final_agent_name,
            )

        except Exception as e:
            logger.error(
                f"Error in flock run {run_id} (started with '{agent_name}'): {e!s}",
                exc_info=True,
            )
            # Update store status
            self.run_store.update_run_status(run_id, "failed", str(e))
            raise  # Re-raise for the endpoint handler

    # --- UI Helper Methods (kept here as they are called by endpoints via self) ---

    def _parse_input_spec(self, input_spec: str) -> list[dict[str, str]]:
        """Parses an agent input string into a list of field definitions."""
        # Use the implementation moved to ui.utils
        return parse_input_spec(input_spec)

    def _format_result_to_html(self, data: Any) -> str:
        """Recursively formats a Python object into an HTML string."""
        # Use the implementation moved to ui.utils
        return format_result_to_html(data)

    def _type_convert_inputs(
        self, agent_name: str, inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """Converts input values (esp. from forms) to expected Python types."""
        typed_inputs = {}
        agent_def = self.flock.agents.get(agent_name)
        if not agent_def or not agent_def.input:
            return inputs  # Return original if no spec

        parsed_fields = self._parse_input_spec(agent_def.input)
        field_types = {f["name"]: f["type"] for f in parsed_fields}

        for k, v in inputs.items():
            target_type = field_types.get(k)
            if target_type and target_type.startswith("bool"):
                typed_inputs[k] = (
                    str(v).lower() in ["true", "on", "1", "yes"]
                    if isinstance(v, str)
                    else bool(v)
                )
            elif target_type and target_type.startswith("int"):
                try:
                    typed_inputs[k] = int(v)
                except (ValueError, TypeError):
                    logger.warning(
                        f"Could not convert input '{k}' value '{v}' to int for agent '{agent_name}'"
                    )
                    typed_inputs[k] = v
            elif target_type and target_type.startswith("float"):
                try:
                    typed_inputs[k] = float(v)
                except (ValueError, TypeError):
                    logger.warning(
                        f"Could not convert input '{k}' value '{v}' to float for agent '{agent_name}'"
                    )
                    typed_inputs[k] = v
            # TODO: Add list/dict parsing (e.g., json.loads) if needed
            else:
                typed_inputs[k] = v  # Assume string or already correct type
        return typed_inputs

    # --- Server Start/Stop ---

    def start(
        self,
        host: str = "0.0.0.0",
        port: int = 8344,
        server_name: str = "Flock API",
        create_ui: bool = False,
    ):
        """Start the API server, optionally creating and mounting a FastHTML UI."""
        if create_ui:
            if not FASTHTML_AVAILABLE:
                logger.error(
                    "FastHTML not installed. Cannot create UI. Running API only."
                )
            else:
                logger.info("Attempting to create and mount FastHTML UI at /ui")
                try:
                    # Pass self (FlockAPI instance) to the UI creation function
                    # It needs access to self.flock and self._parse_input_spec
                    fh_app = create_ui_app(
                        self,
                        api_host=host,
                        api_port=port,
                        server_name=server_name,
                    )
                    self.app.mount("/ui", fh_app, name="ui")
                    logger.info("FastHTML UI mounted successfully.")

                    # Add root redirect only if UI was successfully mounted
                    @self.app.get(
                        "/",
                        include_in_schema=False,
                        response_class=RedirectResponse,
                    )
                    async def root_redirect():
                        logger.debug("Redirecting / to /ui/")
                        return "/ui/"

                except ImportError as e:
                    logger.error(
                        f"Could not create UI due to import error: {e}. Running API only."
                    )
                except Exception as e:
                    logger.error(
                        f"An error occurred setting up the UI: {e}. Running API only.",
                        exc_info=True,
                    )

        logger.info(f"Starting API server on http://{host}:{port}")
        if (
            create_ui
            and FASTHTML_AVAILABLE
            and any(
                m.path == "/ui" for m in self.app.routes if hasattr(m, "path")
            )
        ):
            logger.info(f"UI available at http://{host}:{port}/ui/")

        uvicorn.run(self.app, host=host, port=port)

    async def stop(self):
        """Stop the API server."""
        logger.info("Stopping API server (cleanup if necessary)")
        pass  # Add cleanup logic if needed


# --- End of file ---

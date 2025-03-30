# src/flock/core/api/main.py
"""Main Flock API server class and endpoints."""

import html  # For escaping HTML in responses
import uuid
from datetime import datetime
from typing import Any

import uvicorn

# FastAPI related imports
from fastapi import (
    BackgroundTasks,
    FastAPI,
    HTTPException,
    Request as FastAPIRequest,
)
from fastapi.responses import HTMLResponse, RedirectResponse

# Flock core imports
from flock.core.flock import Flock
from flock.core.logging.logging import get_logger
from flock.core.util.input_resolver import (
    split_top_level,  # Ensure this utility exists and works
)

# Import models and UI creation function from within the package
from .models import FlockAPIRequest, FlockAPIResponse

# Import UI creation function and availability flag
from .ui.routes import FASTHTML_AVAILABLE, create_ui_app

logger = get_logger("api.main")  # Updated logger name


# --- Main API Class ---
class FlockAPI:
    """REST API server for Flock with optional integrated UI."""

    def __init__(self, flock: Flock):
        self.flock = flock
        self.app = FastAPI(title="Flock API")
        self.runs: dict[str, FlockAPIResponse] = {}
        self._setup_routes()  # Setup FastAPI routes

    def _setup_routes(self):
        """Set up FastAPI API and UI routes."""

        # --- API Endpoints ---
        @self.app.post(
            "/run/flock", response_model=FlockAPIResponse, tags=["API"]
        )
        async def run_flock_json(
            request: FlockAPIRequest, background_tasks: BackgroundTasks
        ):
            """Run a flock workflow starting with the specified agent (expects JSON)."""
            run_id = None
            try:
                run_id = str(uuid.uuid4())
                response = FlockAPIResponse(
                    run_id=run_id, status="starting", started_at=datetime.now()
                )
                self.runs[run_id] = response
                processed_inputs = request.inputs if request.inputs else {}
                logger.info(
                    f"Received API request to run flock '{request.agent_name}' (run_id: {run_id})",
                    inputs=processed_inputs,
                )

                if request.async_run:
                    logger.debug(
                        f"Running flock '{request.agent_name}' asynchronously (run_id: {run_id})"
                    )
                    background_tasks.add_task(
                        self._run_flock,
                        run_id,
                        request.agent_name,
                        processed_inputs,
                    )
                    response.status = "running"
                else:
                    logger.debug(
                        f"Running flock '{request.agent_name}' synchronously (run_id: {run_id})"
                    )
                    await self._run_flock(
                        run_id, request.agent_name, processed_inputs
                    )
                    # Update response from self.runs which _run_flock modified
                    response = self.runs.get(run_id, response)

                return response
            except ValueError as ve:
                logger.error(f"Value error starting run: {ve}")
                raise HTTPException(status_code=400, detail=str(ve))
            except Exception as e:
                logger.error(f"Error starting run: {e!s}", exc_info=True)
                if run_id and run_id in self.runs:
                    self.runs[run_id].status = "failed"
                    self.runs[
                        run_id
                    ].error = f"Internal server error: {type(e).__name__}"
                    self.runs[run_id].completed_at = datetime.now()
                raise HTTPException(
                    status_code=500,
                    detail=f"Internal server error: {type(e).__name__}",
                )

        @self.app.get(
            "/run/{run_id}", response_model=FlockAPIResponse, tags=["API"]
        )
        async def get_run_status(run_id: str):
            """Get the status of a specific run."""
            logger.debug(f"Request received for status of run_id: {run_id}")
            if run_id not in self.runs:
                logger.warning(f"Run ID not found: {run_id}")
                raise HTTPException(status_code=404, detail="Run not found")
            return self.runs[run_id]

        @self.app.get("/agents", tags=["API"])
        async def list_agents():
            """List all available agents."""
            logger.debug("Request received to list agents")
            agents_list = [
                {
                    "name": agent.name,
                    "description": agent.description or agent.name,
                }
                for agent in self.flock.agents.values()
            ]
            return {"agents": agents_list}

        # --- UI Form Endpoint ---
        @self.app.post(
            "/ui/run-agent-form", response_class=HTMLResponse, tags=["UI"]
        )
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

                logger.info(
                    f"UI Form submission received for agent: {agent_name}"
                )

                # Reconstruct inputs dict from form data
                form_inputs = {}
                agent_def = self.flock.agents.get(
                    agent_name
                )  # Needed for checkbox handling
                defined_input_fields = (
                    self._parse_input_spec(agent_def.input or "")
                    if agent_def
                    else []
                )

                for key, value in form_data.items():
                    if key.startswith("inputs."):
                        form_inputs[key[len("inputs.") :]] = value
                    # Skip agent_name and other potential non-input form fields

                # Handle checkboxes - set to False if not present in form data
                for field in defined_input_fields:
                    if (
                        field["html_type"] == "checkbox"
                        and field["name"] not in form_inputs
                    ):
                        form_inputs[field["name"]] = (
                            False  # Unchecked checkbox value
                        )
                    elif (
                        field["html_type"] == "checkbox"
                        and field["name"] in form_inputs
                    ):
                        form_inputs[field["name"]] = (
                            True  # Checked checkbox value (form sends 'true' or 'on')
                        )

                logger.debug(f"Parsed form inputs for UI run: {form_inputs}")
                run_id = str(uuid.uuid4())
                self.runs[run_id] = FlockAPIResponse(
                    run_id=run_id, status="starting", started_at=datetime.now()
                )
                logger.debug(
                    f"Running flock '{agent_name}' synchronously from UI (run_id: {run_id})"
                )

                # Run the flock workflow
                await self._run_flock(
                    run_id, agent_name, form_inputs
                )  # Run synchronously

                final_status = self.runs.get(run_id)
                if final_status and final_status.status == "completed":
                    # Format the result dictionary/Box into HTML
                    formatted_html = self._format_result_to_html(
                        final_status.result
                    )
                    logger.info(
                        f"UI run completed successfully (run_id: {run_id})"
                    )
                    # Return the generated HTML structure directly
                    return HTMLResponse(
                        f"<div id='result-content'>{formatted_html}</div>"
                    )  # Wrap in target div
                elif final_status and final_status.status == "failed":
                    logger.error(
                        f"UI run failed (run_id: {run_id}): {final_status.error}"
                    )
                    error_msg = html.escape(
                        final_status.error or "Unknown error"
                    )
                    return HTMLResponse(
                        f"<div id='result-content' class='error-message'>Run Failed: {error_msg}</div>",
                        status_code=500,
                    )
                else:  # Should ideally not happen in sync mode
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

            except (
                ValueError
            ) as ve:  # Catch specific errors like agent not found
                logger.error(f"Value error processing UI form run: {ve}")
                return HTMLResponse(
                    f"<div id='result-content' class='error-message'>Error: {html.escape(str(ve))}</div>",
                    status_code=400,
                )
            except Exception as e:
                logger.error(
                    f"Error processing UI form run: {e!s}", exc_info=True
                )
                if run_id and run_id in self.runs:
                    self.runs[run_id].status = "failed"
                    self.runs[
                        run_id
                    ].error = f"Internal server error: {type(e).__name__}"
                    self.runs[run_id].completed_at = datetime.now()
                return HTMLResponse(
                    f"<div id='result-content' class='error-message'>Internal Server Error: {html.escape(type(e).__name__)}</div>",
                    status_code=500,
                )

    # --- Helper Methods ---

    async def _run_agent(
        self, run_id: str, agent_name: str, inputs: dict[str, Any]
    ):
        """Executes a single agent run (internal helper)."""
        # Note: This is less used now with the UI focusing on flock runs.
        try:
            if agent_name not in self.flock.agents:
                raise ValueError(f"Agent '{agent_name}' not found")
            agent = self.flock.agents[agent_name]

            # Type conversion for inputs potentially coming from JSON API
            typed_inputs = {}
            agent_def = self.flock.agents.get(agent_name)
            if agent_def and agent_def.input:
                parsed_fields = self._parse_input_spec(agent_def.input)
                field_types = {f["name"]: f["type"] for f in parsed_fields}
                for k, v in inputs.items():
                    target_type = field_types.get(k)
                    if target_type and target_type.startswith("bool"):
                        typed_inputs[k] = bool(v)
                    elif target_type and target_type.startswith("int"):
                        try:
                            typed_inputs[k] = int(v)
                        except (ValueError, TypeError):
                            typed_inputs[k] = v
                    elif target_type and target_type.startswith("float"):
                        try:
                            typed_inputs[k] = float(v)
                        except (ValueError, TypeError):
                            typed_inputs[k] = v
                    else:
                        typed_inputs[k] = v
            else:
                typed_inputs = inputs

            logger.debug(
                f"Executing single agent '{agent_name}' (run_id: {run_id})",
                inputs=typed_inputs,
            )
            result = await agent.run_async(typed_inputs)
            logger.info(
                f"Single agent '{agent_name}' completed (run_id: {run_id})"
            )

            # Update status in self.runs
            self.runs[run_id].status = "completed"
            self.runs[run_id].result = (
                dict(result) if hasattr(result, "to_dict") else result
            )
            self.runs[run_id].completed_at = datetime.now()
        except Exception as e:
            logger.error(
                f"Error in single agent run {run_id} ('{agent_name}'): {e!s}",
                exc_info=True,
            )
            if run_id in self.runs:
                self.runs[run_id].status = "failed"
                self.runs[run_id].error = str(e)
                self.runs[run_id].completed_at = datetime.now()
            raise  # Re-raise for the main handler

    async def _run_flock(
        self, run_id: str, agent_name: str, inputs: dict[str, Any]
    ):
        """Executes a flock workflow run (internal helper)."""
        try:
            if agent_name not in self.flock.agents:
                raise ValueError(f"Starting agent '{agent_name}' not found")

            # Apply type conversion for initial inputs (critical for UI form data)
            typed_inputs = {}
            agent_def = self.flock.agents.get(agent_name)
            if agent_def and agent_def.input:
                parsed_fields = self._parse_input_spec(agent_def.input)
                field_types = {f["name"]: f["type"] for f in parsed_fields}
                for k, v in inputs.items():
                    target_type = field_types.get(k)
                    if target_type and target_type.startswith("bool"):
                        # Handles bool, 'true', 'on', etc. from form or bool from JSON
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
                    # TODO: Add handling for list/dict from textarea if needed (e.g., json.loads)
                    else:
                        typed_inputs[k] = (
                            v  # Assume string or already correct type
                        )
            else:
                typed_inputs = inputs  # Fallback if no spec

            logger.debug(
                f"Executing flock workflow starting with '{agent_name}' (run_id: {run_id})",
                inputs=typed_inputs,
            )
            result = await self.flock.run_async(
                start_agent=agent_name, input=typed_inputs
            )
            # Result is potentially a Box object

            # Update the stored run record *before* logging or converting
            self.runs[run_id].status = "completed"
            self.runs[
                run_id
            ].result = result  # Store the original result (Box or dict)
            self.runs[run_id].completed_at = datetime.now()

            # Log using the local result variable
            final_agent_name = (
                result.get("agent_name", "N/A") if result is not None else "N/A"
            )
            logger.info(
                f"Flock workflow completed (run_id: {run_id})",
                final_agent=final_agent_name,
            )

            # Convert Box to dict *after* logging if needed for later JSON use
            if hasattr(result, "to_dict"):
                self.runs[run_id].result = result.to_dict()

        except Exception as e:
            logger.error(
                f"Error in flock run {run_id} (started with '{agent_name}'): {e!s}",
                exc_info=True,
            )
            if run_id in self.runs:
                self.runs[run_id].status = "failed"
                self.runs[run_id].error = str(e)
                self.runs[run_id].completed_at = datetime.now()
            raise  # Re-raise for the main handler

    def _parse_input_spec(self, input_spec: str) -> list[dict[str, str]]:
        """Parses an agent input string into a list of field definitions."""
        fields = []
        if not input_spec:
            return fields
        try:
            parts = split_top_level(input_spec)
        except NameError:
            logger.error("split_top_level utility function not found!")
            return fields

        for part in parts:
            part = part.strip()
            if not part:
                continue
            field_info = {
                "name": "",
                "type": "str",
                "desc": "",
                "html_type": "text",
            }
            name_type_part, *desc_part = part.split("|", 1)
            if desc_part:
                field_info["desc"] = desc_part[0].strip()
            name_part, *type_part = name_type_part.split(":", 1)
            field_info["name"] = name_part.strip()
            if type_part:
                field_info["type"] = type_part[0].strip().lower()

            step = None
            field_type_norm = field_info["type"]
            if field_type_norm.startswith("int"):
                field_info["html_type"] = "number"
            elif field_type_norm.startswith("float"):
                field_info["html_type"] = "number"
                step = "any"
            elif field_type_norm.startswith("bool"):
                field_info["html_type"] = "checkbox"
            elif "list" in field_type_norm or "dict" in field_type_norm:
                field_info["html_type"] = "textarea"
                field_info["rows"] = 3

            if step:
                field_info["step"] = step
            if field_info["name"]:
                fields.append(field_info)
            else:
                logger.warning(
                    f"Could not parse field name from input spec part: '{part}'"
                )
        return fields

    def _format_result_to_html(
        self,
        data: Any,
        level: int = 0,
        max_level: int = 5,
        max_str_len: int = 500,
    ) -> str:
        """Recursively formats a Python object (dict, list, Box, etc.) into an HTML string."""
        if hasattr(data, "to_dict") and callable(data.to_dict):
            data = data.to_dict()
        if level > max_level:
            return html.escape(f"[Max recursion depth {max_level} reached]")

        if isinstance(data, dict):
            if not data:
                return "<i>(empty dictionary)</i>"
            table_html = '<table style="width: 100%; border-collapse: collapse; margin-bottom: 10px; border: 1px solid #dee2e6;">'
            table_html += '<thead style="background-color: #e9ecef;"><tr><th style="text-align: left; padding: 8px; border-bottom: 2px solid #dee2e6;">Key</th><th style="text-align: left; padding: 8px; border-bottom: 2px solid #dee2e6;">Value</th></tr></thead>'
            table_html += "<tbody>"
            for key, value in data.items():
                escaped_key = html.escape(str(key))
                formatted_value = self._format_result_to_html(
                    value, level + 1, max_level, max_str_len
                )
                table_html += f'<tr><td style="vertical-align: top; padding: 8px; border-top: 1px solid #dee2e6;"><strong>{escaped_key}</strong></td><td style="padding: 8px; border-top: 1px solid #dee2e6;">{formatted_value}</td></tr>'
            table_html += "</tbody></table>"
            return table_html
        elif isinstance(data, (list, tuple)):
            if not data:
                return "<i>(empty list)</i>"
            # Use definition list for slightly cleaner look than ul/li for nested structures
            list_html = '<dl style="margin-left: 20px; padding-left: 0; margin-bottom: 10px;">'
            for i, item in enumerate(data):
                formatted_item = self._format_result_to_html(
                    item, level + 1, max_level, max_str_len
                )
                # Use dt/dd for list items
                list_html += f'<dt style="font-weight: bold; margin-top: 5px;">Item {i + 1}:</dt><dd style="margin-left: 20px; margin-bottom: 5px;">{formatted_item}</dd>'
            list_html += "</dl>"
            return list_html
        else:
            str_value = str(data)
            escaped_value = html.escape(str_value)
            if len(str_value) > max_str_len:
                escaped_value = (
                    html.escape(str_value[:max_str_len])
                    + f"... <i style='color: #6c757d;'>({len(str_value) - max_str_len} more chars)</i>"
                )

            style = ""
            if isinstance(data, bool):
                style = "color: #d63384; font-weight: bold;"  # Pinkish/bold for bools
            elif isinstance(data, (int, float)):
                style = "color: #0d6efd;"  # Blue for numbers
            elif data is None:
                style = "color: #6c757d; font-style: italic;"
                escaped_value = "None"  # Grey/italic for None
            # Wrap in code tag for monospace and styling
            return f'<code style="{style}">{escaped_value}</code>'

    # --- Server Start/Stop ---

    def start(
        self, host: str = "0.0.0.0", port: int = 8344, create_ui: bool = False
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
                    fh_app = create_ui_app(self, api_host=host, api_port=port)
                    self.app.mount("/ui", fh_app, name="ui")
                    logger.info("FastHTML UI mounted successfully.")

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

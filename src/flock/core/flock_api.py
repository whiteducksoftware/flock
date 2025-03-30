# src/flock/core/flock_api.py
"""REST API server for Flock, with optional integrated UI."""

import uuid
from datetime import datetime
from typing import Any

import uvicorn
from fastapi import (
    BackgroundTasks,
    FastAPI,
    HTTPException,
)
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from flock.core.flock import Flock
from flock.core.logging.logging import get_logger
from flock.core.util.input_resolver import split_top_level

# --- Conditional FastHTML Imports ---
try:
    import httpx  # Needed for server-side requests from FastHTML routes
    from fasthtml.common import *

    FASTHTML_AVAILABLE = True
except ImportError:
    FASTHTML_AVAILABLE = False

    # Define dummy classes/functions if FastHTML is not available,
    # so the rest of the type hints don't break completely.
    class Request:
        pass

    class Titled:
        pass

    class Div:
        pass

    class H1:
        pass

    class P:
        pass

    class Label:
        pass

    class Select:
        pass

    class Option:
        pass

    class Form:
        pass

    class Button:
        pass

    class Span:
        pass

    class Script:
        pass

    class Style:
        pass

    class Hidden:
        pass

    class Textarea:
        pass

    class Input:
        pass

    def fast_app():
        return None, None

    def picolink():
        return None
# ------------------------------------

logger = get_logger("api")

# --- API Request/Response Models ---


class FlockAPIRequest(BaseModel):
    """Request model for running an agent."""

    agent_name: str = Field(..., description="Name of the agent to run")
    # Changed inputs to Any to handle potential structure from HTML form
    inputs: Any = Field(
        default_factory=dict,
        description="Input data for the agent (can be nested from UI)",
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


# --- Main API Class ---


class FlockAPI:
    """REST API server for Flock with optional integrated UI."""

    def __init__(self, flock: Flock):
        self.flock = flock
        self.app = FastAPI(title="Flock API")
        self.runs: dict[str, FlockAPIResponse] = {}
        self._setup_routes()  # Setup FastAPI routes first

    def _setup_routes(self):
        """Set up FastAPI API routes."""

        @self.app.post("/run/flock", response_model=FlockAPIResponse)
        async def run_flock(
            request: FlockAPIRequest, background_tasks: BackgroundTasks
        ):
            """Run a flock workflow starting with the specified agent."""
            try:
                run_id = str(uuid.uuid4())
                response = FlockAPIResponse(
                    run_id=run_id, status="starting", started_at=datetime.now()
                )
                self.runs[run_id] = response

                # Process inputs from UI form (prefixed with 'inputs.')
                processed_inputs = {}
                if isinstance(request.inputs, dict):
                    for key, value in request.inputs.items():
                        if key.startswith("inputs."):
                            processed_inputs[key[len("inputs.") :]] = value
                        # Keep non-prefixed keys as well, if any
                        elif (
                            key != "agent_name"
                        ):  # Don't pass agent_name as input
                            processed_inputs[key] = value
                else:
                    # Handle case where inputs might not be a dict (though unlikely from UI form)
                    processed_inputs = request.inputs if request.inputs else {}

                if request.async_run:
                    background_tasks.add_task(
                        self._run_flock,
                        run_id,
                        request.agent_name,
                        processed_inputs,  # Use processed inputs
                    )
                    response.status = "running"
                else:
                    await self._run_flock(
                        run_id,
                        request.agent_name,
                        processed_inputs,  # Use processed inputs
                    )

                # Return potentially updated status
                return self.runs.get(run_id, response)

            except ValueError as ve:
                logger.error(f"Value error starting run: {ve}")
                raise HTTPException(status_code=400, detail=str(ve))
            except Exception as e:
                logger.error(f"Error starting run: {e!s}", exc_info=True)
                # Update run status if possible
                if run_id in self.runs:
                    self.runs[run_id].status = "failed"
                    self.runs[
                        run_id
                    ].error = f"Internal server error: {type(e).__name__}"
                    self.runs[run_id].completed_at = datetime.now()
                raise HTTPException(
                    status_code=500,
                    detail=f"Internal server error: {type(e).__name__}",
                )

        @self.app.get("/run/{run_id}", response_model=FlockAPIResponse)
        async def get_run_status(run_id: str):
            """Get the status of a specific run."""
            if run_id not in self.runs:
                raise HTTPException(status_code=404, detail="Run not found")
            return self.runs[run_id]

        @self.app.get("/agents")
        async def list_agents():
            """List all available agents."""
            # Return simplified agent info for UI dropdown
            return {
                "agents": [
                    {
                        "name": agent.name,
                        "description": agent.description or agent.name,
                    }
                    for agent in self.flock.agents.values()
                ]
            }

        # Note: _run_agent endpoint is kept but not used by the UI
        @self.app.post("/run/agent", response_model=FlockAPIResponse)
        async def run_agent(
            request: FlockAPIRequest, background_tasks: BackgroundTasks
        ):
            """Run a single agent directly (not used by UI)."""
            try:
                run_id = str(uuid.uuid4())
                response = FlockAPIResponse(
                    run_id=run_id, status="starting", started_at=datetime.now()
                )
                self.runs[run_id] = response

                if request.async_run:
                    background_tasks.add_task(
                        self._run_agent,
                        run_id,
                        request.agent_name,
                        request.inputs,
                    )
                    response.status = "running"
                else:
                    await self._run_agent(
                        run_id, request.agent_name, request.inputs
                    )
                return self.runs[run_id]
            except Exception as e:
                logger.error(
                    f"Error starting single agent run: {e!s}", exc_info=True
                )
                raise HTTPException(status_code=500, detail=str(e))

    # --- Helper Methods ---

    async def _run_agent(
        self, run_id: str, agent_name: str, inputs: dict[str, Any]
    ):
        """Execute a single agent run (internal helper)."""
        try:
            if agent_name not in self.flock.agents:
                raise ValueError(f"Agent '{agent_name}' not found")
            agent = self.flock.agents[agent_name]
            result = await agent.run_async(inputs)

            self.runs[run_id].status = "completed"
            self.runs[run_id].result = result
            self.runs[run_id].completed_at = datetime.now()
        except Exception as e:
            logger.error(
                f"Error in single agent run {run_id}: {e!s}", exc_info=True
            )
            self.runs[run_id].status = "failed"
            self.runs[run_id].error = str(e)
            self.runs[run_id].completed_at = datetime.now()

    async def _run_flock(
        self, run_id: str, agent_name: str, inputs: dict[str, Any]
    ):
        """Execute a flock workflow run (internal helper)."""
        try:
            if agent_name not in self.flock.agents:
                raise ValueError(f"Starting agent '{agent_name}' not found")

            result = await self.flock.run_async(
                start_agent=agent_name, input=inputs
            )

            self.runs[run_id].status = "completed"
            # Result might be Box, convert to dict for JSON response
            self.runs[run_id].result = (
                dict(result) if hasattr(result, "to_dict") else result
            )
            self.runs[run_id].completed_at = datetime.now()

        except Exception as e:
            logger.error(f"Error in flock run {run_id}: {e!s}", exc_info=True)
            self.runs[run_id].status = "failed"
            self.runs[run_id].error = str(e)
            self.runs[run_id].completed_at = datetime.now()

    def _parse_input_spec(self, input_spec: str) -> list[dict[str, str]]:
        """Parses an agent input string into a list of field definitions."""
        fields = []
        if not input_spec:
            return fields
        # Assuming split_top_level exists and works correctly
        try:
            parts = split_top_level(input_spec)
        except NameError:
            logger.error("split_top_level utility function not found!")
            return fields  # Or raise?

        for part in parts:
            part = part.strip()
            if not part:
                continue
            field_info = {
                "name": "",
                "type": "str",
                "desc": "",
            }  # Default type str
            name_type_part, *desc_part = part.split("|", 1)
            if desc_part:
                field_info["desc"] = desc_part[0].strip()

            name_part, *type_part = name_type_part.split(":", 1)
            field_info["name"] = name_part.strip()
            if type_part:
                field_info["type"] = type_part[0].strip()

            # Basic type to HTML input type mapping
            html_type = "text"
            step = None
            if field_info["type"].startswith("int"):
                html_type = "number"
            elif field_info["type"].startswith("float"):
                html_type = "number"
                step = "any"  # Allow decimals for float
            elif field_info["type"].startswith("bool"):
                html_type = "checkbox"
            elif "list" in field_info["type"] or "dict" in field_info["type"]:
                html_type = "textarea"
                field_info["rows"] = 3  # Default rows for textarea

            field_info["html_type"] = html_type
            if step:
                field_info["step"] = step
            fields.append(field_info)
        return fields

    def _create_fasthtml_app(self, api_host: str, api_port: int) -> Any:
        """Creates and configures the FastHTML application."""
        if not FASTHTML_AVAILABLE:
            raise ImportError("FastHTML is not installed. Cannot create UI.")

        logger.debug("Creating FastHTML application instance")
        # Note: fast_app might have its own default headers, adjust as needed
        fh_app, fh_rt = fast_app(
            hdrs=(
                Script(
                    src="https://unpkg.com/htmx.org@1.9.10/dist/htmx.min.js"
                ),
                picolink,  # Use FastHTML's Pico CSS link helper
                Style("""
                body { padding: 20px; max-width: 800px; margin: auto; }
                label { display: block; margin-top: 1rem; font-weight: bold;}
                input, select, textarea { width: 100%; margin-top: 0.25rem; }
                button[type=submit] { margin-top: 1.5rem; }
                #result-area { margin-top: 2rem; background-color: #f8f9fa; padding: 15px; border: 1px solid #dee2e6; border-radius: 5px; white-space: pre-wrap; word-wrap: break-word; font-family: monospace; }
                .htmx-indicator { display: none; margin-left: 10px; font-style: italic; color: #6c757d; }
                .htmx-request .htmx-indicator { display: inline; }
                .htmx-request.htmx-indicator { display: inline; }
                .error-message { color: red; margin-top: 10px; }
            """),
            )
        )

        @fh_rt("/get-agent-inputs")
        def get_agent_inputs(request: Request):
            """Endpoint called by HTMX to get agent input fields."""
            agent_name = request.query_params.get("agent_name")
            logger.debug(f"UI requesting inputs for agent: {agent_name}")
            if not agent_name:
                return Div("Please select an agent.", cls="error-message")

            agent_def = self.flock.agents.get(agent_name)
            if not agent_def:
                logger.warning(
                    f"Agent '{agent_name}' not found for UI input generation."
                )
                return Div(
                    f"Agent '{agent_name}' not found.", cls="error-message"
                )

            input_fields = self._parse_input_spec(agent_def.input or "")
            logger.debug(
                f"Parsed input fields for {agent_name}: {input_fields}"
            )

            inputs_html = []
            for field in input_fields:
                label = Label(
                    f"{field['name']} ({field['type']})", fr=field["name"]
                )
                input_attrs = dict(
                    id=field["name"],
                    name=f"inputs.{field['name']}",
                    type=field["html_type"],
                )
                if field.get("step"):
                    input_attrs["step"] = field["step"]
                if field.get("desc"):
                    input_attrs["placeholder"] = field["desc"]
                if field.get("rows"):
                    input_attrs["rows"] = field["rows"]

                if field["html_type"] == "textarea":
                    input_el = Textarea(**input_attrs)
                elif field["html_type"] == "checkbox":
                    # Checkboxes need careful value handling. Simple "true" for now.
                    input_el = Div(
                        Input(
                            **input_attrs, value="true"
                        ),  # Send "true" if checked
                        Label(
                            f" Enable {field['name']}?",
                            fr=field["name"],
                            style="display: inline; margin-left: 5px; font-weight: normal;",
                        ),
                    )
                else:
                    input_el = Input(**input_attrs)

                inputs_html.append(Div(label, input_el))

            # Include agent name as hidden input for the main form submission
            inputs_html.append(
                Hidden(
                    id="selected_agent_name",
                    name="agent_name",
                    value=agent_name,
                )
            )

            return (
                Div(*inputs_html)
                if inputs_html
                else P("This agent requires no input.")
            )

        @fh_rt("/")
        async def ui_root(request: Request):
            """Serves the main UI page."""
            logger.info("Serving main UI page /ui/")
            agents_list = []
            error_msg = None
            api_url = f"http://{api_host}:{api_port}/agents"
            try:
                async with httpx.AsyncClient() as client:
                    logger.debug(f"UI fetching agents from {api_url}")
                    response = await client.get(api_url)
                    response.raise_for_status()
                    agent_data = response.json()
                    agents_list = agent_data.get("agents", [])
                    logger.debug(
                        f"Successfully fetched {len(agents_list)} agents for UI"
                    )
            except httpx.RequestError as e:
                error_msg = f"UI Error: Could not connect to API at {api_url}. Is the API running? Details: {e}"
                logger.error(error_msg)
            except httpx.HTTPStatusError as e:
                error_msg = f"UI Error: API returned status {e.response.status_code}. Details: {e.response.text}"
                logger.error(error_msg)
            except Exception as e:
                error_msg = f"UI Error: An unexpected error occurred while fetching agents: {e}"
                logger.error(error_msg, exc_info=True)

            options = [
                Option(
                    "--- Select Agent ---",
                    value="",
                    selected=True,
                    disabled=True,
                )
            ] + [
                Option(
                    f"{agent['name']}: {agent['description']}",
                    value=agent["name"],
                )
                for agent in agents_list
            ]

            content = Div(
                H1("Flock Agent Runner UI"),
                P(
                    "Select an agent, provide the required inputs, and click 'Run Agent'."
                ),
                Label("Select Agent:", fr="agent_select"),
                Select(
                    *options,
                    id="agent_select",
                    name="agent_name",
                    hx_get="/ui/get-agent-inputs",  # Fetch inputs dynamically
                    hx_trigger="change",
                    hx_target="#agent-inputs-container",  # Target the container
                    hx_indicator="#loading-indicator",
                ),
                # Container for dynamic inputs
                Form(  # Wrap inputs and button in a form
                    Div(
                        id="agent-inputs-container"
                    ),  # Inputs will be loaded here
                    Button("Run Agent", type="submit"),
                    Span(
                        " Processing...",
                        id="loading-indicator",
                        cls="htmx-indicator",
                    ),
                    hx_post="/run/flock",  # POST to the FastAPI endpoint
                    hx_target="#result-area",  # Target the result area
                    hx_swap="innerHTML",  # Replace its content
                    hx_indicator="#loading-indicator",  # Show indicator during request
                ),
                H2("Result"),
                Div(
                    Pre(
                        Code("Result will appear here...", id="result-content")
                    ),  # Use Pre/Code for JSON
                    id="result-area",
                    style="min-height: 100px; border: 1px solid #ccc;",
                ),
            )

            if error_msg:
                content = Div(
                    H1("Flock UI - Error"), P(error_msg, cls="error-message")
                )

            return Titled(
                "Flock UI", content
            )  # Titled provides basic HTML structure

        return fh_app

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
                    # Pass host/port so FastHTML routes can call back to the API
                    fh_app = self._create_fasthtml_app(
                        api_host=host, api_port=port
                    )
                    # Mount the FastHTML app under the FastAPI app at /ui
                    self.app.mount("/ui", fh_app, name="ui")
                    logger.info("FastHTML UI mounted successfully.")

                    # Add a root redirect to /ui for convenience
                    @self.app.get(
                        "/",
                        include_in_schema=False,
                        response_class=RedirectResponse,
                    )
                    async def root_redirect():
                        logger.debug("Redirecting / to /ui/")
                        return "/ui/"  # FastAPI handles the redirect response generation

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

        # Run the main FastAPI app (which now might include the mounted UI)
        uvicorn.run(self.app, host=host, port=port)

    async def stop(self):
        """Stop the API server."""
        logger.info("Stopping API server (cleanup if necessary)")
        pass  # Add cleanup logic if needed

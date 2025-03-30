# src/flock/core/flock_api.py
"""REST API server for Flock, with optional integrated UI."""

import json
import uuid
from datetime import datetime
from typing import Any

import uvicorn

# FastAPI related imports
from fastapi import (
    BackgroundTasks,
    FastAPI,
    Form,  # Needed for form data handling
    HTTPException,
    Request as FastAPIRequest,
)
from fastapi.responses import HTMLResponse, RedirectResponse

# Pydantic for models
from pydantic import BaseModel, Field

# Flock core imports
from flock.core.flock import Flock
from flock.core.logging.logging import get_logger
from flock.core.serialization.json_encoder import (
    FlockJSONEncoder,  # For encoding results
)
from flock.core.util.input_resolver import (
    split_top_level,  # Ensure this utility is correct
)

# --- Conditional FastHTML Imports ---
try:
    import httpx  # Needed for server-side requests from FastHTML routes
    from fasthtml.common import *

    FASTHTML_AVAILABLE = True
except ImportError:
    FASTHTML_AVAILABLE = False

    # Define dummy classes/functions if FastHTML is not available
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

    class H2:
        pass

    class Pre:
        pass

    class Code:
        pass

    class Label:
        pass

    class Select:
        pass

    class Option:
        pass

    # class Form as FHForm: pass # Alias to avoid clash with FastAPI's Form
    class Form:
        pass  # Original Form class

    class FHForm(Form):
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
    """Request model for running an agent via JSON API."""

    agent_name: str = Field(..., description="Name of the agent to run")
    inputs: dict[str, Any] = Field(
        default_factory=dict, description="Input data for the agent"
    )
    async_run: bool = Field(
        default=False, description="Whether to run asynchronously"
    )


class FlockAPIResponse(BaseModel):
    """Response model for API run requests."""

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
            run_id = None  # Define run_id here to be available in except block
            try:
                run_id = str(uuid.uuid4())
                response = FlockAPIResponse(
                    run_id=run_id, status="starting", started_at=datetime.now()
                )
                self.runs[run_id] = response

                processed_inputs = request.inputs if request.inputs else {}

                if request.async_run:
                    background_tasks.add_task(
                        self._run_flock,
                        run_id,
                        request.agent_name,
                        processed_inputs,
                    )
                    response.status = "running"
                else:
                    await self._run_flock(
                        run_id, request.agent_name, processed_inputs
                    )

                return self.runs.get(run_id, response)
            except ValueError as ve:
                logger.error(f"Value error starting run: {ve}")
                raise HTTPException(status_code=400, detail=str(ve))
            except Exception as e:
                logger.error(f"Error starting run: {e!s}", exc_info=True)
                if (
                    run_id and run_id in self.runs
                ):  # Check if run_id was assigned
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
            if run_id not in self.runs:
                raise HTTPException(status_code=404, detail="Run not found")
            return self.runs[run_id]

        @self.app.get("/agents", tags=["API"])
        async def list_agents():
            """List all available agents."""
            return {
                "agents": [
                    {
                        "name": agent.name,
                        "description": agent.description or agent.name,
                    }
                    for agent in self.flock.agents.values()
                ]
            }

        # --- UI Form Endpoint ---
        @self.app.post(
            "/ui/run-agent-form", response_class=HTMLResponse, tags=["UI"]
        )
        async def run_flock_form(
            fastapi_req: FastAPIRequest,  # Use raw request to get form data
            # background_tasks: BackgroundTasks # Not using async for UI simplicity now
        ):
            """Endpoint to handle form submissions from the UI."""
            run_id = None  # Define run_id here
            try:
                form_data = await fastapi_req.form()
                agent_name = form_data.get("agent_name")
                # async_run = False # UI doesn't support async toggle, default to False

                if not agent_name:
                    return HTMLResponse(
                        '<div class="error-message">Error: Agent name not provided in form.</div>',
                        status_code=400,
                    )

                logger.info(
                    f"UI Form submission received for agent: {agent_name}"
                )

                # Reconstruct inputs dict from form data (removing 'inputs.' prefix)
                form_inputs = {}
                for key, value in form_data.items():
                    if key.startswith("inputs."):
                        # Handle checkboxes - unchecked boxes might not be sent by the browser
                        # If a checkbox input field exists but isn't in form_data, treat it as false
                        field_key = key[len("inputs.") :]
                        # Simple check based on expected type hint (could be improved)
                        agent_def = self.flock.agents.get(agent_name)
                        parsed_fields = self._parse_input_spec(
                            agent_def.input or ""
                        )
                        field_meta = next(
                            (
                                f
                                for f in parsed_fields
                                if f["name"] == field_key
                            ),
                            None,
                        )
                        if field_meta and field_meta["html_type"] == "checkbox":
                            form_inputs[field_key] = (
                                True  # Value is 'true' if sent
                            )
                        else:
                            form_inputs[field_key] = value
                # Add False for any defined boolean inputs that weren't submitted
                agent_def = self.flock.agents.get(agent_name)
                if agent_def and agent_def.input:
                    parsed_fields = self._parse_input_spec(agent_def.input)
                    for field in parsed_fields:
                        if (
                            field["html_type"] == "checkbox"
                            and field["name"] not in form_inputs
                        ):
                            form_inputs[field["name"]] = False

                logger.debug(f"Parsed form inputs: {form_inputs}")

                run_id = str(uuid.uuid4())
                response_status = FlockAPIResponse(
                    run_id=run_id, status="starting", started_at=datetime.now()
                )
                self.runs[run_id] = response_status

                # Run synchronously for UI
                await self._run_flock(run_id, agent_name, form_inputs)

                final_status = self.runs.get(run_id)

                if final_status and final_status.status == "completed":
                    result_json = json.dumps(
                        final_status.result, indent=2, cls=FlockJSONEncoder
                    )
                    # Use class_ to avoid conflict with Python keyword
                    return HTMLResponse(
                        f"<pre><code id='result-content' class_='language-json'>{result_json}</code></pre>"
                    )
                elif final_status and final_status.status == "failed":
                    logger.error(
                        f"UI run failed (run_id: {run_id}): {final_status.error}"
                    )
                    return HTMLResponse(
                        f"<div id='result-content' class='error-message'>Run Failed: {final_status.error or 'Unknown error'}</div>",
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
                return HTMLResponse(
                    f"<div id='result-content' class='error-message'>Error: {ve}</div>",
                    status_code=400,
                )
            except Exception as e:
                logger.error(
                    f"Error processing UI form run: {e!s}", exc_info=True
                )
                if (
                    run_id and run_id in self.runs
                ):  # Check if run_id was assigned
                    self.runs[run_id].status = "failed"
                    self.runs[
                        run_id
                    ].error = f"Internal server error: {type(e).__name__}"
                    self.runs[run_id].completed_at = datetime.now()
                return HTMLResponse(
                    f"<div id='result-content' class='error-message'>Internal Server Error: {type(e).__name__}</div>",
                    status_code=500,
                )

    # --- Helper Methods ---

    async def _run_agent(
        self, run_id: str, agent_name: str, inputs: dict[str, Any]
    ):
        """Executes a single agent run (internal helper)."""
        try:
            if agent_name not in self.flock.agents:
                raise ValueError(f"Agent '{agent_name}' not found")
            agent = self.flock.agents[agent_name]
            result = await agent.run_async(inputs)

            self.runs[run_id].status = "completed"
            self.runs[run_id].result = (
                dict(result) if hasattr(result, "to_dict") else result
            )
            self.runs[run_id].completed_at = datetime.now()
        except Exception as e:
            logger.error(
                f"Error in single agent run {run_id}: {e!s}", exc_info=True
            )
            self.runs[run_id].status = "failed"
            self.runs[run_id].error = str(e)
            self.runs[run_id].completed_at = datetime.now()
            # Re-raise for the main handler to catch and return HTTP error
            raise

    async def _run_flock(
        self, run_id: str, agent_name: str, inputs: dict[str, Any]
    ):
        """Executes a flock workflow run (internal helper)."""
        try:
            if agent_name not in self.flock.agents:
                raise ValueError(f"Starting agent '{agent_name}' not found")

            result = await self.flock.run_async(
                start_agent=agent_name, input=inputs
            )

            self.runs[run_id].status = "completed"
            self.runs[run_id].result = (
                dict(result) if hasattr(result, "to_dict") else result
            )
            self.runs[run_id].completed_at = datetime.now()
        except Exception as e:
            logger.error(f"Error in flock run {run_id}: {e!s}", exc_info=True)
            self.runs[run_id].status = "failed"
            self.runs[run_id].error = str(e)
            self.runs[run_id].completed_at = datetime.now()
            # Re-raise for the main handler to catch and return HTTP error
            raise

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
                field_info["type"] = type_part[0].strip()

            # Basic type to HTML input type mapping
            step = None
            if field_info["type"].startswith("int"):
                field_info["html_type"] = "number"
            elif field_info["type"].startswith("float"):
                field_info["html_type"] = "number"
                step = "any"
            elif field_info["type"].startswith("bool"):
                field_info["html_type"] = "checkbox"
            elif "list" in field_info["type"] or "dict" in field_info["type"]:
                field_info["html_type"] = "textarea"
                field_info["rows"] = 3

            if step:
                field_info["step"] = step
            fields.append(field_info)
        return fields

    def _create_fasthtml_app(self, api_host: str, api_port: int) -> Any:
        """Creates and configures the FastHTML application."""
        if not FASTHTML_AVAILABLE:
            raise ImportError("FastHTML is not installed.")
        logger.debug("Creating FastHTML application instance")

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
                input[type=checkbox] { width: auto; margin-right: 0.5rem; vertical-align: middle; }
                label[for^=inputs] { font-weight: normal; display: inline; } /* Style for checkbox labels */
                button[type=submit] { margin-top: 1.5rem; }
                #result-area { margin-top: 2rem; background-color: #f8f9fa; padding: 15px; border: 1px solid #dee2e6; border-radius: 5px; white-space: pre-wrap; word-wrap: break-word; font-family: monospace; }
                .htmx-indicator { display: none; margin-left: 10px; font-style: italic; color: #6c757d; }
                .htmx-request .htmx-indicator { display: inline; }
                .htmx-request.htmx-indicator { display: inline; }
                .error-message { color: red; margin-top: 10px; font-weight: bold; background-color: #f8d7da; border: 1px solid #f5c6cb; padding: 10px; border-radius: 5px;}
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
                logger.warning(f"Agent '{agent_name}' not found for UI.")
                return Div(
                    f"Agent '{agent_name}' not found.", cls="error-message"
                )

            input_fields = self._parse_input_spec(agent_def.input or "")
            logger.debug(
                f"Parsed input fields for {agent_name}: {input_fields}"
            )

            inputs_html = []
            for field in input_fields:
                field_id = (
                    f"input_{field['name']}"  # Ensure unique ID if name clashes
                )
                label = Label(f"{field['name']} ({field['type']})", fr=field_id)
                input_attrs = dict(
                    id=field_id,
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
                    input_el = Div(
                        Input(**input_attrs, value="true"),
                        Label(f" Enable?", fr=field_id),
                    )  # Simplified label
                else:
                    input_el = Input(**input_attrs)

                inputs_html.append(Div(label, input_el))

            # Add hidden input with agent name for the main form
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
                    logger.debug(f"Fetched {len(agents_list)} agents for UI")
            except Exception as e:
                error_msg = f"UI Error: Could not fetch agent list from API at {api_url}. Details: {e}"
                logger.error(error_msg, exc_info=True)

            options = [
                Option(
                    "-- Select Agent --", value="", selected=True, disabled=True
                )
            ] + [
                Option(
                    f"{agent['name']}: {agent['description']}",
                    value=agent["name"],
                )
                for agent in agents_list
            ]

            # Use FHForm alias for fasthtml.Form to avoid clash with FastAPI.Form
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
                    hx_get="/ui/get-agent-inputs",
                    hx_trigger="change",
                    hx_target="#agent-inputs-container",
                    hx_indicator="#loading-indicator",
                ),
                FHForm(  # Use FHForm alias here
                    Div(id="agent-inputs-container"),  # Inputs loaded here
                    Button("Run Agent", type="submit"),
                    Span(
                        " Processing...",
                        id="loading-indicator",
                        cls="htmx-indicator",
                    ),
                    hx_post="/ui/run-agent-form",  # Target the dedicated form endpoint
                    hx_target="#result-area",
                    hx_swap="innerHTML",
                    hx_indicator="#loading-indicator",
                ),
                H2("Result"),
                Div(
                    Pre(
                        Code(
                            "Result will appear here...",
                            id="result-content",
                            class_="language-json",
                        )
                    ),  # Add class for potential JS syntax highlighting
                    id="result-area",
                    style="min-height: 100px;",
                ),
            )

            if error_msg:
                content = Div(
                    H1("Flock UI - Error"), P(error_msg, cls="error-message")
                )

            return Titled("Flock UI", content)

        return fh_app

    # --- start() and stop() methods ---

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
                    fh_app = self._create_fasthtml_app(
                        api_host=host, api_port=port
                    )
                    self.app.mount("/ui", fh_app, name="ui")
                    logger.info("FastHTML UI mounted successfully.")

                    @self.app.get(
                        "/",
                        include_in_schema=False,
                        response_class=RedirectResponse,
                    )
                    async def root_redirect():
                        logger.debug("Redirecting / to /ui/")
                        return "/ui/"  # FastAPI handles RedirectResponse

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
        pass

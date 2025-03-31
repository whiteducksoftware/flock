# src/flock/core/api/ui/routes.py
"""FastHTML UI routes for the Flock API."""

from typing import TYPE_CHECKING

# --- Conditional FastHTML Imports ---
try:
    import httpx
    from fasthtml.common import *

    # Import Form explicitly with an alias to avoid collisions
    from fasthtml.common import Form as FHForm

    FASTHTML_AVAILABLE = True
except ImportError:
    FASTHTML_AVAILABLE = False

    # Define necessary dummies if not available
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

    class FHForm:
        pass  # Dummy alias if not available

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

# Use TYPE_CHECKING to avoid circular import errors for type hints
if TYPE_CHECKING:
    from flock.core.api.main import FlockAPI

# Import logger and utils needed by UI routes
from flock.core.logging.logging import get_logger

logger = get_logger("api.ui")


def create_ui_app(
    flock_api_instance: "FlockAPI",
    api_host: str,
    api_port: int,
    server_name: str,
) -> Any:
    """Creates and configures the FastHTML application and its routes."""
    if not FASTHTML_AVAILABLE:
        raise ImportError("FastHTML is not installed. Cannot create UI.")
    logger.debug("Creating FastHTML application instance for UI")

    # Use the passed FlockAPI instance to access necessary data/methods
    flock_instance = flock_api_instance.flock
    parse_input_spec_func = (
        flock_api_instance._parse_input_spec
    )  # Get reference to parser

    fh_app, fh_rt = fast_app(
        hdrs=(
            Script(src="https://unpkg.com/htmx.org@1.9.10/dist/htmx.min.js"),
            picolink,  # Pass directly
            Style("""
            body { padding: 20px; max-width: 800px; margin: auto; font-family: sans-serif; }
            label { display: block; margin-top: 1rem; font-weight: bold;}
            input, select, textarea { width: 100%; margin-top: 0.25rem; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
            input[type=checkbox] { width: auto; margin-right: 0.5rem; vertical-align: middle; }
            label[for^=input_] { font-weight: normal; display: inline; margin-top: 0;} /* Style for checkbox labels */
            button[type=submit] { margin-top: 1.5rem; padding: 0.75rem 1.5rem; background-color: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 1rem;}
            button[type=submit]:hover { background-color: #0056b3; }
            #result-area { margin-top: 2rem; background-color: #f8f9fa; padding: 15px; border: 1px solid #dee2e6; border-radius: 5px; white-space: pre-wrap; word-wrap: break-word; font-family: monospace; }
            .htmx-indicator { display: none; margin-left: 10px; font-style: italic; color: #6c757d; }
            .htmx-request .htmx-indicator { display: inline; }
            .htmx-request.htmx-indicator { display: inline; }
            .error-message { color: #721c24; margin-top: 10px; font-weight: bold; background-color: #f8d7da; border: 1px solid #f5c6cb; padding: 10px; border-radius: 5px;}
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

        # Access agents via the passed FlockAPI instance
        agent_def = flock_instance.agents.get(agent_name)
        if not agent_def:
            logger.warning(f"Agent '{agent_name}' not found for UI.")
            return Div(f"Agent '{agent_name}' not found.", cls="error-message")

        # Use the parsing function from the FlockAPI instance
        input_fields = parse_input_spec_func(agent_def.input or "")
        logger.debug(f"Parsed input fields for {agent_name}: {input_fields}")

        inputs_html = []
        for field in input_fields:
            field_id = f"input_{field['name']}"
            label_text = f"{field['name']}"
            if field["type"] != "bool":
                label_text += f" ({field['type']})"
            label = Label(label_text, fr=field_id)
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
                )
            else:
                input_el = Input(**input_attrs)

            inputs_html.append(
                Div(label, input_el, style="margin-bottom: 1rem;")
            )

        inputs_html.append(
            Hidden(
                id="selected_agent_name", name="agent_name", value=agent_name
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
            Option("-- Select Agent --", value="", selected=True, disabled=True)
        ] + [
            Option(
                f"{agent['name']}: {agent['description']}", value=agent["name"]
            )
            for agent in agents_list
        ]

        # Use FHForm alias here
        content = Div(
            H2(f"Agent Runner"),
            P(
                "Select an agent, provide the required inputs, and click 'Run Flock'."
            ),
            Label("Select Starting Agent:", fr="agent_select"),
            Select(
                *options,
                id="agent_select",
                name="agent_name",
                hx_get="/ui/get-agent-inputs",
                hx_trigger="change",
                hx_target="#agent-inputs-container",
                hx_indicator="#loading-indicator",
            ),
            FHForm(
                Div(id="agent-inputs-container", style="margin-top: 1rem;"),
                Button("Run Flock", type="submit"),
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
                ),
                id="result-area",
                style="min-height: 100px;",
            ),
        )

        if error_msg:
            content = Div(
                H1("Flock UI - Error"), P(error_msg, cls="error-message")
            )

        return Titled(f"{server_name}", content)

    return fh_app

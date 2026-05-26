# src/flock/webapp/app/api/agent_management.py
import json
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import (  # Added Depends and HTTPException
    APIRouter,
    Depends,
    Form,
    Request,
)
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

if TYPE_CHECKING:
    from flock.core.flock import Flock

# Import the dependency to get the current Flock instance
from flock.webapp.app.dependencies import (
    get_flock_instance,
    get_optional_flock_instance,
)

# Import service functions that now take app_state (or directly the Flock instance)
from flock.webapp.app.services.flock_service import (
    add_agent_to_current_flock_service,
    get_registered_items_service,  # This is fine as it doesn't depend on current_flock
    remove_agent_from_current_flock_service,
    update_agent_in_current_flock_service,
)

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent # Points to flock-ui/
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@router.get("/htmx/agent-list", response_class=HTMLResponse)
async def htmx_get_agent_list(
    request: Request,
    message: str = None,
    success: bool = None,
    # Use Depends to get the current flock instance.
    # Use get_optional_flock_instance if the route should work even without a flock loaded.
    current_flock: "Flock | None" = Depends(get_optional_flock_instance)
):
    if not current_flock:
        # If used in a context where flock might not be loaded (e.g. main agent manager view before load)
        # it should be handled by the page template or a higher-level redirect.
        # For a partial, returning an error or empty state is reasonable.
        return HTMLResponse("<div id='agent-list-container'><p class='error'>No Flock loaded to display agents.</p></div>", headers={"HX-Retarget": "#agent-list-container", "HX-Reswap": "innerHTML"})

    return templates.TemplateResponse(request, "partials/_agent_list.html",
        {
            "request": request,
            "flock": current_flock, # Pass the injected flock instance
            "message": message,
            "success": success,
        },
    )


@router.get("/htmx/agents/{agent_name}/details-form", response_class=HTMLResponse)
async def htmx_get_agent_details_form(
    request: Request,
    agent_name: str,
    current_flock: "Flock" = Depends(get_flock_instance) # Expect flock to be loaded
):
    # flock instance is now injected by FastAPI
    agent = current_flock.agents.get(agent_name)
    if not agent:
        return HTMLResponse(
            f"<p class='error'>Agent '{agent_name}' not found in the current Flock.</p>"
        )

    registered_tools = get_registered_items_service("tool")
    current_agent_tools = (
        [tool.__name__ for tool in agent.tools] if agent.tools else []
    )

    return templates.TemplateResponse(request, "partials/_agent_detail_form.html",
        {
            "request": request,
            "agent": agent,
            "is_new": False,
            "registered_tools": registered_tools,
            "current_tools": current_agent_tools,
        },
    )


@router.get("/htmx/agents/new-agent-form", response_class=HTMLResponse)
async def htmx_get_new_agent_form(
    request: Request,
    current_flock: "Flock" = Depends(get_flock_instance) # Expect flock for context, even for new agent
):
    # current_flock is injected, primarily to ensure context if needed by template/tools list
    registered_tools = get_registered_items_service("tool")
    return templates.TemplateResponse(request, "partials/_agent_detail_form.html",
        {
            "request": request,
            "agent": None,
            "is_new": True,
            "registered_tools": registered_tools,
            "current_tools": [],
        },
    )


@router.post("/htmx/agents", response_class=HTMLResponse)
async def htmx_create_agent(
    request: Request,
    agent_name: str = Form(...),
    agent_description: str = Form(""),
    agent_model: str = Form(None),
    input_signature: str = Form(...),
    output_signature: str = Form(...),
    tools: list[str] = Form([]),
    # current_flock: Flock = Depends(get_flock_instance) # Service will use app_state
):
    # The service function add_agent_to_current_flock_service now takes app_state
    if (not agent_name.strip() or not input_signature.strip() or not output_signature.strip()):
        registered_tools = get_registered_items_service("tool")
        return templates.TemplateResponse(request, "partials/_agent_detail_form.html",
            {
                "request": request, "agent": None, "is_new": True,
                "error_message": "Name, Input Signature, and Output Signature are required.",
                "registered_tools": registered_tools, "current_tools": tools,
            })

    agent_config = {
        "name": agent_name, "description": agent_description,
        "model": agent_model if agent_model and agent_model.strip() else None,
        "input": input_signature, "output": output_signature, "tools_names": tools,
    }
    # Pass request.app.state to the service function
    success = add_agent_to_current_flock_service(agent_config, request.app.state)

    response_headers = {}
    if success:
        response_headers["HX-Trigger"] = json.dumps({"agentListChanged": None, "notify": {"type":"success", "message": f"Agent '{agent_name}' created."}})


    # Re-render the form or an empty state for the detail panel
    # The agent list itself will be refreshed by the agentListChanged trigger
    new_form_context = {
        "request": request, "agent": None, "is_new": True,
        "registered_tools": get_registered_items_service("tool"),
        "current_tools": [], # Reset tools for new form
        "form_message": "Agent created successfully!" if success else "Failed to create agent. Check logs.",
        "success": success,
    }
    return templates.TemplateResponse(request, "partials/_agent_detail_form.html", new_form_context, headers=response_headers)


@router.put("/htmx/agents/{original_agent_name}", response_class=HTMLResponse)
async def htmx_update_agent(
    request: Request,
    original_agent_name: str,
    agent_name: str = Form(...),
    agent_description: str = Form(""),
    agent_model: str = Form(None),
    input_signature: str = Form(...),
    output_signature: str = Form(...),
    tools: list[str] = Form([]),
    # current_flock: Flock = Depends(get_flock_instance) # Service will use app_state
):
    agent_config = {
        "name": agent_name, "description": agent_description,
        "model": agent_model if agent_model and agent_model.strip() else None,
        "input": input_signature, "output": output_signature, "tools_names": tools,
    }
    # Pass request.app.state
    success = update_agent_in_current_flock_service(original_agent_name, agent_config, request.app.state)

    response_headers = {}
    if success:
        response_headers["HX-Trigger"] = json.dumps({"agentListChanged": None, "notify": {"type":"success", "message": f"Agent '{agent_name}' updated."}})


    # After update, get the (potentially renamed) agent from app.state's flock
    updated_agent_instance: Flock | None = getattr(request.app.state, 'flock_instance', None)
    updated_agent = updated_agent_instance.agents.get(agent_name) if updated_agent_instance else None

    registered_tools = get_registered_items_service("tool")
    current_agent_tools = []
    if updated_agent and updated_agent.tools:
        current_agent_tools = [tool.__name__ for tool in updated_agent.tools]

    updated_form_context = {
        "request": request, "agent": updated_agent, "is_new": False,
        "form_message": "Agent updated successfully!" if success else "Failed to update agent. Check logs.",
        "success": success,
        "registered_tools": registered_tools, "current_tools": current_agent_tools,
    }
    return templates.TemplateResponse(request, "partials/_agent_detail_form.html", updated_form_context, headers=response_headers)


@router.delete("/htmx/agents/{agent_name}", response_class=HTMLResponse)
async def htmx_delete_agent(
    request: Request,
    agent_name: str,
    # current_flock: Flock = Depends(get_flock_instance) # Service will use app_state
):
    # Pass request.app.state
    success = remove_agent_from_current_flock_service(agent_name, request.app.state)
    response_headers = {}

    if success:
        response_headers["HX-Trigger"] = json.dumps({"agentListChanged": None, "notify": {"type":"info", "message": f"Agent '{agent_name}' removed."}})
        # Return an empty agent detail form to clear that panel
        empty_form_context = {
            "request": request, "agent": None, "is_new": True,
            "registered_tools": get_registered_items_service("tool"),
            "current_tools": [],
            # "form_message": f"Agent '{agent_name}' removed.", # Message handled by notify
            # "success": True, # Not strictly needed if form is cleared
        }
        return templates.TemplateResponse(request, "partials/_agent_detail_form.html", empty_form_context, headers=response_headers)
    else:
        # Deletion failed, re-render the form for the agent that failed to delete (if it still exists)
        flock_instance_from_state: Flock | None = getattr(request.app.state, 'flock_instance', None)
        agent_still_exists = flock_instance_from_state.agents.get(agent_name) if flock_instance_from_state else None

        registered_tools = get_registered_items_service("tool")
        current_tools = []
        if agent_still_exists and agent_still_exists.tools:
            current_tools = [tool.__name__ for tool in agent_still_exists.tools]

        error_form_context = {
            "request": request, "agent": agent_still_exists, "is_new": False,
            "form_message": f"Failed to remove agent '{agent_name}'. It might have already been removed or an error occurred.",
            "success": False,
            "registered_tools": registered_tools, "current_tools": current_tools,
        }
        # Trigger a notification for the error as well
        response_headers["HX-Trigger"] = json.dumps({"notify": {"type":"error", "message": f"Failed to remove agent '{agent_name}'."}})
        return templates.TemplateResponse(request, "partials/_agent_detail_form.html", error_form_context, headers=response_headers)

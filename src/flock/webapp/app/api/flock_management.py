# src/flock/webapp/app/api/flock_management.py
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Form, Request  # Added Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

if TYPE_CHECKING:
    from flock.core.flock import Flock

# Import the dependency to get the current Flock instance
from flock.webapp.app.dependencies import (
    get_flock_instance,
)

# Service functions now take app_state
from flock.webapp.app.services.flock_service import (
    save_current_flock_to_file_service,
    update_flock_properties_service,
    # get_current_flock_filename IS NO LONGER IMPORTED
    # get_current_flock_instance IS NO LONGER IMPORTED
)

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@router.get("/htmx/flock-properties-form", response_class=HTMLResponse)
async def htmx_get_flock_properties_form(
    request: Request,
    update_message: str = None,
    success: bool = None,
    current_flock: "Flock" = Depends(get_flock_instance) # Expect flock to be loaded for this form
):
    # current_flock is now injected by FastAPI
    # Get the filename from app.state, as it's managed there
    current_filename: str | None = getattr(request.app.state, 'flock_filename', None)

    if not current_flock: # Should be caught by Depends if get_flock_instance raises error
        return HTMLResponse(
            "<div class='error'>Error: No flock loaded. Please load or create one first.</div>"
        )
    return templates.TemplateResponse(request, "partials/_flock_properties_form.html",
        {
            "request": request,
            "flock": current_flock,
            "current_filename": current_filename,
            "update_message": update_message,
            "success": success,
        },
    )


@router.post("/htmx/flock-properties", response_class=HTMLResponse)
async def htmx_update_flock_properties(
    request: Request,
    flock_name: str = Form(...),
    default_model: str = Form(...),
    description: str = Form(""),
    # current_flock: Flock = Depends(get_flock_instance) # Service will use app_state
):
    # Pass request.app.state to the service function
    success_update = update_flock_properties_service(
        flock_name, default_model, description, request.app.state
    )

    # Retrieve updated flock and filename from app.state for rendering the form
    updated_flock: Flock | None = getattr(request.app.state, 'flock_instance', None)
    updated_filename: str | None = getattr(request.app.state, 'flock_filename', None)

    return templates.TemplateResponse(request, "partials/_flock_properties_form.html",
        {
            "request": request,
            "flock": updated_flock,
            "current_filename": updated_filename,
            "update_message": "Flock properties updated!"
            if success_update
            else "Failed to update properties. Check logs.",
            "success": success_update,
        },
    )


@router.post("/htmx/save-flock", response_class=HTMLResponse)
async def htmx_save_flock(
    request: Request,
    save_filename: str = Form(...),
    # current_flock: Flock = Depends(get_flock_instance) # Service will use app_state
):
    current_flock_from_state: Flock | None = getattr(request.app.state, 'flock_instance', None)
    current_filename_from_state: str | None = getattr(request.app.state, 'flock_filename', None)

    if not save_filename.strip():
        return templates.TemplateResponse(request, "partials/_flock_properties_form.html",
            {
                "request": request,
                "flock": current_flock_from_state,
                "current_filename": current_filename_from_state,
                "save_message": "Filename cannot be empty.",
                "success": False,
            },
        )

    if not (save_filename.endswith(".yaml") or save_filename.endswith(".yml") or save_filename.endswith(".flock")):
        save_filename += ".flock.yaml"

    # Pass request.app.state to the service function
    success, message = save_current_flock_to_file_service(save_filename, request.app.state)

    # Retrieve potentially updated flock and filename from app.state
    saved_flock: Flock | None = getattr(request.app.state, 'flock_instance', None)
    saved_filename: str | None = getattr(request.app.state, 'flock_filename', None)


    return templates.TemplateResponse(request, "partials/_flock_properties_form.html",
        {
            "request": request,
            "flock": saved_flock, # Use the instance from app_state
            "current_filename": saved_filename, # Use the filename from app_state (updated on successful save)
            "save_message": message,
            "success": success,
        },
    )

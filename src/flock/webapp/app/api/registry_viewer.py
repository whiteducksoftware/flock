from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from flock.webapp.app.services.flock_service import get_registered_items_service

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@router.get("/htmx/{item_type}/table", response_class=HTMLResponse)
async def htmx_get_registry_table(request: Request, item_type: str):
    valid_item_types = ["type", "tool", "component"]
    if item_type not in valid_item_types:
        return HTMLResponse(
            "<p class='error'>Invalid item type requested.</p>", status_code=400
        )

    items = get_registered_items_service(item_type)
    return templates.TemplateResponse(request, "partials/_registry_table.html",
        {
            "request": request,
            "item_type_display": item_type.capitalize() + "s",
            "items": items,
        },
    )

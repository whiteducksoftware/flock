# src/flock/webapp/app/main.py
import asyncio
import json
import os  # Added import
import shutil

# Added for share link creation
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import markdown2  # Import markdown2
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from flock.core.api.endpoints import create_api_router
from flock.core.api.run_store import RunStore

# Import core Flock components and API related modules
from flock.core.flock import Flock  # For type hinting
from flock.core.flock_scheduler import FlockScheduler
from flock.core.logging.logging import get_logger  # For logging
from flock.core.util.splitter import parse_schema

# Import UI-specific routers
from flock.webapp.app.api import (
    agent_management,
    execution,
    flock_management,
    registry_viewer,
)
from flock.webapp.app.config import (
    DEFAULT_THEME_NAME,
    FLOCK_FILES_DIR,
    THEMES_DIR,
    get_current_theme_name,
)

# Import dependency management and config
from flock.webapp.app.dependencies import (
    get_pending_custom_endpoints_and_clear,
    get_shared_link_store,
    set_global_flock_services,
    set_global_shared_link_store,
)

# Import service functions (which now expect app_state)
from flock.webapp.app.middleware import ProxyHeadersMiddleware
from flock.webapp.app.services.flock_service import (
    clear_current_flock_service,
    create_new_flock_service,
    get_available_flock_files,
    get_flock_preview_service,
    load_flock_from_file_service,
    # Note: get_current_flock_instance/filename are removed from service,
    # as main.py will use request.app.state for this.
)

# Added for share link creation
from flock.webapp.app.services.sharing_models import SharedLinkConfig
from flock.webapp.app.services.sharing_store import (
    SharedLinkStoreInterface,
    create_shared_link_store,
)
from flock.webapp.app.theme_mapper import alacritty_to_pico

logger = get_logger("webapp.main")


try:
    from flock.core.logging.formatters.themed_formatter import (
        load_theme_from_file,
    )
    THEME_LOADER_AVAILABLE = True
except ImportError:
    logger.warning("Could not import flock.core theme loading utilities.")
    THEME_LOADER_AVAILABLE = False

# --- .env helpers (copied from original main.py for self-containment) ---
ENV_FILE_PATH = Path(".env") #Path(os.getenv("FLOCK_WEB_ENV_FILE", Path.home() / ".flock" / ".env"))
#ENV_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
SHOW_SECRETS_KEY = "SHOW_SECRETS"

def load_env_file_web() -> dict[str, str]:
    env_vars: dict[str, str] = {}
    if not ENV_FILE_PATH.exists(): return env_vars
    with open(ENV_FILE_PATH) as f: lines = f.readlines()
    for line in lines:
        line = line.strip()
        if not line: env_vars[""] = ""; continue
        if line.startswith("#"): env_vars[line] = ""; continue
        if "=" in line: k, v = line.split("=", 1); env_vars[k] = v
        else: env_vars[line] = ""
    return env_vars

def save_env_file_web(env_vars: dict[str, str]):
    try:
        with open(ENV_FILE_PATH, "w") as f:
            for k, v in env_vars.items():
                if k.startswith("#"): f.write(f"{k}\n")
                elif not k: f.write("\n")
                else: f.write(f"{k}={v}\n")
    except Exception as e: logger.error(f"[Settings] Failed to save .env: {e}")

def is_sensitive_web(key: str) -> bool:
    patterns = ["key", "token", "secret", "password", "api", "pat"]; low = key.lower()
    return any(p in low for p in patterns)

def mask_sensitive_value_web(value: str) -> str:
    if not value: return value
    if len(value) <= 4: return "••••"
    return value[:2] + "•" * (len(value) - 4) + value[-2:]

def create_hx_trigger_header(triggers: dict[str, Any]) -> str:
    """Helper function to create HX-Trigger header with JSON serialization."""
    return json.dumps(triggers)

def get_show_secrets_setting_web(env_vars: dict[str, str]) -> bool:
    return env_vars.get(SHOW_SECRETS_KEY, "false").lower() == "true"

def set_show_secrets_setting_web(show: bool):
    env_vars = load_env_file_web()
    env_vars[SHOW_SECRETS_KEY] = str(show)
    save_env_file_web(env_vars)
# --- End .env helpers ---


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("FastAPI application starting up...")
    # Flock instance and RunStore are expected to be set on app.state
    # by `start_unified_server` in `webapp/run.py` *before* uvicorn starts the app.
    # The call to `set_global_flock_services` also happens there.    # Initialize and set the SharedLinkStore
    try:
        logger.info("Initializing SharedLinkStore using factory...")
        shared_link_store = create_shared_link_store()
        await shared_link_store.initialize() # Create tables if they don't exist
        set_global_shared_link_store(shared_link_store)
        logger.info("SharedLinkStore initialized and set globally.")
    except Exception as e:
        logger.error(f"Failed to initialize SharedLinkStore: {e}", exc_info=True)# Configure chat features with clear precedence:
    # 1. Value set by start_unified_server (programmatic)
    # 2. Environment variables (standalone mode)
    programmatic_chat_enabled = getattr(app.state, "chat_enabled", None)
    env_start_mode = os.environ.get("FLOCK_START_MODE")
    env_chat_enabled = os.environ.get("FLOCK_CHAT_ENABLED", "false").lower() == "true"

    if programmatic_chat_enabled is not None:
        # Programmatic setting takes precedence (from start_unified_server)
        should_enable_chat_routes = programmatic_chat_enabled
        logger.info(f"Using programmatic chat_enabled setting: {should_enable_chat_routes}")
    elif env_start_mode == "chat":
        should_enable_chat_routes = True
        app.state.initial_redirect_to_chat = True
        app.state.chat_enabled = True
        logger.info("FLOCK_START_MODE='chat'. Enabling chat routes and setting redirect.")
    elif env_chat_enabled:
        should_enable_chat_routes = True
        app.state.chat_enabled = True
        logger.info("FLOCK_CHAT_ENABLED='true'. Enabling chat routes.")
    else:
        should_enable_chat_routes = False
        app.state.chat_enabled = False
        logger.info("Chat routes disabled (no programmatic or environment setting).")

    if should_enable_chat_routes:
        try:
            from flock.webapp.app.chat import router as chat_router
            app.include_router(chat_router, tags=["Chat"])
            logger.info("Chat routes included in the application.")
        except Exception as e:
            logger.error(f"Failed to include chat routes during lifespan startup: {e}", exc_info=True)    # If in standalone chat mode, strip non-essential UI routes
    if env_start_mode == "chat":
        from fastapi.routing import APIRoute
        logger.info("FLOCK_START_MODE='chat'. Stripping non-chat UI routes.")

        # Define tags for routes to KEEP.
        # "Chat" for primary chat functionality.
        # "Chat Sharing" for shared chat links & pages.
        # API tags might be needed if chat agents make internal API calls or for general health/docs.
        # Public static files (/static/...) are typically handled by app.mount and not in app.router.routes directly this way.
        allowed_tags_for_chat_mode = {
            "Chat",
            "Chat Sharing",
            "Flock API Core", # Keep core API for potential underlying needs
            "Flock API Custom Endpoints" # Keep custom API endpoints
        }

        def _route_is_allowed_in_chat_mode(route: APIRoute) -> bool:
            # Keep documentation (e.g. /docs, /openapi.json - usually no tags or specific tags)
            # and non-API utility routes (often no tags).
            if not hasattr(route, "tags") or not route.tags:
                # Check common doc paths explicitly as they might not have tags or might have default tags
                if route.path in ["/docs", "/openapi.json", "/redoc"]:
                    return True
                # Allow other untagged routes for now, assuming they are essential (e.g. static mounts if they appeared here)
                # This might need refinement if untagged UI routes exist.
                return True
            return any(tag in allowed_tags_for_chat_mode for tag in route.tags)

        original_route_count = len(app.router.routes)
        app.router.routes = [r for r in app.router.routes if _route_is_allowed_in_chat_mode(r)]
        num_removed = original_route_count - len(app.router.routes)
        logger.info(f"Stripped {num_removed} routes for chat-only mode. {len(app.router.routes)} routes remaining.")

        if num_removed > 0 and hasattr(app, "openapi_schema"):
            app.openapi_schema = None # Clear cached OpenAPI schema to regenerate
            logger.info("Cleared OpenAPI schema cache due to route removal.")

    # Add custom routes if any were passed during server startup
    # These are retrieved from the dependency module where `start_unified_server` stored them.
    pending_endpoints = get_pending_custom_endpoints_and_clear()
    if pending_endpoints:
        flock_instance_from_state: Flock | None = getattr(app.state, "flock_instance", None)
        if flock_instance_from_state:
            from flock.core.api.main import (
                FlockAPI,  # Local import for this specific task
            )
            # Create a temporary FlockAPI service object just for adding routes
            temp_flock_api_service = FlockAPI(
                flock_instance_from_state,
                custom_endpoints=pending_endpoints
            )
            temp_flock_api_service.add_custom_routes_to_app(app)
            logger.info(f"Lifespan: Added {len(pending_endpoints)} custom API routes to main app.")
        else:
            logger.warning("Lifespan: Pending custom endpoints found, but no Flock instance in app.state. Cannot add custom routes.")

    # --- Add Scheduler Startup Logic ---
    flock_instance_from_state: Flock | None = getattr(app.state, "flock_instance", None)
    if flock_instance_from_state:
        # Create and start the scheduler
        scheduler = FlockScheduler(flock_instance_from_state)
        app.state.flock_scheduler = scheduler  # Store for access during shutdown

        scheduler_loop_task = await scheduler.start() # Start returns the task
        if scheduler_loop_task:
            app.state.flock_scheduler_task = scheduler_loop_task # Store the task
            logger.info("FlockScheduler background task started.")
        else:
            app.state.flock_scheduler_task = None
            logger.info("FlockScheduler initialized, but no scheduled agents found or loop not started.")
    else:
        app.state.flock_scheduler = None
        app.state.flock_scheduler_task = None
        logger.warning("No Flock instance found in app.state; FlockScheduler not started.")
    # --- End Scheduler Startup Logic ---

    yield
    logger.info("FastAPI application shutting down...")

     # --- Add Scheduler Shutdown Logic ---
    logger.info("FastAPI application initiating shutdown...")
    scheduler_to_stop: FlockScheduler | None = getattr(app.state, "flock_scheduler", None)
    scheduler_task_to_await: asyncio.Task | None = getattr(app.state, "flock_scheduler_task", None)

    if scheduler_to_stop:
        logger.info("Attempting to stop FlockScheduler...")
        await scheduler_to_stop.stop() # Signal the scheduler loop to stop

        if scheduler_task_to_await and not scheduler_task_to_await.done():
            logger.info("Waiting for FlockScheduler task to complete...")
            try:
                await asyncio.wait_for(scheduler_task_to_await, timeout=10.0) # Wait for graceful exit
                logger.info("FlockScheduler task completed gracefully.")
            except asyncio.TimeoutError:
                logger.warning("FlockScheduler task did not complete in time, cancelling.")
                scheduler_task_to_await.cancel()
                try:
                    await scheduler_task_to_await # Await cancellation
                except asyncio.CancelledError:
                    logger.info("FlockScheduler task cancelled.")
            except Exception as e:
                logger.error(f"Error during FlockScheduler task finalization: {e}", exc_info=True)
        elif scheduler_task_to_await and scheduler_task_to_await.done():
            logger.info("FlockScheduler task was already done.")
        else:
            logger.info("FlockScheduler instance found, but no running task was stored to await.")
    else:
        logger.info("No active FlockScheduler found to stop.")

    logger.info("FastAPI application finished shutdown sequence.")
    # --- End Scheduler Shutdown Logic ---

app = FastAPI(title="Flock Web UI & API", lifespan=lifespan, docs_url="/docs",
    openapi_url="/openapi.json", root_path=os.getenv("FLOCK_ROOT_PATH", ""))

# Add middleware for handling proxy headers (HTTPS detection)
# You can force HTTPS by setting FLOCK_FORCE_HTTPS=true
force_https = os.getenv("FLOCK_FORCE_HTTPS", "false").lower() == "true"
app.add_middleware(ProxyHeadersMiddleware, force_https=force_https)
logger.info(f"FastAPI booting complete with proxy headers middleware (force_https={force_https}).")

BASE_DIR = Path(__file__).resolve().parent.parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Add markdown2 filter to Jinja2 environment
def markdown_filter(text):
    return markdown2.markdown(text, extras=["tables", "fenced-code-blocks"])

templates.env.filters['markdown'] = markdown_filter

core_api_router = create_api_router()
app.include_router(core_api_router, prefix="/api", tags=["Flock API Core"])
app.include_router(flock_management.router, prefix="/ui/api/flock", tags=["UI Flock Management"])
app.include_router(agent_management.router, prefix="/ui/api/flock", tags=["UI Agent Management"])
app.include_router(execution.router, prefix="/ui/api/flock", tags=["UI Execution"])
app.include_router(registry_viewer.router, prefix="/ui/api/registry", tags=["UI Registry"])

# --- Share Link API Models and Endpoint ---
class CreateShareLinkRequest(BaseModel):
    agent_name: str

class CreateShareLinkResponse(BaseModel):
    share_url: str

@app.post("/api/v1/share/link", response_model=CreateShareLinkResponse, tags=["UI Sharing"])
async def create_share_link(
    request: Request,
    request_data: CreateShareLinkRequest,
    store: SharedLinkStoreInterface = Depends(get_shared_link_store)
):
    """Creates a new shareable link for an agent."""
    share_id = uuid.uuid4().hex
    agent_name = request_data.agent_name

    if not agent_name: # Basic validation
        raise HTTPException(status_code=400, detail="Agent name cannot be empty.")

    current_flock_instance: Flock | None = getattr(request.app.state, "flock_instance", None)
    current_flock_filename: str | None = getattr(request.app.state, "flock_filename", None)

    if not current_flock_instance or not current_flock_filename:
        logger.error("Cannot create share link: No Flock is currently loaded in the application state.")
        raise HTTPException(status_code=400, detail="No Flock loaded. Cannot create share link.")

    if agent_name not in current_flock_instance.agents:
        logger.error(f"Agent '{agent_name}' not found in currently loaded Flock '{current_flock_instance.name}'.")
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found in current Flock.")

    try:
        flock_file_path = FLOCK_FILES_DIR / current_flock_filename
        if not flock_file_path.is_file():
            logger.warning(f"Flock file {current_flock_filename} not found at {flock_file_path} for sharing. Using in-memory definition.")
            flock_definition_str = current_flock_instance.to_yaml()
        else:
            flock_definition_str = flock_file_path.read_text()
    except Exception as e:
        logger.error(f"Failed to get flock definition for sharing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Could not retrieve Flock definition for sharing.")

    config = SharedLinkConfig(
        share_id=share_id,
        agent_name=agent_name,
        flock_definition=flock_definition_str
    )
    try:
        await store.save_config(config)
        share_url = f"/ui/shared-run/{share_id}" # Relative URL for client-side navigation
        logger.info(f"Created share link for agent '{agent_name}' in Flock '{current_flock_instance.name}' with ID '{share_id}'. URL: {share_url}")
        return CreateShareLinkResponse(share_url=share_url)
    except Exception as e:
        logger.error(f"Failed to create share link for agent '{agent_name}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create share link: {e!s}")

# --- End Share Link API ---

# --- HTMX Endpoint for Generating Share Link Snippet ---
@app.post("/ui/htmx/share/generate-link", response_class=HTMLResponse, tags=["UI Sharing HTMX"])
async def htmx_generate_share_link(
    request: Request,
    start_agent_name: str | None = Form(None),
    store: SharedLinkStoreInterface = Depends(get_shared_link_store)
):
    if not start_agent_name:
        logger.warning("HTMX generate share link: Agent name not provided.")
        return templates.TemplateResponse(
            "partials/_share_link_snippet.html",
            {"request": request, "error_message": "No agent selected to share."}
        )

    current_flock_instance: Flock | None = getattr(request.app.state, "flock_instance", None)
    current_flock_filename: str | None = getattr(request.app.state, "flock_filename", None)

    if not current_flock_instance or not current_flock_filename:
        logger.error("HTMX: Cannot create share link: No Flock is currently loaded.")
        return templates.TemplateResponse(
            "partials/_share_link_snippet.html",
            {"request": request, "error_message": "No Flock loaded. Cannot create share link."}
        )

    if start_agent_name not in current_flock_instance.agents:
        logger.error(f"HTMX: Agent '{start_agent_name}' not found in Flock '{current_flock_instance.name}'.")
        return templates.TemplateResponse(
            "partials/_share_link_snippet.html",
            {"request": request, "error_message": f"Agent '{start_agent_name}' not found in current Flock."}
        )

    try:
        flock_file_path = FLOCK_FILES_DIR / current_flock_filename
        if not flock_file_path.is_file():
            logger.warning(f"HTMX: Flock file {current_flock_filename} not found at {flock_file_path} for sharing. Using in-memory definition.")
            flock_definition_str = current_flock_instance.to_yaml()
        else:
            flock_definition_str = flock_file_path.read_text()
    except Exception as e:
        logger.error(f"HTMX: Failed to get flock definition for sharing: {e}", exc_info=True)
        return templates.TemplateResponse(
            "partials/_share_link_snippet.html",
            {"request": request, "error_message": "Could not retrieve Flock definition for sharing."}
        )

    share_id = uuid.uuid4().hex
    config = SharedLinkConfig(
        share_id=share_id,
        agent_name=start_agent_name,
        flock_definition=flock_definition_str
    )

    try:
        await store.save_config(config)
        base_url = str(request.base_url)
        full_share_url = f"{base_url.rstrip('/')}/ui/shared-run/{share_id}"

        logger.info(f"HTMX: Generated share link for agent '{start_agent_name}' in Flock '{current_flock_instance.name}' with ID '{share_id}'. URL: {full_share_url}")
        return templates.TemplateResponse(
            "partials/_share_link_snippet.html",
            {"request": request, "share_url": full_share_url, "flock_name": current_flock_instance.name, "agent_name": start_agent_name}
        )
    except Exception as e:
        logger.error(f"HTMX: Failed to create share link for agent '{start_agent_name}': {e}", exc_info=True)
        return templates.TemplateResponse(
            "partials/_share_link_snippet.html",
            {"request": request, "error_message": f"Could not generate link: {e!s}"}
        )
# --- End HTMX Endpoint ---

# --- HTMX Endpoint for Generating SHARED CHAT Link Snippet ---
@app.post("/ui/htmx/share/chat/generate-link", response_class=HTMLResponse, tags=["UI Sharing HTMX"])
async def htmx_generate_share_chat_link(
    request: Request,
    agent_name: str | None = Form(None), # This is the chat agent
    message_key: str | None = Form(None), # Changed default to None
    history_key: str | None = Form(None), # Changed default to None
    response_key: str | None = Form(None), # Changed default to None
    store: SharedLinkStoreInterface = Depends(get_shared_link_store)
):
    if not agent_name:
        logger.warning("HTMX generate share chat link: Agent name not provided.")
        return templates.TemplateResponse(
            "partials/_share_chat_link_snippet.html", # Will create this template
            {"request": request, "error_message": "No agent selected for chat sharing."}
        )

    current_flock_instance: Flock | None = getattr(request.app.state, "flock_instance", None)
    current_flock_filename: str | None = getattr(request.app.state, "flock_filename", None)

    if not current_flock_instance or not current_flock_filename:
        logger.error("HTMX Chat Share: Cannot create share link: No Flock is currently loaded.")
        return templates.TemplateResponse(
            "partials/_share_chat_link_snippet.html",
            {"request": request, "error_message": "No Flock loaded. Cannot create share link."}
        )

    if agent_name not in current_flock_instance.agents:
        logger.error(f"HTMX Chat Share: Agent '{agent_name}' not found in Flock '{current_flock_instance.name}'.")
        return templates.TemplateResponse(
            "partials/_share_chat_link_snippet.html",
            {"request": request, "error_message": f"Agent '{agent_name}' not found in current Flock."}
        )

    try:
        flock_file_path = FLOCK_FILES_DIR / current_flock_filename
        if not flock_file_path.is_file():
            logger.warning(f"HTMX Chat Share: Flock file {current_flock_filename} not found at {flock_file_path} for sharing. Using in-memory definition.")
            flock_definition_str = current_flock_instance.to_yaml()
        else:
            flock_definition_str = flock_file_path.read_text()
    except Exception as e:
        logger.error(f"HTMX Chat Share: Failed to get flock definition for sharing: {e}", exc_info=True)
        return templates.TemplateResponse(
            "partials/_share_chat_link_snippet.html",
            {"request": request, "error_message": "Could not retrieve Flock definition for sharing."}
        )

    share_id = uuid.uuid4().hex

    # Explicitly convert empty strings from form to None for optional keys
    actual_message_key = message_key if message_key else None
    actual_history_key = history_key if history_key else None
    actual_response_key = response_key if response_key else None

    config = SharedLinkConfig(
        share_id=share_id,
        agent_name=agent_name, # agent_name from form is the chat agent
        flock_definition=flock_definition_str,
        share_type="chat",
        chat_message_key=actual_message_key,
        chat_history_key=actual_history_key,
        chat_response_key=actual_response_key
    )

    try:
        await store.save_config(config)
        base_url = str(request.base_url)
        # Link to the new /chat/shared/{share_id} endpoint
        full_share_url = f"{base_url.rstrip('/')}/chat/shared/{share_id}"

        logger.info(f"HTMX: Generated share CHAT link for agent '{agent_name}' in Flock '{current_flock_instance.name}' with ID '{share_id}'. URL: {full_share_url}")
        return templates.TemplateResponse(
            "partials/_share_chat_link_snippet.html", # Will create this template
            {"request": request, "share_url": full_share_url, "flock_name": current_flock_instance.name, "agent_name": agent_name}
        )
    except Exception as e:
        logger.error(f"HTMX Chat Share: Failed to create share link for agent '{agent_name}': {e}", exc_info=True)
        return templates.TemplateResponse(
            "partials/_share_chat_link_snippet.html",
            {"request": request, "error_message": f"Could not generate chat link: {e!s}"}
        )

# --- Route for Shared Run Page ---
@app.get("/ui/shared-run/{share_id}", response_class=HTMLResponse, tags=["UI Sharing"])
async def page_shared_run(
    request: Request,
    share_id: str,
    store: SharedLinkStoreInterface = Depends(get_shared_link_store),
):
    logger.info(f"Accessed shared run page with share_id: {share_id}")
    shared_config = await store.get_config(share_id)

    if not shared_config:
        logger.warning(f"Share ID {share_id} not found.")
        return templates.TemplateResponse(
            "error_page.html",
            {"request": request, "error_title": "Link Not Found", "error_message": "The shared link does not exist or may have expired."},
            status_code=404
        )

    agent_name_from_link = shared_config.agent_name
    flock_definition_str = shared_config.flock_definition
    context: dict[str, Any] = {"request": request, "is_shared_run_page": True, "share_id": share_id}

    try:
        from flock.core.flock import Flock as ConcreteFlock
        loaded_flock = ConcreteFlock.from_yaml(flock_definition_str)

        # Store the loaded_flock instance in app.state for later retrieval
        if not hasattr(request.app.state, 'shared_flocks'):
            request.app.state.shared_flocks = {}
        request.app.state.shared_flocks[share_id] = loaded_flock
        logger.info(f"Shared Run Page: Stored Flock instance for share_id {share_id} in app.state.")

        context["flock"] = loaded_flock
        context["selected_agent_name"] = agent_name_from_link # For pre-selection & hidden field
        # flock_definition_str is no longer needed in the template for a hidden field if we reuse the instance
        # context["flock_definition_str"] = flock_definition_str
        logger.info(f"Shared Run Page: Loaded Flock '{loaded_flock.name}' for agent '{agent_name_from_link}'.")

        if agent_name_from_link not in loaded_flock.agents:
            context["error_message"] = f"Agent '{agent_name_from_link}' not found in the shared Flock definition."
            logger.warning(context["error_message"])
        else:
            agent = loaded_flock.agents[agent_name_from_link]
            input_fields = []
            if agent.input and isinstance(agent.input, str):
                try:
                    parsed_spec = parse_schema(agent.input) # parse_schema is imported at top of main.py
                    for name, type_str, description in parsed_spec:
                        field_info = {"name": name, "type": type_str.lower(), "description": description or ""}
                        if "bool" in field_info["type"]: field_info["html_type"] = "checkbox"
                        elif "int" in field_info["type"] or "float" in field_info["type"]: field_info["html_type"] = "number"
                        elif "list" in field_info["type"] or "dict" in field_info["type"]:
                            field_info["html_type"] = "textarea"; field_info["placeholder"] = f"Enter JSON for {field_info['type']}"
                        else: field_info["html_type"] = "text"
                        input_fields.append(field_info)
                    context["input_fields"] = input_fields
                except Exception as e_parse:
                    logger.error(f"Shared Run Page: Error parsing input for '{agent_name_from_link}': {e_parse}", exc_info=True)
                    context["error_message"] = f"Could not parse inputs for agent '{agent_name_from_link}'."
            else:
                context["input_fields"] = [] # Agent has no inputs defined

    except Exception as e_load:
        logger.error(f"Shared Run Page: Failed to load Flock from definition for share_id {share_id}: {e_load}", exc_info=True)
        context["error_message"] = f"Fatal: Could not load the shared Flock configuration: {e_load!s}"
        context["flock"] = None
        context["selected_agent_name"] = agent_name_from_link # Still pass for potential error display
        context["input_fields"] = []
        # context["flock_definition_str"] = flock_definition_str # Not needed if not sent to template

    try:
        current_theme_name = get_current_theme_name()
        context["theme_css"] = generate_theme_css_web(current_theme_name)
        context["active_theme_name"] = current_theme_name or DEFAULT_THEME_NAME
    except Exception as e_theme:
        logger.error(f"Shared Run Page: Error generating theme: {e_theme}", exc_info=True)
        context["theme_css"] = ""
        context["active_theme_name"] = DEFAULT_THEME_NAME

    # The shared_run_page.html will now be a simple wrapper that includes _execution_form.html
    return templates.TemplateResponse("shared_run_page.html", context)

# --- End Route for Shared Run Page ---

def generate_theme_css_web(theme_name: str | None) -> str:
    if not THEME_LOADER_AVAILABLE or THEMES_DIR is None: return ""

    chosen_theme_name_input = theme_name or get_current_theme_name() or DEFAULT_THEME_NAME

    # Sanitize the input to get only the filename component
    sanitized_name_part = Path(chosen_theme_name_input).name
    # Ensure we have a stem
    theme_stem_candidate = sanitized_name_part
    if theme_stem_candidate.endswith(".toml"):
        theme_stem_candidate = theme_stem_candidate[:-5]

    effective_theme_filename = f"{theme_stem_candidate}.toml"
    _theme_to_load_stem = theme_stem_candidate # This will be the name of the theme we attempt to load

    try:
        resolved_themes_dir = THEMES_DIR.resolve(strict=True) # Ensure THEMES_DIR itself is valid
        prospective_theme_path = resolved_themes_dir / effective_theme_filename

        # Resolve the prospective path
        resolved_theme_path = prospective_theme_path.resolve()

        # Validate:
        # 1. Path is still within the resolved THEMES_DIR
        # 2. The final filename component of the resolved path matches the intended filename
        #    (guards against symlinks or normalization changing the name unexpectedly)
        # 3. The file exists
        if (
            str(resolved_theme_path).startswith(str(resolved_themes_dir)) and
            resolved_theme_path.name == effective_theme_filename and
            resolved_theme_path.is_file() # is_file checks existence too
        ):
            theme_path = resolved_theme_path
        else:
            logger.warning(
                f"Validation failed or theme '{effective_theme_filename}' not found in '{resolved_themes_dir}'. "
                f"Attempted path: '{prospective_theme_path}'. Resolved to: '{resolved_theme_path}'. "
                f"Falling back to default theme: {DEFAULT_THEME_NAME}.toml"
            )
            _theme_to_load_stem = DEFAULT_THEME_NAME
            theme_path = resolved_themes_dir / f"{DEFAULT_THEME_NAME}.toml"
            if not theme_path.is_file():
                logger.error(f"Default theme file '{theme_path}' not found. No theme CSS will be generated.")
                return ""
    except FileNotFoundError: # THEMES_DIR does not exist
        logger.error(f"Themes directory '{THEMES_DIR}' not found. Falling back to default theme.")
        _theme_to_load_stem = DEFAULT_THEME_NAME
        # Attempt to use a conceptual default path if THEMES_DIR was bogus, though it's unlikely to succeed
        theme_path = Path(f"{DEFAULT_THEME_NAME}.toml") # This won't be in THEMES_DIR if THEMES_DIR is bad
        if not theme_path.exists(): # Check existence without assuming a base directory
             logger.error(f"Default theme file '{DEFAULT_THEME_NAME}.toml' not found at root or THEMES_DIR is inaccessible. No theme CSS.")
             return ""
    except Exception as e:
        logger.error(f"Error during theme path resolution for '{effective_theme_filename}': {e}. Falling back to default.")
        _theme_to_load_stem = DEFAULT_THEME_NAME
        theme_path = THEMES_DIR / f"{DEFAULT_THEME_NAME}.toml" if THEMES_DIR else Path(f"{DEFAULT_THEME_NAME}.toml")
        if not theme_path.exists():
            logger.error(f"Default theme file '{theme_path}' not found after error. No theme CSS.")
            return ""

    try:
        theme_dict = load_theme_from_file(str(theme_path))
        logger.debug(f"Successfully loaded theme '{_theme_to_load_stem}' from '{theme_path}'")
    except Exception as e:
        logger.error(f"Error loading theme file '{theme_path}' (intended: '{_theme_to_load_stem}.toml'): {e}")
        return ""

    pico_vars = alacritty_to_pico(theme_dict)
    if not pico_vars: return ""
    css_rules = [f"    {name}: {value};" for name, value in pico_vars.items()]
    css_string = ":root {\n" + "\n".join(css_rules) + "\n}"
    return css_string

def get_base_context_web(
    request: Request, error: str = None, success: str = None, ui_mode: str = "standalone"
) -> dict:
    flock_instance_from_state: Flock | None = getattr(request.app.state, "flock_instance", None)
    current_flock_filename_from_state: str | None = getattr(request.app.state, "flock_filename", None)
    theme_name = get_current_theme_name()
    theme_css = generate_theme_css_web(theme_name)

    return {
        "request": request,
        "current_flock": flock_instance_from_state,
        "current_filename": current_flock_filename_from_state,
        "error_message": error,
        "success_message": success,
        "ui_mode": ui_mode,
        "theme_css": theme_css,
        "active_theme_name": theme_name,
        "chat_enabled": getattr(request.app.state, "chat_enabled", False), # Reverted to app.state
    }

@app.get("/", response_class=HTMLResponse, tags=["UI Pages"])
async def page_dashboard(
    request: Request, error: str = None, success: str = None, ui_mode: str = Query(None)
):
    # Handle initial redirect if flagged during app startup
    if getattr(request.app.state, "initial_redirect_to_chat", False):
        logger.info("Initial redirect to CHAT page triggered from dashboard (FLOCK_START_MODE='chat').")
        # Use url_for to respect the root_path setting
        chat_url = str(request.url_for("page_chat"))
        return RedirectResponse(url=chat_url, status_code=307)

    effective_ui_mode = ui_mode
    flock_is_preloaded = hasattr(request.app.state, "flock_instance") and request.app.state.flock_instance is not None

    if effective_ui_mode is None:
        effective_ui_mode = "scoped" if flock_is_preloaded else "standalone"
        if effective_ui_mode == "scoped":
            # Manually construct URL with root_path to ensure it works with proxy setups
            root_path = request.scope.get("root_path", "")
            redirect_url = f"{root_path}/?ui_mode=scoped&initial_load=true"
            logger.info(f"Dashboard redirect: {redirect_url} (root_path: '{root_path}')")
            return RedirectResponse(url=redirect_url, status_code=307)

    if effective_ui_mode == "standalone" and flock_is_preloaded:
        clear_current_flock_service(request.app.state) # Pass app.state
        logger.info("Switched to standalone mode, cleared preloaded Flock instance from app.state.")

    context = get_base_context_web(request, error, success, effective_ui_mode)
    flock_in_state = hasattr(request.app.state, "flock_instance") and request.app.state.flock_instance is not None

    if effective_ui_mode == "scoped":
        context["initial_content_url"] = str(request.url_for("htmx_get_execution_view_container")) if flock_in_state else str(request.url_for("htmx_scoped_no_flock_view"))
    else:
        context["initial_content_url"] = str(request.url_for("htmx_get_load_flock_view"))
    return templates.TemplateResponse("base.html", context)

@app.get("/ui/editor/{section:path}", response_class=HTMLResponse, tags=["UI Pages"])
async def page_editor_section(
    request: Request, section: str, success: str = None, error: str = None, ui_mode: str = Query("standalone")
):
    flock_instance_from_state: Flock | None = getattr(request.app.state, "flock_instance", None)
    if not flock_instance_from_state:
        err_msg = "No flock loaded. Please load or create a flock first."
        # Use url_for to respect the root_path setting
        redirect_url = str(request.url_for("page_dashboard").include_query_params(error=err_msg))
        if ui_mode == "scoped":
            redirect_url = str(request.url_for("page_dashboard").include_query_params(error=err_msg, ui_mode="scoped"))
        return RedirectResponse(url=redirect_url, status_code=303)

    context = get_base_context_web(request, error, success, ui_mode)
    root_path = request.scope.get("root_path", "")
    content_map = {
        "properties": f"{root_path}/ui/api/flock/htmx/flock-properties-form",
        "agents": f"{root_path}/ui/htmx/agent-manager-view",
        "execute": f"{root_path}/ui/htmx/execution-view-container"
    }
    context["initial_content_url"] = content_map.get(section, f"{root_path}/ui/htmx/load-flock-view")
    if section not in content_map: context["error_message"] = "Invalid editor section."
    return templates.TemplateResponse("base.html", context)

@app.get("/ui/registry", response_class=HTMLResponse, tags=["UI Pages"])
async def page_registry(request: Request, error: str = None, success: str = None, ui_mode: str = Query("standalone")):
    context = get_base_context_web(request, error, success, ui_mode)
    root_path = request.scope.get("root_path", "")
    context["initial_content_url"] = f"{root_path}/ui/htmx/registry-viewer"
    return templates.TemplateResponse("base.html", context)

@app.get("/ui/create", response_class=HTMLResponse, tags=["UI Pages"])
async def page_create(request: Request, error: str = None, success: str = None, ui_mode: str = Query("standalone")):
    clear_current_flock_service(request.app.state) # Pass app.state
    context = get_base_context_web(request, error, success, "standalone")
    root_path = request.scope.get("root_path", "")
    context["initial_content_url"] = f"{root_path}/ui/htmx/create-flock-form"
    return templates.TemplateResponse("base.html", context)

@app.get("/ui/htmx/sidebar", response_class=HTMLResponse, tags=["UI HTMX Partials"])
async def htmx_get_sidebar(request: Request, ui_mode: str = Query("standalone")):
    return templates.TemplateResponse("partials/_sidebar.html", get_base_context_web(request, ui_mode=ui_mode))

@app.get("/ui/htmx/header-flock-status", response_class=HTMLResponse, tags=["UI HTMX Partials"])
async def htmx_get_header_flock_status(request: Request, ui_mode: str = Query("standalone")):
    return templates.TemplateResponse("partials/_header_flock_status.html", get_base_context_web(request, ui_mode=ui_mode))

@app.get("/ui/htmx/load-flock-view", response_class=HTMLResponse, tags=["UI HTMX Partials"])
async def htmx_get_load_flock_view(request: Request, error: str = None, success: str = None, ui_mode: str = Query("standalone")):
    return templates.TemplateResponse("partials/_load_manager_view.html", get_base_context_web(request, error, success, ui_mode))

@app.get("/ui/htmx/dashboard-flock-file-list", response_class=HTMLResponse, tags=["UI HTMX Partials"])
async def htmx_get_dashboard_flock_file_list_partial(request: Request):
    return templates.TemplateResponse("partials/_dashboard_flock_file_list.html", {"request": request, "flock_files": get_available_flock_files()})

@app.get("/ui/htmx/dashboard-default-action-pane", response_class=HTMLResponse, tags=["UI HTMX Partials"])
async def htmx_get_dashboard_default_action_pane(request: Request):
    return HTMLResponse("""<article style="text-align:center; margin-top: 2rem; border: none; background: transparent;"><p>Select a Flock from the list to view its details and load it into the editor.</p><hr><p>Or, create a new Flock or upload an existing one using the "Create New Flock" option in the sidebar.</p></article>""")

@app.get("/ui/htmx/dashboard-flock-properties-preview/{filename}", response_class=HTMLResponse, tags=["UI HTMX Partials"])
async def htmx_get_dashboard_flock_properties_preview(request: Request, filename: str):
    preview_flock_data = get_flock_preview_service(filename)
    return templates.TemplateResponse("partials/_dashboard_flock_properties_preview.html", {"request": request, "selected_filename": filename, "preview_flock": preview_flock_data})

@app.get("/ui/htmx/create-flock-form", response_class=HTMLResponse, tags=["UI HTMX Partials"])
async def htmx_get_create_flock_form(request: Request, error: str = None, success: str = None, ui_mode: str = Query("standalone")):
    return templates.TemplateResponse("partials/_create_flock_form.html", get_base_context_web(request, error, success, ui_mode))

@app.get("/ui/htmx/agent-manager-view", response_class=HTMLResponse, tags=["UI HTMX Partials"])
async def htmx_get_agent_manager_view(request: Request):
    context = get_base_context_web(request) # This gets flock from app.state
    if not context.get("current_flock"): # Check if flock exists in the context
        return HTMLResponse("<article class='error'><p>No flock loaded. Cannot manage agents.</p></article>")
    # Pass the 'current_flock' from the context to the template as 'flock'
    return templates.TemplateResponse(
        "partials/_agent_manager_view.html",
        {"request": request, "flock": context.get("current_flock")}
    )

@app.get("/ui/htmx/registry-viewer", response_class=HTMLResponse, tags=["UI HTMX Partials"])
async def htmx_get_registry_viewer(request: Request):
    return templates.TemplateResponse("partials/_registry_viewer_content.html", get_base_context_web(request))

@app.get("/ui/htmx/execution-view-container", response_class=HTMLResponse, tags=["UI HTMX Partials"])
async def htmx_get_execution_view_container(request: Request):
    context = get_base_context_web(request)
    if not context.get("current_flock"): return HTMLResponse("<article class='error'><p>No Flock loaded. Cannot execute.</p></article>")
    return templates.TemplateResponse("partials/_execution_view_container.html", context)

@app.get("/ui/htmx/scoped-no-flock-view", response_class=HTMLResponse, tags=["UI HTMX Partials"])
async def htmx_scoped_no_flock_view(request: Request):
    return HTMLResponse("""<article style="text-align:center; margin-top: 2rem; border: none; background: transparent;"><hgroup><h2>Scoped Flock Mode</h2><h3>No Flock Loaded</h3></hgroup><p>This UI is in a scoped mode, expecting a Flock to be pre-loaded.</p><p>Please ensure the calling application provides a Flock instance.</p></article>""")

# --- Action Routes (POST requests for UI interactions) ---
@app.post("/ui/load-flock-action/by-name", response_class=HTMLResponse, tags=["UI Actions"])
async def ui_load_flock_by_name_action(request: Request, selected_flock_filename: str = Form(...)):
    loaded_flock = load_flock_from_file_service(selected_flock_filename, request.app.state)
    response_headers = {}
    ui_mode_query = request.query_params.get("ui_mode", "standalone")
    if loaded_flock:
        success_message_text = f"Flock '{loaded_flock.name}' loaded from '{selected_flock_filename}'."
        response_headers["HX-Push-Url"] = "/ui/editor/execute?ui_mode=" + ui_mode_query
        response_headers["HX-Trigger"] = create_hx_trigger_header({"flockLoaded": None, "notify": {"type": "success", "message": success_message_text}})
        context = get_base_context_web(request, success=success_message_text, ui_mode=ui_mode_query)
        return templates.TemplateResponse("partials/_execution_view_container.html", context, headers=response_headers)
    else:
        error_message_text = f"Failed to load flock file '{selected_flock_filename}'."
        response_headers["HX-Trigger"] = create_hx_trigger_header({"notify": {"type": "error", "message": error_message_text}})
        context = get_base_context_web(request, error=error_message_text, ui_mode=ui_mode_query)
        context["error_message_inline"] = error_message_text # For direct display in partial
        return templates.TemplateResponse("partials/_load_manager_view.html", context, headers=response_headers)

@app.post("/ui/load-flock-action/by-upload", response_class=HTMLResponse, tags=["UI Actions"])
async def ui_load_flock_by_upload_action(request: Request, flock_file_upload: UploadFile = File(...)):
    error_message_text, filename_to_load, response_headers = None, None, {}
    ui_mode_query = request.query_params.get("ui_mode", "standalone")

    if flock_file_upload and flock_file_upload.filename:
        if not flock_file_upload.filename.endswith((".yaml", ".yml", ".flock")): error_message_text = "Invalid file type."
        else:
            upload_path = FLOCK_FILES_DIR / flock_file_upload.filename
            try:
                with upload_path.open("wb") as buffer: shutil.copyfileobj(flock_file_upload.file, buffer)
                filename_to_load = flock_file_upload.filename
            except Exception as e: error_message_text = f"Upload failed: {e}"
            finally: await flock_file_upload.close()
    else: error_message_text = "No file uploaded."

    if filename_to_load and not error_message_text:
        loaded_flock = load_flock_from_file_service(filename_to_load, request.app.state)
        if loaded_flock:
            success_message_text = f"Flock '{loaded_flock.name}' loaded from '{filename_to_load}'."
            response_headers["HX-Push-Url"] = f"/ui/editor/execute?ui_mode={ui_mode_query}"
            response_headers["HX-Trigger"] = create_hx_trigger_header({"flockLoaded": None, "flockFileListChanged": None, "notify": {"type": "success", "message": success_message_text}})
            context = get_base_context_web(request, success=success_message_text, ui_mode=ui_mode_query)
            return templates.TemplateResponse("partials/_execution_view_container.html", context, headers=response_headers)
        else: error_message_text = f"Failed to process uploaded '{filename_to_load}'."

    final_error_msg = error_message_text or "Upload failed."
    response_headers["HX-Trigger"] = create_hx_trigger_header({"notify": {"type": "error", "message": final_error_msg}})
    context = get_base_context_web(request, error=final_error_msg, ui_mode=ui_mode_query)
    return templates.TemplateResponse("partials/_create_flock_form.html", context, headers=response_headers)

@app.post("/ui/create-flock", response_class=HTMLResponse, tags=["UI Actions"])
async def ui_create_flock_action(request: Request, flock_name: str = Form(...), default_model: str = Form(None), description: str = Form(None)):
    ui_mode_query = request.query_params.get("ui_mode", "standalone")
    if not flock_name.strip():
        context = get_base_context_web(request, error="Flock name cannot be empty.", ui_mode=ui_mode_query)
        return templates.TemplateResponse("partials/_create_flock_form.html", context)

    new_flock = create_new_flock_service(flock_name, default_model, description, request.app.state)
    success_msg_text = f"New flock '{new_flock.name}' created. Navigating to Execute page. Configure properties and agents as needed."
    response_headers = {"HX-Push-Url": f"/ui/editor/execute?ui_mode={ui_mode_query}", "HX-Trigger": create_hx_trigger_header({"flockLoaded": None, "notify": {"type": "success", "message": success_msg_text}})}
    context = get_base_context_web(request, success=success_msg_text, ui_mode=ui_mode_query)
    return templates.TemplateResponse("partials/_execution_view_container.html", context, headers=response_headers)


# --- Settings Page & Endpoints ---
@app.get("/ui/settings", response_class=HTMLResponse, tags=["UI Pages"])
async def page_settings(request: Request, error: str = None, success: str = None, ui_mode: str = Query("standalone")):
    context = get_base_context_web(request, error, success, ui_mode)
    root_path = request.scope.get("root_path", "")
    context["initial_content_url"] = f"{root_path}/ui/htmx/settings-view"
    return templates.TemplateResponse("base.html", context)

def _prepare_env_vars_for_template_web():
    env_vars_raw = load_env_file_web(); show_secrets = get_show_secrets_setting_web(env_vars_raw)
    env_vars_list = []
    for name, value in env_vars_raw.items():
        if name.startswith("#") or name == "": continue
        display_value = value if (not is_sensitive_web(name) or show_secrets) else mask_sensitive_value_web(value)
        env_vars_list.append({"name": name, "value": display_value})
    return env_vars_list, show_secrets

@app.get("/ui/htmx/settings-view", response_class=HTMLResponse, tags=["UI HTMX Partials"])
async def htmx_get_settings_view(request: Request):
    env_vars_list, show_secrets = _prepare_env_vars_for_template_web()
    theme_name = get_current_theme_name()
    themes_available = [p.stem for p in THEMES_DIR.glob("*.toml")] if THEMES_DIR and THEMES_DIR.exists() else []
    return templates.TemplateResponse("partials/_settings_view.html", {"request": request, "env_vars": env_vars_list, "show_secrets": show_secrets, "themes": themes_available, "current_theme": theme_name})

@app.post("/ui/htmx/toggle-show-secrets", response_class=HTMLResponse, tags=["UI Actions"])
async def htmx_toggle_show_secrets(request: Request):
    env_vars_raw = load_env_file_web(); current = get_show_secrets_setting_web(env_vars_raw)
    set_show_secrets_setting_web(not current)
    env_vars_list, show_secrets = _prepare_env_vars_for_template_web()
    return templates.TemplateResponse("partials/_env_vars_table.html", {"request": request, "env_vars": env_vars_list, "show_secrets": show_secrets})

@app.post("/ui/htmx/env-delete", response_class=HTMLResponse, tags=["UI Actions"])
async def htmx_env_delete(request: Request, var_name: str = Form(...)):
    env_vars_raw = load_env_file_web()
    if var_name in env_vars_raw: del env_vars_raw[var_name]; save_env_file_web(env_vars_raw)
    env_vars_list, show_secrets = _prepare_env_vars_for_template_web()
    return templates.TemplateResponse("partials/_env_vars_table.html", {"request": request, "env_vars": env_vars_list, "show_secrets": show_secrets})

@app.post("/ui/htmx/env-edit", response_class=HTMLResponse, tags=["UI Actions"])
async def htmx_env_edit(request: Request, var_name: str = Form(...)):
    new_value = request.headers.get("HX-Prompt")
    env_vars_list, show_secrets = _prepare_env_vars_for_template_web()
    if new_value is not None:
        env_vars_raw = load_env_file_web()
        env_vars_raw[var_name] = new_value
        save_env_file_web(env_vars_raw)
        env_vars_list, show_secrets = _prepare_env_vars_for_template_web()
    return templates.TemplateResponse("partials/_env_vars_table.html", {"request": request, "env_vars": env_vars_list, "show_secrets": show_secrets})

@app.get("/ui/htmx/env-add-form", response_class=HTMLResponse, tags=["UI HTMX Partials"])
async def htmx_env_add_form(request: Request):
    return HTMLResponse("""<form hx-post='/ui/htmx/env-add' hx-target='#env-vars-container' hx-swap='outerHTML' style='display:flex; gap:0.5rem; margin-bottom:0.5rem;'><input name='var_name' placeholder='NAME' required style='flex:2;'><input name='var_value' placeholder='VALUE' style='flex:3;'><button type='submit'>Add</button></form>""")

@app.post("/ui/htmx/env-add", response_class=HTMLResponse, tags=["UI Actions"])
async def htmx_env_add(request: Request, var_name: str = Form(...), var_value: str = Form("")):
    env_vars_raw = load_env_file_web()
    env_vars_raw[var_name] = var_value; save_env_file_web(env_vars_raw)
    env_vars_list, show_secrets = _prepare_env_vars_for_template_web()
    return templates.TemplateResponse("partials/_env_vars_table.html", {"request": request, "env_vars": env_vars_list, "show_secrets": show_secrets})

@app.get("/ui/htmx/theme-preview", response_class=HTMLResponse, tags=["UI HTMX Partials"])
async def htmx_theme_preview(request: Request, theme: str = Query(None)):
    if not THEME_LOADER_AVAILABLE:
        return HTMLResponse("<p>Theme loading functionality is not available.</p>", status_code=500)
    if THEMES_DIR is None or not THEMES_DIR.exists():
        return HTMLResponse("<p>Themes directory is not configured or does not exist.</p>", status_code=500)

    chosen_theme_name_input = theme or get_current_theme_name() or DEFAULT_THEME_NAME

    # Sanitize the input to get only the filename component
    sanitized_name_part = Path(chosen_theme_name_input).name
    # Ensure we have a stem
    theme_stem_from_input = sanitized_name_part
    if theme_stem_from_input.endswith(".toml"):
        theme_stem_from_input = theme_stem_from_input[:-5]

    theme_filename_to_load = f"{theme_stem_from_input}.toml"
    theme_name_for_display = theme_stem_from_input # Use the sanitized stem for display/logging

    try:
        resolved_themes_dir = THEMES_DIR.resolve(strict=True)
        theme_path_candidate = resolved_themes_dir / theme_filename_to_load
        resolved_theme_path = theme_path_candidate.resolve()

        if not str(resolved_theme_path).startswith(str(resolved_themes_dir)) or \
           resolved_theme_path.name != theme_filename_to_load:
            logger.warning(f"Invalid theme path access attempt for '{theme_name_for_display}'. "
                           f"Original input: '{chosen_theme_name_input}', Sanitized filename: '{theme_filename_to_load}', "
                           f"Attempted path: '{theme_path_candidate}', Resolved to: '{resolved_theme_path}'")
            return HTMLResponse(f"<p>Invalid theme name or path for '{theme_name_for_display}'.</p>", status_code=400)

        if not resolved_theme_path.is_file():
            logger.info(f"Theme preview: Theme file '{theme_filename_to_load}' not found at '{resolved_theme_path}'.")
            return HTMLResponse(f"<p>Theme '{theme_name_for_display}' not found.</p>", status_code=404)

        theme_path = resolved_theme_path
        theme_data = load_theme_from_file(str(theme_path))
        logger.debug(f"Successfully loaded theme '{theme_name_for_display}' for preview from '{theme_path}'")

    except FileNotFoundError: # For THEMES_DIR.resolve(strict=True)
        logger.error(f"Themes directory '{THEMES_DIR}' not found during preview for '{theme_name_for_display}'.")
        return HTMLResponse("<p>Themes directory not found.</p>", status_code=500)
    except Exception as e:
        logger.error(f"Error loading theme '{theme_name_for_display}' for preview (path: '{theme_path_candidate if 'theme_path_candidate' in locals() else 'unknown'}'): {e}")
        return HTMLResponse(f"<p>Error loading theme '{theme_name_for_display}': {e}</p>", status_code=500)

    css_vars = alacritty_to_pico(theme_data)
    if not css_vars:
        return HTMLResponse(f"<p>Could not convert theme '{theme_name_for_display}' to CSS variables.</p>")

    css_vars_str = ":root {\n" + "\\n".join([f"  {k}: {v};" for k, v in css_vars.items()]) + "\\n}"
    main_colors = [("Background", css_vars.get("--pico-background-color")), ("Text", css_vars.get("--pico-color")), ("Primary", css_vars.get("--pico-primary")), ("Secondary", css_vars.get("--pico-secondary")), ("Muted", css_vars.get("--pico-muted-color"))]
    return templates.TemplateResponse("partials/_theme_preview.html", {"request": request, "theme_name": theme_name_for_display, "css_vars_str": css_vars_str, "main_colors": main_colors})

@app.post("/ui/apply-theme", tags=["UI Actions"])
async def apply_theme(request: Request, theme: str = Form(...)):
    try:
        from flock.webapp.app.config import set_current_theme_name
        set_current_theme_name(theme)
        headers = {"HX-Refresh": "true"}
        return HTMLResponse("", headers=headers)
    except Exception as e: return HTMLResponse(f"Failed to apply theme: {e}", status_code=500)

@app.get("/ui/htmx/settings/env-vars", response_class=HTMLResponse, tags=["UI HTMX Partials"])
async def htmx_settings_env_vars(request: Request):
    env_vars_list, show_secrets = _prepare_env_vars_for_template_web()
    return templates.TemplateResponse("partials/_settings_env_content.html", {"request": request, "env_vars": env_vars_list, "show_secrets": show_secrets})

@app.get("/ui/htmx/settings/theme", response_class=HTMLResponse, tags=["UI HTMX Partials"])
async def htmx_settings_theme(request: Request):
    theme_name = get_current_theme_name()
    themes_available = [p.stem for p in THEMES_DIR.glob("*.toml")] if THEMES_DIR and THEMES_DIR.exists() else []
    return templates.TemplateResponse("partials/_settings_theme_content.html", {"request": request, "themes": themes_available, "current_theme": theme_name})

@app.get("/ui/chat", response_class=HTMLResponse, tags=["UI Pages"])
async def page_chat(request: Request, ui_mode: str = Query("standalone")):
    context = get_base_context_web(request, ui_mode=ui_mode)
    context["initial_content_url"] = "/ui/htmx/chat-view"
    return templates.TemplateResponse("base.html", context)

@app.get("/ui/htmx/chat-view", response_class=HTMLResponse, tags=["UI HTMX Partials"])
async def htmx_get_chat_view(request: Request):
    # Render container partial; session handled in chat router
    return templates.TemplateResponse("partials/_chat_container.html", get_base_context_web(request))

if __name__ == "__main__":
    import uvicorn
    # Ensure the dependency injection system is initialized for standalone run
    temp_run_store = RunStore()
    # Create a default/dummy Flock instance for standalone UI testing
    # This allows the UI to function without being started by `Flock.start_api()`
    dev_flock_instance = Flock(name="DevStandaloneFlock", model="test/dummy", show_flock_banner=False)

    set_global_flock_services(dev_flock_instance, temp_run_store)
    app.state.flock_instance = dev_flock_instance
    app.state.run_store = temp_run_store
    app.state.flock_filename = "development_standalone.flock.yaml"

    logger.info("Running webapp.app.main directly for development with a dummy Flock instance.")
    uvicorn.run(app, host="127.0.0.1", port=8344, reload=True)

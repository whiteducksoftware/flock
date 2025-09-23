# src/flock/webapp/run.py
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import uvicorn

# Import core Flock components
if TYPE_CHECKING:
    from flock.core.api.custom_endpoint import FlockEndpoint
    from flock.core.flock import Flock

# --- Ensure src is in path for imports ---
current_file_path = Path(__file__).resolve()
flock_webapp_dir = current_file_path.parent
flock_dir = flock_webapp_dir.parent
src_dir = flock_dir.parent # Assuming `flock` is a package within `src`

if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

# --- Main Server Startup Function ---
def start_unified_server(
    flock_instance: "Flock",
    host: str,
    port: int,
    server_title: str,
    enable_ui_routes: bool,
    enable_chat_routes: bool = False,
    ui_theme: str | None = None,
    custom_endpoints: Sequence["FlockEndpoint"] | dict[tuple[str, list[str] | None], Callable[..., Any]] | None = None,
):
    """Starts the unified FastAPI server for Flock.
    - Initializes the web application (imported from webapp.app.main).
    - Sets the provided Flock instance and a RunStore for dependency injection
      and makes them available via app.state.
    - Configures the UI theme.
    - Stores custom API endpoints for registration during app lifespan startup.
    - Optionally registers chat routes.
    - Runs Uvicorn.
    """
    print(f"Attempting to start unified server for Flock '{flock_instance.name}' on http://{host}:{port}")
    print(f"UI Routes Enabled: {enable_ui_routes}, Theme: {ui_theme or 'Default'}")

    try:
        # Import necessary webapp components HERE, after path setup.
        from flock.core.api.run_store import RunStore
        from flock.core.logging.logging import get_logger  # For logging
        from flock.core.logging.live_capture import enable_live_log_capture
        from flock.webapp.app.config import (  # For logging resolved theme
            get_current_theme_name,
            set_current_theme_name,
        )
        from flock.webapp.app.dependencies import (
            add_pending_custom_endpoints,
            set_global_flock_services,
        )
        from flock.webapp.app.main import (
            app as fastapi_app,  # The single FastAPI app instance
        )

        logger = get_logger("webapp.run") # Use a logger
        enable_live_log_capture()
        logger.info("Live CLI log capture enabled for web footer display.")


        # 1. Set UI Theme globally for the webapp
        set_current_theme_name(ui_theme)
        logger.info(f"Unified server configured to use theme: {get_current_theme_name()}")

        # 2. Create RunStore & Set Global Services for Dependency Injection
        run_store_instance = RunStore()
        set_global_flock_services(flock_instance, run_store_instance)
        logger.info("Global Flock instance and RunStore set for dependency injection.")

        # 3. Make Flock instance and filename available on app.state
        fastapi_app.state.flock_instance = flock_instance
        source_file_attr = "_source_file_path" # Attribute where Flock might store its load path
        fastapi_app.state.flock_filename = getattr(flock_instance, source_file_attr, None) or \
                                           f"{flock_instance.name.replace(' ', '_').lower()}.flock.yaml"
        fastapi_app.state.run_store = run_store_instance
        fastapi_app.state.chat_enabled = enable_chat_routes

        logger.info(f"Flock '{flock_instance.name}' (from '{fastapi_app.state.flock_filename}') made available via app.state.")

        # 4. Store Custom Endpoints for registration by the lifespan manager in app.main
        processed_custom_endpoints = []
        if custom_endpoints:
            from flock.core.api.custom_endpoint import (
                FlockEndpoint,  # Ensure it's imported
            )
            if isinstance(custom_endpoints, dict):
                for (path_val, methods_val), cb_val in custom_endpoints.items():
                    processed_custom_endpoints.append(
                        FlockEndpoint(path=path_val, methods=list(methods_val) if methods_val else ["GET"], callback=cb_val)
                    )
            else: # Assumed Sequence[FlockEndpoint]
                processed_custom_endpoints.extend(list(custom_endpoints))

        if processed_custom_endpoints:
            add_pending_custom_endpoints(processed_custom_endpoints)
            logger.info(f"{len(processed_custom_endpoints)} custom endpoints stored for registration by app lifespan.")

        # 5. Update FastAPI app title (FastAPI app instance is now imported from main)
        fastapi_app.title = server_title

        # 5a. Optionally strip UI routes if UI is disabled
        if not enable_ui_routes:
            from fastapi.routing import APIRoute

            allowed_tags = {"Flock API Core", "Flock API Custom Endpoints", "Chat"}

            def _route_is_allowed(route: APIRoute) -> bool:  # type: ignore
                # Keep documentation and non-API utility routes (no tags)
                if not hasattr(route, "tags") or not route.tags:
                    return True
                # Keep if any tag is in the allowed list
                return any(tag in allowed_tags for tag in route.tags)  # type: ignore

            original_count = len(fastapi_app.router.routes)
            fastapi_app.router.routes = [r for r in fastapi_app.router.routes if _route_is_allowed(r)]

            # Clear cached OpenAPI schema so FastAPI regenerates it with the reduced route set
            if hasattr(fastapi_app, "openapi_schema"):
                fastapi_app.openapi_schema = None  # type: ignore

            logger.info(
                f"UI disabled: removed {original_count - len(fastapi_app.router.routes)} UI routes. Remaining routes: {len(fastapi_app.router.routes)}"
            )

        # 5b. Include Chat routes if requested
        if enable_chat_routes:
            try:
                from flock.webapp.app.chat import (
                    router as chat_router,  # type: ignore
                )
                fastapi_app.include_router(chat_router, tags=["Chat"])
                logger.info("Chat routes enabled and registered.")
            except Exception as e:
                logger.error(f"Failed to include chat routes: {e}")

        # 6. Run Uvicorn
        logger.info(f"Running Uvicorn with application: flock.webapp.app.main:app")
        uvicorn.run(
            "flock.webapp.app.main:app",
            host=host,
            port=port,
            reload=False, # Critical for programmatically set state like flock_instance
       #     root_path=os.getenv("FLOCK_ROOT_PATH", "")
        )

    except ImportError as e:
        # More specific error logging
        print(f"CRITICAL: Error importing components for unified server: {e}", file=sys.stderr)
        print(f"Module not found: {e.name}", file=sys.stderr)
        print("This usually means a problem with sys.path or missing dependencies.", file=sys.stderr)
        print(f"Current sys.path: {sys.path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"CRITICAL: Error starting unified server: {e}", file=sys.stderr)
        # Consider logging the full traceback for easier debugging
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


# --- Standalone Webapp Runner (for `flock --web` or direct execution `python -m flock.webapp.run`) ---
def main():
    """Runs the Flock web application in standalone mode.
    In this mode, no specific Flock is pre-loaded by the startup script;
    the user will load or create one via the UI.
    The FastAPI app (`webapp.app.main:app`) will initialize with DI services
    set to None for Flock, and a new RunStore.
    """
    print("Starting Flock web application in standalone mode...")

    from flock.core.api.run_store import RunStore
    from flock.webapp.app.config import (
        get_current_theme_name,  # To log the theme being used
    )
    from flock.webapp.app.dependencies import set_global_flock_services

    # No pre-loaded Flock instance; create a RunStore so API calls can still function
    standalone_run_store = RunStore()
    set_global_flock_services(None, standalone_run_store)

    print(
        f"Standalone mode: Initialized global services. Flock: None, RunStore: {type(standalone_run_store)}"
    )
    print(f"Standalone webapp using theme: {get_current_theme_name()}")

    host = "127.0.0.1"
    port = 8344
    try:
        import os

        host = os.environ.get("FLOCK_WEB_HOST", host)
        port = int(os.environ.get("FLOCK_WEB_PORT", port))
        webapp_reload = os.environ.get("FLOCK_WEB_RELOAD", "true").lower() == "true"
    except Exception:
        webapp_reload = True

    app_import_string = "flock.webapp.app.main:app"
    print(
        f"Running Uvicorn: app='{app_import_string}', host='{host}', port={port}, reload={webapp_reload}"
    )

    uvicorn.run(
        app_import_string,
        host=host,
        port=port,
        reload=webapp_reload,
       # root_path=os.getenv("FLOCK_ROOT_PATH", "")
    )


if __name__ == "__main__":
    main()

# src/flock/webapp/app/dependencies.py
from collections.abc import Sequence
from typing import TYPE_CHECKING, Optional

# Import FlockEndpoint for type hinting
from flock.core.api.custom_endpoint import FlockEndpoint

if TYPE_CHECKING:
    from flock.core.api.run_store import RunStore
    from flock.core.flock import Flock
    from flock.webapp.app.services.sharing_store import SharedLinkStoreInterface


# These will be set once when the FastAPI app starts, via set_global_flock_services
_flock_instance: Optional["Flock"] = None
_run_store_instance: Optional["RunStore"] = None
_shared_link_store_instance: Optional["SharedLinkStoreInterface"] = None

# Global-like variable (scoped to this module) to temporarily store custom endpoints
# before the app is fully configured and the lifespan event runs.
_pending_custom_endpoints: list[FlockEndpoint] = []


def add_pending_custom_endpoints(endpoints: Sequence[FlockEndpoint] | None):
    """Temporarily stores custom endpoints. Called by `start_unified_server`
    before the FastAPI app's lifespan event can process them.
    """
    global _pending_custom_endpoints
    if endpoints:
        # Ensure we are adding FlockEndpoint instances
        for ep in endpoints:
            if not isinstance(ep, FlockEndpoint):
                # If it's a dict, try to convert it, assuming it was the old format
                if isinstance(ep, dict) and "path" in ep and "callback" in ep:
                    try:
                        # Attempt to create FlockEndpoint from dict - assumes correct keys
                        # This is a basic conversion; more robust parsing might be needed
                        # if the dict structure is very different.
                        _pending_custom_endpoints.append(FlockEndpoint(**ep)) # type: ignore
                    except Exception as e:
                        print(f"Warning: Could not convert custom endpoint dict to FlockEndpoint: {ep}. Error: {e}")
                else:
                    print(f"Warning: Custom endpoint is not a FlockEndpoint instance and cannot be automatically converted: {type(ep)}")
            else:
                _pending_custom_endpoints.append(ep)
        print(f"Dependencies: Added {len(endpoints)} pending custom endpoints.")


def get_pending_custom_endpoints_and_clear() -> list[FlockEndpoint]:
    """Retrieves and clears pending custom endpoints.
    Called by the FastAPI app's lifespan event manager in `webapp/app/main.py`.
    """
    global _pending_custom_endpoints
    endpoints_to_add = _pending_custom_endpoints[:] # Create a copy
    _pending_custom_endpoints = [] # Clear the pending list
    if endpoints_to_add:
        print(f"Dependencies: Retrieved {len(endpoints_to_add)} pending custom endpoints for app registration.")
    return endpoints_to_add


def set_global_flock_services(flock: Optional["Flock"], run_store: "RunStore"):
    """Called once at application startup to set the global Flock and RunStore.
    This is typically invoked by the server startup script (e.g., in webapp/run.py).
    """
    global _flock_instance, _run_store_instance
    from flock.core.logging.logging import (
        get_logger,  # Local import to avoid circularity at module level
    )
    logger = get_logger("dependencies")

    if _flock_instance is not None or _run_store_instance is not None:
        logger.warning("Global Flock services are being re-initialized in dependencies.py.")

    _flock_instance = flock
    _run_store_instance = run_store
    logger.info(f"Global services set in dependencies: Flock='{flock.name if flock else 'None'}', RunStore type='{type(run_store)}'")


def set_global_shared_link_store(store: "SharedLinkStoreInterface"):
    """Called once at application startup to set the global SharedLinkStore."""
    global _shared_link_store_instance
    from flock.core.logging.logging import get_logger
    logger = get_logger("dependencies")

    if _shared_link_store_instance is not None:
        logger.warning("Global SharedLinkStore is being re-initialized in dependencies.py.")

    _shared_link_store_instance = store
    logger.info(f"Global SharedLinkStore set in dependencies: Store type='{type(store)}'")


def get_flock_instance() -> "Flock":
    """FastAPI dependency to get the globally available Flock instance."""
    if _flock_instance is None:
        # This can happen if accessed before `set_global_flock_services` or if it was cleared.
        # The application should handle this gracefully, e.g. by redirecting to a setup page.
        raise RuntimeError("Flock instance has not been initialized or is not currently available for DI.")
    return _flock_instance

def get_optional_flock_instance() -> Optional["Flock"]:
    """FastAPI dependency to optionally get the Flock instance. Returns None if not set."""
    return _flock_instance


def get_run_store() -> "RunStore":
    """FastAPI dependency to get the globally available RunStore instance."""
    if _run_store_instance is None:
        # Similar to Flock instance, should be initialized at app startup.
        raise RuntimeError("RunStore instance has not been initialized in the application.")
    return _run_store_instance


def get_shared_link_store() -> "SharedLinkStoreInterface":
    """FastAPI dependency to get the globally available SharedLinkStore instance."""
    if _shared_link_store_instance is None:
        raise RuntimeError("SharedLinkStore instance has not been initialized in the application.")
    return _shared_link_store_instance

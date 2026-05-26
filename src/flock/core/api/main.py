# src/flock/core/api/main.py
"""This module defines the FlockAPI class, which is now primarily responsible for
managing and adding user-defined custom API endpoints to a main FastAPI application.
"""

import inspect
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

from fastapi import (  # Ensure Request is aliased
    Body,
    Depends,
    FastAPI,
    Request as FastAPIRequest,
)

from flock.core.logging.logging import get_logger

from .custom_endpoint import FlockEndpoint

if TYPE_CHECKING:
    from flock.core.flock import Flock

logger = get_logger("core.api.custom_setup")


class FlockAPI:
    """A helper class to manage the addition of user-defined custom API endpoints
    to an existing FastAPI application, in the context of a Flock instance.
    """

    def __init__(
        self,
        flock_instance: "Flock",
        custom_endpoints: Sequence[FlockEndpoint] | dict[tuple[str, list[str] | None], Callable[..., Any]] | None = None,
    ):
        self.flock = flock_instance
        self.processed_custom_endpoints: list[FlockEndpoint] = []
        if custom_endpoints:
            if isinstance(custom_endpoints, dict):
                logger.warning("Received custom_endpoints as dict, converting. Prefer Sequence[FlockEndpoint].")
                for (path, methods), cb in custom_endpoints.items():
                    self.processed_custom_endpoints.append(
                        FlockEndpoint(path=path, methods=list(methods) if methods else ["GET"], callback=cb)
                    )
            elif isinstance(custom_endpoints, Sequence):
                for ep_item in custom_endpoints: # Renamed loop variable
                    if isinstance(ep_item, FlockEndpoint):
                        self.processed_custom_endpoints.append(ep_item)
                    else:
                        logger.warning(f"Skipping non-FlockEndpoint item in custom_endpoints sequence: {type(ep_item)}")
            else:
                logger.warning(f"Unsupported type for custom_endpoints: {type(custom_endpoints)}")
        logger.info(
            f"FlockAPI helper initialized for Flock: '{self.flock.name}'. "
            f"Prepared {len(self.processed_custom_endpoints)} custom endpoints."
        )

    def add_custom_routes_to_app(self, app: FastAPI):
        if not self.processed_custom_endpoints:
            logger.debug("No custom endpoints to add to the FastAPI app.")
            return

        logger.info(f"Adding {len(self.processed_custom_endpoints)} custom endpoints to the FastAPI app instance.")

        for current_ep_def in self.processed_custom_endpoints: # Use current_ep_def to avoid closure issues

            # This factory now takes current_ep_def to ensure it uses the correct endpoint's details
            def _create_handler_factory(
                # Capture the specific endpoint definition for this factory instance
                specific_ep: FlockEndpoint
            ):
                # This inner function prepares the payload and calls the user's callback
                async def _invoke_user_callback(
                    request_param: FastAPIRequest, # Parameter for FastAPI's Request object
                    body_param: Any,      # Will be populated by the _route_handler
                    query_param: Any      # Will be populated by the _route_handler
                ):
                    payload_to_user: dict[str, Any] = {"flock": self.flock} # self here refers to FlockAPI instance

                    if request_param: # Ensure request_param is not None
                        payload_to_user.update(request_param.path_params)
                        # query_param is already the parsed Pydantic model or None
                        if specific_ep.query_model and query_param is not None:
                            payload_to_user["query"] = query_param
                        # Fallback for raw query if callback expects 'query' but no query_model was set
                        elif 'query' in inspect.signature(specific_ep.callback).parameters and not specific_ep.query_model:
                             if request_param.query_params:
                                payload_to_user["query"] = dict(request_param.query_params)

                        # body_param is already the parsed Pydantic model or None
                        if specific_ep.request_model and body_param is not None:
                            payload_to_user["body"] = body_param
                        # Fallback for raw body if callback expects 'body' but no request_model was set
                        elif 'body' in inspect.signature(specific_ep.callback).parameters and \
                             not specific_ep.request_model and \
                             request_param.method in {"POST", "PUT", "PATCH"}:
                            try: payload_to_user["body"] = await request_param.json()
                            except Exception: payload_to_user["body"] = await request_param.body()

                        # If user callback explicitly asks for 'request'
                        if 'request' in inspect.signature(specific_ep.callback).parameters:
                            payload_to_user['request'] = request_param


                    user_callback_sig = inspect.signature(specific_ep.callback)
                    final_kwargs = {
                        k: v for k, v in payload_to_user.items() if k in user_callback_sig.parameters
                    }

                    if inspect.iscoroutinefunction(specific_ep.callback):
                        return await specific_ep.callback(**final_kwargs)
                    return specific_ep.callback(**final_kwargs)

                # --- Select the correct handler signature based on specific_ep's models ---
                if specific_ep.request_model and specific_ep.query_model:
                    async def _route_handler_body_query(
                        request: FastAPIRequest, # Correct alias for FastAPI Request
                        body: specific_ep.request_model = Body(...),  # type: ignore
                        query: specific_ep.query_model = Depends(specific_ep.query_model)  # type: ignore
                    ):
                        return await _invoke_user_callback(request, body, query)
                    return _route_handler_body_query
                elif specific_ep.request_model and not specific_ep.query_model:
                    async def _route_handler_body_only(
                        request: FastAPIRequest, # Correct alias
                        body: specific_ep.request_model = Body(...)  # type: ignore
                    ):
                        return await _invoke_user_callback(request, body, None)
                    return _route_handler_body_only
                elif not specific_ep.request_model and specific_ep.query_model:
                    async def _route_handler_query_only(
                        request: FastAPIRequest, # Correct alias
                        query: specific_ep.query_model = Depends(specific_ep.query_model)  # type: ignore
                    ):
                        return await _invoke_user_callback(request, None, query)
                    return _route_handler_query_only
                else: # Neither request_model nor query_model
                    async def _route_handler_request_only(
                        request: FastAPIRequest # Correct alias
                    ):
                        return await _invoke_user_callback(request, None, None)
                    return _route_handler_request_only

            # Create the handler for the current_ep_def
            selected_handler = _create_handler_factory(current_ep_def) # Pass current_ep_def
            selected_handler.__name__ = f"handler_for_{current_ep_def.path.replace('/', '_').lstrip('_')}_{current_ep_def.methods[0]}"


            app.add_api_route(
                current_ep_def.path,
                selected_handler,
                methods=current_ep_def.methods or ["GET"],
                name=current_ep_def.name or f"custom:{current_ep_def.path.replace('/', '_').lstrip('_')}",
                include_in_schema=current_ep_def.include_in_schema,
                response_model=current_ep_def.response_model,
                summary=current_ep_def.summary,
                description=current_ep_def.description,
                dependencies=current_ep_def.dependencies,
                tags=["Flock API Custom Endpoints"],
            )
            logger.debug(f"Added custom route to app: {current_ep_def.methods} {current_ep_def.path} (Handler: {selected_handler.__name__}, Summary: {current_ep_def.summary})")

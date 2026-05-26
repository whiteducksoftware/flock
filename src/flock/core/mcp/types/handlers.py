"""Handler functions."""

from collections.abc import Callable

from mcp import CreateMessageRequest
from mcp.client.session import ClientResponse
from mcp.shared.context import RequestContext
from mcp.shared.session import RequestResponder
from mcp.types import (
    INTERNAL_ERROR,
    CancelledNotification,
    ClientResult,
    ErrorData,
    ListRootsRequest,
    LoggingMessageNotification,
    LoggingMessageNotificationParams,
    ProgressNotification,
    ResourceListChangedNotification,
    ResourceUpdatedNotification,
    ServerNotification,
    ServerRequest,
    ToolListChangedNotification,
)

from flock.core.logging.logging import FlockLogger
from flock.core.mcp.mcp_client import Any


async def handle_incoming_exception(
    e: Exception,
    logger_to_use: FlockLogger,
    associated_client: Any,
) -> None:
    """Process an incoming exception Message."""
    server_name = await associated_client.config.name

    # For now, simply log it
    logger_to_use.error(
        f"Encountered Exception while communicating with server '{server_name}': {e}"
    )


async def handle_progress_notification(
    n: ProgressNotification,
    logger_to_use: FlockLogger,
    server_name: str,
) -> None:
    """Process an incoming progress Notification."""
    params = n.params
    progress = params.progress
    total = params.total or "Unknown"
    progress_token = params.progressToken
    metadata = params.meta or {}

    message = f"PROGRESS_NOTIFICATION: Server '{server_name}' reports Progress: {progress}/{total}. (Token: {progress_token}) (Meta Data: {metadata})"

    logger_to_use.info(message)


async def handle_cancellation_notification(
    n: CancelledNotification,
    logger_to_use: FlockLogger,
    server_name: str,
) -> None:
    """Process an incoming Cancellation Notification."""
    params = n.params
    request_id_to_cancel = params.requestId
    reason = params.reason or "no reason given"
    metadata = params.meta or {}

    message = f"CANCELLATION_REQUEST: Server '{server_name}' requests to cancel request with id: {request_id_to_cancel}. Reason: {reason}. (Metadata: {metadata})"

    logger_to_use.warning(message)


async def handle_resource_update_notification(
    n: ResourceUpdatedNotification,
    logger_to_use: FlockLogger,
    associated_client: Any,
) -> None:
    """Handle an incoming ResourceUpdatedNotification."""
    # This also means that the associated client needs to invalidate
    # its resource_contents_cache

    params = n.params
    metadata = params.meta or {}
    uri = params.uri

    message = f"RESOURCE_UPDATE: Server '{associated_client.config.name}' reports change on resoure at: {uri}. (Meta Data: {metadata})"

    logger_to_use.info(message)

    await associated_client.invalidate_resource_contents_cache_entry(key=uri)


async def handle_resource_list_changed_notification(
    n: ResourceListChangedNotification,
    logger_to_use: FlockLogger,
    associated_client: Any,
) -> None:
    """Handle an incoming ResourecListChangedNotification."""
    # This also means that the associated client needs to invalidate
    # its resource_contents_cache

    params = n.params or {}
    metadata = params.meta or {}

    message = f"TOOLS_LIST_CHANGED: Server '{associated_client.config.name}' reports a change in their tools list: {metadata}. Resetting Tools Cache for associated clients."

    logger_to_use.info(message)
    await associated_client.invalidate_resource_list_cache()


async def handle_tool_list_changed_notification(
    n: ToolListChangedNotification,
    logger_to_use: FlockLogger,
    associated_client: Any,
) -> None:
    """Handle an incoming ToolListChangedNotification."""
    params = n.params or {}
    metadata = params.meta or {}

    message = f"TOOLS_LIST_CHANGED: Server '{associated_client.config.name}' reports a change in their tools list: {metadata}. Resetting Tools Cache for associated clients."

    logger_to_use.info(message)
    await associated_client.invalidate_tool_cache()


_SERVER_NOTIFICATION_MAP: dict[type[ServerNotification], Callable] = {
    ResourceListChangedNotification: handle_resource_list_changed_notification,
    ResourceUpdatedNotification: handle_resource_update_notification,
    LoggingMessageNotification: lambda n, log, client: handle_logging_message(
        params=n.params,
        logger=log,
        server_name=client.config.name,
    ),
    ProgressNotification: handle_progress_notification,
    CancelledNotification: handle_cancellation_notification,
}


async def handle_incoming_server_notification(
    n: ServerNotification,
    logger: FlockLogger,
    client: Any,
) -> None:
    """Process an incoming server notification."""
    handler = _SERVER_NOTIFICATION_MAP.get(type(n.root))
    if handler:
        await handler(n.root, logger, client)


async def handle_logging_message(
    params: LoggingMessageNotificationParams,
    logger: FlockLogger,
    server_name: str,
) -> None:
    """Handle a logging request."""
    level = params.level
    method = logger.debug
    logger_name = params.logger if params.logger else "unknown_remote_logger"
    metadata = params.meta or {}

    str_level = "DEBUG"
    prefix = f"Message from Remote MCP Logger '{logger_name}' for server '{server_name}': "

    match level:
        case "info":
            method = logger.info
            str_level = "INFO: "
        case "notice":
            method = logger.info
            str_level = "NOTICE: "
        case "alert":
            method = logger.warning
            str_level = "WARNING: "
        case "critical":
            method = logger.error
            str_level = "CRITICAL: "
        case "error":
            method = logger.error
            str_level = "ERROR: "
        case "emergency":
            method = logger.error
            str_level = "EMERGENCY: "

    full_msg = f"{prefix}{str_level}{params.data} (Meta Data: {metadata})"
    method(full_msg)


async def handle_incoming_request(
    req: RequestResponder[ServerRequest, ClientResult],
    logger_to_use: FlockLogger,
    associated_client: Any,
) -> None:
    """Handle generic request."""
    ctx = RequestContext(
        request_id=req.request_id,
        meta=req.request_meta,
        session=req._session,
        lifespan_context=None,
    )

    try:
        match req.request.root:
            case CreateMessageRequest(params=req.request.root.params):
                with req:
                    # invoke user's sampling callback
                    # type: ignore
                    response = await associated_client.sampling_callback(
                        ctx, req.request.root.params
                    )
                    client_resp = ClientResponse.validate_python(response)
                    await req.respond(client_resp)
            case ListRootsRequest():
                with req:
                    # type: ignore
                    response = await associated_client.list_roots_callback(ctx)
                    client_resp = ClientResponse.validate_python(response)
                    await req.respond(client_resp)
            case _:
                # unrecognized -> no-op
                return
    except Exception as e:
        # 1) Log the error and stacktrace
        logger_to_use.error(
            f"Error in fallback handle_incoming_request (id={req.request_id}): {e}"
        )
        # 2) If the request wasn't already completed, send a JSON-RPC error back
        if not getattr(req, "_completed", False):
            with req:
                err = ErrorData(
                    code=INTERNAL_ERROR, message=f"Client-side error: {e}"
                )
                client_err = ClientResponse.validate_python(err)
                await req.respond(client_err)
    return

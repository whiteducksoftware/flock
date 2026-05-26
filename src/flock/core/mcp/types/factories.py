"""Factories for default MCP Callbacks."""

from typing import Any

from mcp.shared.context import RequestContext
from mcp.types import (
    CreateMessageRequestParams,
)

from flock.core.logging.logging import FlockLogger, get_logger
from flock.core.mcp.types.callbacks import (
    default_list_roots_callback,
    default_logging_callback,
    default_message_handler,
    default_sampling_callback,
)
from flock.core.mcp.types.types import (
    FlockListRootsMCPCallback,
    FlockLoggingMCPCallback,
    FlockLoggingMessageNotificationParams,
    FlockMessageHandlerMCPCallback,
    FlockSamplingMCPCallback,
    ServerNotification,
)

default_logging_callback_logger = get_logger("mcp.callback.logging")
default_sampling_callback_logger = get_logger("mcp.callback.sampling")
default_list_roots_callback_logger = get_logger("mcp.callback.roots")
default_message_handler_logger = get_logger("mcp.callback.message")


def default_flock_mcp_logging_callback_factory(
    associated_client: Any,
    logger: FlockLogger | None = None,
) -> FlockLoggingMCPCallback:
    """Creates a fallback for handling incoming logging requests."""
    logger_to_use = logger if logger else default_logging_callback_logger

    async def _method(
        params: FlockLoggingMessageNotificationParams,
    ) -> None:
        return await default_logging_callback(
            params=params,
            logger=logger_to_use,
            server_name=associated_client.config.name,
        )


def default_flock_mcp_sampling_callback_factory(
    associated_client: Any,
    logger: FlockLogger | None = None,
) -> FlockSamplingMCPCallback:
    """Creates a fallback for handling incoming sampling requests."""
    logger_to_use = logger if logger else default_sampling_callback_logger

    async def _method(
        ctx: RequestContext,
        params: CreateMessageRequestParams,
    ):
        logger_to_use.info(
            f"SAMPLING_REQUEST: server '{associated_client.config.name}' sent a sampling request: {params}"
        )
        await default_sampling_callback(
            ctx=ctx, params=params, logger=logger_to_use
        )

    return _method


def default_flock_mcp_message_handler_callback_factory(
    associated_client: Any,
    logger: FlockLogger | None = None,
) -> FlockMessageHandlerMCPCallback:
    """Creates a fallback for handling incoming messages.

    Note:
        Incoming Messages differ from incoming requests.
        Requests can do things like list roots, create messages through sampling etc.
        While Incoming Messages mainly consist of miscellanious information
        sent by the server.
    """
    logger_to_use = logger if logger else default_message_handler_logger

    async def _method(
        n: ServerNotification,
    ) -> None:
        await default_message_handler(
            req=n,
            logger=logger_to_use,
            associated_client=associated_client,
        )

    return _method


def default_flock_mcp_list_roots_callback_factory(
    associated_client: Any,
    logger: FlockLogger | None = None,
) -> FlockListRootsMCPCallback:
    """Creates a fallback for a list roots callback for a client."""
    logger_to_use = logger or default_list_roots_callback_logger

    async def _method(*args, **kwargs):
        return await default_list_roots_callback(
            associated_client=associated_client,
            logger=logger_to_use,
        )

    return _method

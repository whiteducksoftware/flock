"""Thin wrapper around the Dapr gRPC client.

Centralises client creation so that address override, retry policies,
and future migration to the async client happen in one place.
"""

from __future__ import annotations

from dapr.clients import DaprClient


def create_dapr_client(config) -> DaprClient:
    """Return a configured :class:`DaprClient`.

    The caller is responsible for closing the client, either
    via a context-manager (``with create_dapr_client() as c: ...``) or
    by calling ``c.close()`` explicitly.
    """
    return DaprClient(
        address=config.dapr_grpc_endpoint,
        headers_callback=config.headers_callback,
        interceptors=config.interceptors,
        http_timeout_seconds=config.http_timeout_seconds,
        max_grpc_message_length=config.max_grpc_message_length,
        retry_policy=config.retry_policy,
    )

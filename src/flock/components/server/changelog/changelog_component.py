"""ChangelogStreamComponent — SSE, WebSocket, and cursor-based changelog delivery.

Registers three endpoints:
- GET  /api/v1/changelog/stream  — SSE push (EventSourceResponse)
- WS   /ws/changelog             — WebSocket push
- GET  /api/v1/changelog/events  — cursor-based pull
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any

from fastapi import Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import Field
from sse_starlette.sse import EventSourceResponse

from flock.components.server.base import ServerComponent, ServerComponentConfig
from flock.components.server.changelog.stream_dispatcher import (
    StreamDispatcher,
    Subscription,
)
from flock.logging.logging import get_logger
from flock.models.changelog import ChangelogEvent, ChangelogEventType, ChangelogFilter


if TYPE_CHECKING:
    from flock.core import Flock

logger = get_logger(__name__)

# Keepalive interval for SSE connections (seconds)
_SSE_KEEPALIVE_SECONDS = 15


class ChangelogStreamComponentConfig(ServerComponentConfig):
    """Configuration for ChangelogStreamComponent."""

    prefix: str = Field(
        default="",
        description="Optional prefix for changelog endpoints.",
    )
    tags: list[str] = Field(
        default=["Changelog Stream"],
        description="OpenAPI tags for changelog endpoints.",
    )
    sse_queue_maxsize: int = Field(
        default=256,
        description="Max buffered events per SSE client before drop-oldest.",
    )
    ws_queue_maxsize: int = Field(
        default=256,
        description="Max buffered events per WebSocket client before drop-oldest.",
    )


class ChangelogStreamComponent(ServerComponent):
    """ServerComponent providing real-time changelog event delivery.

    Endpoints:
        - GET /api/v1/changelog/stream — SSE push stream
        - WS  /ws/changelog            — WebSocket push stream
        - GET /api/v1/changelog/events — Cursor-based pull API
    """

    name: str = Field(default="changelog_stream", description="Component name.")
    priority: int = Field(
        default=20,
        description="Registration priority (~20, after core components).",
    )
    config: ChangelogStreamComponentConfig = Field(
        default_factory=ChangelogStreamComponentConfig,
        description="Configuration for changelog stream component.",
    )

    _dispatcher: StreamDispatcher | None = None
    _token_store: Any | None = None  # Optional TokenStore for WebSocket auth

    def __init__(self, token_store: Any | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._token_store = token_store

    @property
    def dispatcher(self) -> StreamDispatcher:
        """Access the StreamDispatcher (created on startup)."""
        if self._dispatcher is None:
            raise RuntimeError(
                "ChangelogStreamComponent not started — dispatcher not available."
            )
        return self._dispatcher

    def configure(self, app: Any, orchestrator: Any) -> None:
        """No-op — dispatcher is created in on_startup_async."""

    def register_routes(self, app: Any, orchestrator: Any) -> None:
        """Register SSE, WebSocket, and cursor endpoints."""
        prefix = self.config.prefix if self.config.prefix else ""
        sse_path = self._join_path(prefix, "/api/v1/changelog/stream")
        ws_path = self._join_path(prefix, "/ws/changelog")
        cursor_path = self._join_path(prefix, "/api/v1/changelog/events")

        component = self  # capture for closures

        @app.get(sse_path, tags=self.config.tags)
        async def changelog_sse_stream(request: Request) -> EventSourceResponse:
            """SSE endpoint for real-time changelog event streaming.

            Supports reconnection via Last-Event-ID header.
            Sends keepalive comments every 15 seconds.
            """
            # Parse Last-Event-ID for reconnection
            last_event_id = request.headers.get("Last-Event-ID")
            after_seq = 0
            if last_event_id:
                try:
                    after_seq = int(last_event_id)
                except (ValueError, TypeError):
                    pass

            return EventSourceResponse(
                component._sse_event_generator(request, orchestrator, after_seq),
                media_type="text/event-stream",
            )

        @app.websocket(ws_path)
        async def changelog_websocket(websocket: WebSocket) -> None:
            """WebSocket endpoint for real-time changelog event streaming.

            Client sends initial filter config as JSON, then receives events.
            Token auth via query parameter (?token=...) when token_store is set.
            """
            # Auth check before accept — token via query parameter
            if component._token_store is not None:
                raw_token = websocket.query_params.get("token")
                if not raw_token:
                    await websocket.close(code=1008, reason="Token required")
                    return
                record = await component._token_store.verify(raw_token)
                if record is None:
                    await websocket.close(code=1008, reason="Invalid or expired token")
                    return

            await websocket.accept()

            # Wait for initial filter message
            filters = ChangelogFilter()
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
                filter_data = json.loads(raw)
                filters = ChangelogFilter(**filter_data)
            except asyncio.TimeoutError:
                # No filter sent within timeout — use empty filter (match all)
                pass
            except (json.JSONDecodeError, TypeError, ValueError) as exc:
                # Malformed filter — send error and close
                await websocket.send_json({
                    "detail": f"Invalid filter JSON: {exc!s}",
                })
                await websocket.close(code=1003, reason="Invalid filter JSON")
                return
            except WebSocketDisconnect:
                return

            # Subscribe with filter
            sub = await component.dispatcher.subscribe(
                filters=filters,
                queue_maxsize=component.config.ws_queue_maxsize,
            )

            try:
                await component._ws_push_loop(websocket, sub)
            finally:
                await component.dispatcher.unsubscribe(sub.id)

        @app.get(cursor_path, tags=self.config.tags)
        async def changelog_events(
            after: int = Query(default=0, description="Return events after this sequence number."),
            limit: int = Query(default=100, ge=1, le=1000, description="Max events to return."),
            type: str | None = Query(default=None, description="Filter by event type."),
            produced_by: str | None = Query(default=None, description="Filter by producer agent."),
        ) -> JSONResponse:
            """Cursor-based pull API for changelog events.

            Returns events after the specified sequence number with bounds metadata.
            """
            # Validate 'after' parameter
            if after < 0:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Parameter 'after' must be a non-negative integer."},
                )

            # Build filter
            filters = ChangelogFilter()
            if type:
                try:
                    event_type = ChangelogEventType(type)
                    filters.event_types = {event_type}
                except ValueError:
                    return JSONResponse(
                        status_code=400,
                        content={"detail": f"Invalid event type: {type}"},
                    )
            if produced_by:
                filters.produced_by = {produced_by}

            store = orchestrator.store
            result = await store.query_changelog(
                after_seq=after,
                limit=limit,
                filters=filters if (type or produced_by) else None,
            )

            return JSONResponse(
                status_code=200,
                content={
                    "events": [ev.model_dump(mode="json") for ev in result.events],
                    "oldest_available_seq": result.oldest_available_seq,
                    "latest_seq": result.latest_seq,
                },
            )

    async def _sse_event_generator(
        self,
        request: Request,
        orchestrator: Any,
        after_seq: int,
    ):
        """Async generator yielding SSE events for a single client.

        1. If after_seq > 0, replays missed events from the store.
        2. Subscribes to live events via dispatcher.
        3. Yields keepalive comments every 15s when idle.
        4. Stops when client disconnects.
        """
        # Replay missed events if reconnecting
        if after_seq > 0:
            store = orchestrator.store
            result = await store.query_changelog(after_seq=after_seq, limit=1000)

            # Notify client if requested sequence is behind retention window
            if result.oldest_available_seq > after_seq:
                yield {
                    "event": "gap",
                    "data": json.dumps({
                        "message": "Events pruned by retention policy",
                        "requested_after": after_seq,
                        "oldest_available": result.oldest_available_seq,
                    }),
                    "id": str(result.oldest_available_seq),
                }

            for ev in result.events:
                if await request.is_disconnected():
                    return
                yield {
                    "event": ev.event_type.value,
                    "data": ev.model_dump_json(),
                    "id": str(ev.seq),
                }

        # Subscribe to live stream
        sub = await self.dispatcher.subscribe(
            queue_maxsize=self.config.sse_queue_maxsize,
        )

        try:
            while True:
                if await request.is_disconnected():
                    return

                try:
                    # Wait for next event with timeout for keepalive
                    serialized = await asyncio.wait_for(
                        sub.queue.get(), timeout=_SSE_KEEPALIVE_SECONDS
                    )
                    # Parse to get seq and event_type for SSE fields
                    try:
                        event_data = json.loads(serialized)
                    except (json.JSONDecodeError, ValueError):
                        logger.warning("Malformed changelog event JSON, skipping")
                        continue
                    yield {
                        "event": event_data.get("event_type", "changelog"),
                        "data": serialized,
                        "id": str(event_data.get("seq", "0")),
                    }
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield {"comment": "keepalive"}
        finally:
            if self._dispatcher is not None:
                await self._dispatcher.unsubscribe(sub.id)

    async def _ws_push_loop(self, websocket: WebSocket, sub: Subscription) -> None:
        """Push events from subscription queue to WebSocket client."""
        try:
            while True:
                try:
                    serialized = await asyncio.wait_for(
                        sub.queue.get(), timeout=_SSE_KEEPALIVE_SECONDS
                    )
                    await websocket.send_text(serialized)
                except asyncio.TimeoutError:
                    # Send ping/keepalive
                    await websocket.send_json({"type": "keepalive"})
        except WebSocketDisconnect:
            logger.debug(f"WebSocket client disconnected (sub={sub.id})")
        except Exception as exc:
            logger.debug(f"WebSocket push error (sub={sub.id}): {exc!s}")

    async def on_startup_async(self, orchestrator: Any) -> None:
        """Create the StreamDispatcher and wire into ArtifactManager + ExternalAgentScheduler."""
        self._dispatcher = StreamDispatcher()
        # Wire dispatcher into artifact_manager for push delivery
        if hasattr(orchestrator, "artifact_manager"):
            orchestrator.artifact_manager._stream_dispatcher = self._dispatcher
        # Wire dispatcher into ExternalAgentScheduler if registered
        for comp in getattr(orchestrator, "_components", []):
            if hasattr(comp, "_stream_dispatcher") and hasattr(comp, "_adapters"):
                comp._stream_dispatcher = self._dispatcher
                logger.debug("Wired StreamDispatcher into %s", comp.name)
        logger.info("ChangelogStreamComponent started — dispatcher ready")

    async def on_shutdown_async(self, orchestrator: Any) -> None:
        """Shutdown the StreamDispatcher."""
        if self._dispatcher is not None:
            await self._dispatcher.shutdown()
            self._dispatcher = None
        logger.info("ChangelogStreamComponent shutdown complete")

    def get_dependencies(self) -> list[type[ServerComponent]]:
        """No dependencies on other components."""
        return []


__all__ = [
    "ChangelogStreamComponent",
    "ChangelogStreamComponentConfig",
]

"""Host a FlockApplication as a Microsoft Foundry hosted agent.

The adapter delegates HTTP, SSE, storage, background mode, polling and the
``/cancel`` endpoint to the official ``azure-ai-agentserver-responses`` host
and maps each Responses request onto one isolated Flock workflow.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from typing import TYPE_CHECKING, Any, Literal

from azure.ai.agentserver.core import get_request_context
from azure.ai.agentserver.responses import (
    ResponseEventStream,
    ResponsesAgentServerHost,
    ResponsesServerOptions,
)
from pydantic import BaseModel, ValidationError

from flock.application import (
    ApplicationNotRunning,
    CapacityExceeded,
    CountingAdmission,
    FlockApplication,
    WorkflowContext,
    WorkflowRejected,
    WorkflowStatus,
    WorkflowStream,
)
from flock.integrations.foundry.identity import IdentityPolicy, IdentityRequiredError
from flock.integrations.foundry.turns import (
    TextTurn,
    UnsupportedRequestError,
    history_messages,
    input_text,
    validate_request_options,
)
from flock.logging.logging import get_logger


if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send


logger = get_logger(__name__)

HistoryMode = Literal["stateless", "conversation"]
Observability = Literal["sdk", "none"]

# Keys of WorkflowContext.attributes set by the adapter.
ATTR_CALL_ID = "foundry.call_id"
ATTR_SESSION_ID = "foundry.session_id"
ATTR_CONVERSATION_ID = "foundry.conversation_id"
FOUNDRY_CALL_ID_HEADER = "x-agent-foundry-call-id"


def json_text(value: BaseModel) -> str:
    """Default output mapper: the output model as JSON text."""
    return value.model_dump_json()


def foundry_headers(context: WorkflowContext) -> dict[str, str]:
    """Headers to forward on outbound Foundry service calls made by a workflow.

    Use in the factory, e.g. ``DSPyEngine(lm_kwargs={"extra_headers":
    foundry_headers(context)})`` when calling models through the Foundry
    project endpoint. The call id is not an authentication or tenant key.
    """
    call_id = context.attributes.get(ATTR_CALL_ID)
    return {FOUNDRY_CALL_ID_HEADER: call_id} if call_id else {}


class _ReadinessGate:
    """ASGI middleware: ``GET /readiness`` reflects the application state.

    The SDK's readiness route only proves the port is open. This gate reports
    503 until the Flock application validated its contract and again once it
    drains for shutdown.
    """

    def __init__(self, app: ASGIApp, adapter: FoundryResponsesAdapter) -> None:
        self._app = app
        self._adapter = adapter

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] == "http"
            and scope.get("method") == "GET"
            and scope.get("path", "").rstrip("/") == "/readiness"
        ):
            ready = await self._adapter._ensure_ready()
            if not ready:
                body = json.dumps({"status": "unavailable"}).encode()
                await send({
                    "type": "http.response.start",
                    "status": 503,
                    "headers": [(b"content-type", b"application/json")],
                })
                await send({"type": "http.response.body", "body": body})
                return
        await self._app(scope, receive, send)


class FoundryResponsesAdapter:
    """Expose a :class:`~flock.application.FlockApplication` via Foundry Responses.

    Args:
        application: The application to host.
        input_mapper: Builds the application's typed input from a
            :class:`~flock.integrations.foundry.TextTurn` (current text plus, in conversation
            mode, prior messages with roles).
        output_mapper: Renders one public output as message text (default:
            JSON text of the model).
        history_mode: ``"conversation"`` loads platform-managed history for
            each turn; ``"stateless"`` treats every request independently.
        identity: How the trusted principal is resolved (see
            :class:`~flock.integrations.foundry.IdentityPolicy`).
        max_history: History messages loaded per turn.
        timeout: Workflow deadline in seconds (``None``: application default).
        drain_timeout: On server shutdown, how long a running workflow may
            finish before it is cancelled. Keep it below the SDK's shutdown grace.
        observability: ``"sdk"`` lets the Foundry host configure OpenTelemetry
            and logging; ``"none"`` leaves both to you.
        options: Custom ``ResponsesServerOptions`` (``default_fetch_history_count``
            is set from ``max_history`` when omitted).
        **host_kwargs: Passed to ``ResponsesAgentServerHost`` (e.g. ``store``).
    """

    def __init__(
        self,
        application: FlockApplication,
        *,
        input_mapper: Callable[[TextTurn], BaseModel | dict[str, Any]],
        output_mapper: Callable[[BaseModel], str] = json_text,
        history_mode: HistoryMode = "stateless",
        identity: IdentityPolicy | None = None,
        max_history: int = 50,
        timeout: float | None = None,
        drain_timeout: float = 5.0,
        observability: Observability = "sdk",
        options: ResponsesServerOptions | None = None,
        **host_kwargs: Any,
    ) -> None:
        if history_mode not in ("stateless", "conversation"):
            raise ValueError("history_mode must be 'stateless' or 'conversation'")
        self.application = application
        self._input_mapper = input_mapper
        self._output_mapper = output_mapper
        self._history_mode = history_mode
        self._identity = identity or IdentityPolicy()
        self._timeout = timeout
        self._drain_timeout = drain_timeout
        self._last_start_error: str | None = None
        _warn_if_unbounded(application)

        if observability == "sdk":
            _warn_if_flock_owns_tracing()
        else:
            host_kwargs.setdefault("configure_observability", None)
        self._host = ResponsesAgentServerHost(
            options=options
            or ResponsesServerOptions(default_fetch_history_count=max_history),
            **host_kwargs,
        )
        self._host.response_handler(self._handle)
        self._host.add_middleware(_ReadinessGate, adapter=self)

    @property
    def app(self) -> ResponsesAgentServerHost:
        """The ASGI application (the SDK host). Serve it as the root app so its
        lifespan - task manager and graceful shutdown - runs."""
        return self._host

    def run(
        self,
        host: str = "0.0.0.0",  # noqa: S104  # nosec B104 - container entrypoint
        port: int | None = None,
        *,
        disable_lm_history: bool = True,
    ) -> None:
        """Serve on ``port`` (default ``$PORT`` or 8088) via the SDK host.

        Args:
            host: Bind address.
            port: Port; the SDK falls back to ``PORT`` and then 8088.
            disable_lm_history: Stop DSPy from keeping every prompt and response
                of every tenant in process memory (recommended when hosted).
        """
        if disable_lm_history:
            import dspy

            dspy.configure(disable_history=True)
        self._host.run(host=host, port=port)

    # -- request handling --------------------------------------------------

    async def _ensure_ready(self) -> bool:
        # Retried on every probe: a transient start failure (e.g. a credential
        # that is not reachable yet) must not keep the replica unready forever.
        try:
            await self.application.start()
        except ApplicationNotRunning:
            return False
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            # Probes repeat every few seconds: log each distinct failure once.
            if error != self._last_start_error:
                logger.warning(f"Flock application is not ready: {error}")
                self._last_start_error = error
            return False
        self._last_start_error = None
        return self.application.accepting

    async def _handle(  # noqa: PLR0911 - one exit per protocol outcome
        self,
        request: Any,
        context: Any,
        cancellation_signal: asyncio.Event,
    ) -> AsyncIterator[Any]:
        stream = ResponseEventStream(response_id=context.response_id, request=request)
        yield stream.emit_created()
        yield stream.emit_in_progress()

        try:
            workflow_context, value = await self._prepare(request, context)
        except UnsupportedRequestError as exc:
            yield stream.emit_failed(code="invalid_prompt", message=str(exc))
            return
        except IdentityRequiredError as exc:
            yield stream.emit_failed(code="invalid_prompt", message=str(exc))
            return
        except ValidationError:
            yield stream.emit_failed(
                code="invalid_prompt",
                message="The input could not be mapped to the application's input type.",
            )
            return

        handle = self.application.stream(
            value, context=workflow_context, timeout=self._timeout
        )
        try:
            workflow = await handle.__aenter__()
        except CapacityExceeded:
            yield stream.emit_failed(
                code="rate_limit_exceeded", message="The agent is busy; retry later."
            )
            return
        except ApplicationNotRunning:
            yield stream.emit_failed(
                code="server_error", message="The agent is not accepting requests."
            )
            return
        except WorkflowRejected as exc:
            yield stream.emit_failed(code="invalid_prompt", message=str(exc))
            return

        watcher = asyncio.create_task(
            self._watch_signals(context, cancellation_signal, workflow),
            name=f"flock-foundry-signals-{context.response_id}",
        )
        try:
            async for event in workflow:
                for wire_event in stream.output_item_message(
                    self._output_mapper(event.value)
                ):
                    yield wire_event
            result = await workflow.result()
        finally:
            watcher.cancel()
            await handle.__aexit__(None, None, None)

        if context.shutdown.is_set() and not result.ok:
            # Interrupted by server shutdown: never report success. Without a
            # terminal event the host records the response as failed.
            return
        if result.status is WorkflowStatus.SUCCEEDED:
            yield stream.emit_completed()
        elif result.status is WorkflowStatus.CANCELLED:
            # Returning without a terminal event after the cancellation signal
            # lets the host record status "cancelled".
            return
        elif result.status is WorkflowStatus.TIMED_OUT:
            yield stream.emit_failed(
                code="server_error", message="The workflow did not finish in time."
            )
        else:
            failure = result.failure
            code = failure.code.value if failure else "server_error"
            message = failure.message if failure else "The workflow failed."
            yield stream.emit_failed(code="server_error", message=f"{code}: {message}")

    async def _prepare(
        self, request: Any, context: Any
    ) -> tuple[WorkflowContext, BaseModel | dict[str, Any]]:
        validate_request_options(request)
        text = input_text(await context.get_input_items())
        history = ()
        if self._history_mode == "conversation":
            history = history_messages(await context.get_history())
        principal = self._identity.principal_for(context)

        platform = getattr(context, "platform_context", None)
        request_context = get_request_context()
        attributes: dict[str, str] = {}
        call_id = getattr(platform, "call_id", None) or request_context.call_id
        if call_id:
            attributes[ATTR_CALL_ID] = call_id
        if request_context.session_id:
            attributes[ATTR_SESSION_ID] = request_context.session_id
        if context.conversation_id:
            attributes[ATTR_CONVERSATION_ID] = context.conversation_id

        workflow_context = WorkflowContext(
            workflow_id=context.response_id,
            principal_id=principal,
            session_id=context.conversation_id,
            attributes=attributes,
        )
        value = self._input_mapper(TextTurn(text=text, history=history))
        return workflow_context, value

    async def _watch_signals(
        self,
        context: Any,
        cancellation_signal: asyncio.Event,
        workflow: WorkflowStream,
    ) -> None:
        shutdown = asyncio.ensure_future(context.shutdown.wait())
        cancelled = asyncio.ensure_future(cancellation_signal.wait())
        try:
            await asyncio.wait(
                {shutdown, cancelled}, return_when=asyncio.FIRST_COMPLETED
            )
        finally:
            shutdown.cancel()
            cancelled.cancel()
        # The SDK can set both signals on shutdown: check shutdown first.
        if context.shutdown.is_set():
            self.application.begin_drain()
            try:
                await asyncio.wait_for(workflow.result(), self._drain_timeout)
            except TimeoutError:
                workflow.cancel()
            return
        workflow.cancel()


def _warn_if_unbounded(application: FlockApplication) -> None:
    admission = application.admission
    if isinstance(admission, CountingAdmission) and admission.limit is None:
        logger.warning(
            "The hosted FlockApplication admits unlimited concurrent workflows. Set "
            "FlockApplication(max_active_workflows=...) so a burst of requests is "
            "answered with rate_limit_exceeded instead of exhausting the container."
        )


def _warn_if_flock_owns_tracing() -> None:
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
    except ImportError:  # pragma: no cover - OpenTelemetry is a flock dependency
        return
    if isinstance(trace.get_tracer_provider(), TracerProvider):
        logger.warning(
            "An OpenTelemetry TracerProvider is already installed (Flock installs one "
            "at import unless FLOCK_DISABLE_TELEMETRY_AUTOSETUP=1 or "
            "FLOCK_AUTO_TRACE=false is set). The Foundry host's observability setup "
            "cannot replace it, so Azure Monitor export may not include Flock spans."
        )


__all__ = [
    "ATTR_CALL_ID",
    "ATTR_CONVERSATION_ID",
    "ATTR_SESSION_ID",
    "FOUNDRY_CALL_ID_HEADER",
    "FoundryResponsesAdapter",
    "foundry_headers",
    "json_text",
]

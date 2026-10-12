"""The engine of a sink: delivers what it consumes, publishes a receipt.

A sink sends each execution's artifacts in one HTTP request (a batch as a
list), retries what is worth retrying, and publishes ``Delivered`` or
``DeliveryFailed``, and with a response type the target's answer. Deliveries
of one correlation go out one after another in the order they were
scheduled; different correlations go out concurrently.
"""

from __future__ import annotations

import asyncio
import json
import random
import time
import uuid
from collections.abc import Callable
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, ValidationError

from flock.components.agent import EngineComponent
from flock.components.orchestrator import OrchestratorComponent
from flock.core.artifacts import Artifact
from flock.core.visibility import PrivateVisibility, Visibility
from flock.decisions.providers import MAX_RETRY_WAIT, retry_wait
from flock.logging.logging import get_logger
from flock.registry import type_registry
from flock.sinks.endpoint import MissingSecretError, Target
from flock.sinks.models import Delivered, DeliveryFailed
from flock.utils.runtime import Context, EvalInputs, EvalResult


logger = get_logger(__name__)

# Worth another attempt: request timeout, rate limited, server errors
RETRY_STATUSES = frozenset({408, 429})
ERROR_BODY_CHARS = 500


async def _sleep(seconds: float) -> None:
    """The wait between attempts (tests replace it)."""
    await asyncio.sleep(seconds)


class _Turns:
    """Per correlation, the scheduled deliveries in order: each waits for the
    ones scheduled before it."""

    def __init__(self) -> None:
        self._queues: dict[str, list[tuple[asyncio.Task, asyncio.Event]]] = {}

    def reserve(self, key: str, task: asyncio.Task) -> None:
        queue = self._queues.setdefault(key, [])
        turn = asyncio.Event()
        if not queue:
            turn.set()
        queue.append((task, turn))
        # A run that ends before its delivery (cancelled, failed) frees its turn
        task.add_done_callback(lambda _: self.release(key, task))

    async def wait(self, key: str | None, task: asyncio.Task | None) -> None:
        for queued, turn in self._queues.get(key or "", []):
            if queued is task:
                await turn.wait()
                return

    def release(self, key: str | None, task: asyncio.Task | None) -> None:
        queue = self._queues.get(key or "")
        if not queue:
            return
        for index, (queued, _) in enumerate(queue):
            if queued is task:
                del queue[index]
                break
        else:
            return
        if queue:
            queue[0][1].set()
        else:
            del self._queues[key or ""]


class SinkEngine(EngineComponent):
    """Delivers the consumed artifacts to one target."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    method: str = Field(description="HTTP method: POST, PUT or PATCH")
    target: Any = Field(description="Where the sink delivers (a Target)")
    body: Callable[[Artifact], Any] | None = Field(
        default=None,
        description="Maps an artifact to the target's JSON; by default its envelope",
    )
    response: type[BaseModel] | None = Field(
        default=None, description="Type the target's answer is published as"
    )
    enable_context: bool = False
    _turns: _Turns = PrivateAttr(default_factory=_Turns)

    @property
    def kind(self) -> str:  # type: ignore[override]
        """The label on the sink's card, e.g. ``↗ POST /billing``."""
        return f"↗ {self.method} {self.target.label}"

    def _reserve(self, artifacts: list[Artifact], task: asyncio.Task) -> None:
        """Queue a scheduled delivery behind the earlier ones of its correlation
        (private: auto-tracing leaves it out)."""
        key = _correlation(artifacts[0].correlation_id) if artifacts else None
        if key is not None:
            self._turns.reserve(key, task)

    async def evaluate(
        self, agent: Any, ctx: Context, inputs: EvalInputs, output_group: Any
    ) -> EvalResult:
        artifacts = list(inputs.artifacts)
        key = _correlation(ctx.correlation_id)
        task = asyncio.current_task()
        await self._turns.wait(key, task)
        try:
            outputs = await self._deliver(agent.name, artifacts)
        finally:
            self._turns.release(key, task)
        visibility = _common_visibility(artifacts, agent.name)
        return EvalResult(
            artifacts=[
                Artifact(
                    type=type_registry.name_for(type(output)),
                    payload=output.model_dump(mode="json"),
                    produced_by=agent.name,
                    visibility=visibility,
                )
                for output in outputs
            ],
            state=dict(inputs.state),
        )

    async def _deliver(self, sink: str, artifacts: list[Artifact]) -> list[BaseModel]:
        target: Target = self.target
        endpoint = target.endpoint
        ids = [str(artifact.id) for artifact in artifacts]
        receipt = {
            "sink": sink,
            "method": self.method,
            "target": target.declared,
            "artifact_ids": ids,
        }
        bodies = [self._body(artifact) for artifact in artifacts]
        content = json.dumps(
            bodies if len(artifacts) != 1 else bodies[0], default=str
        ).encode()
        try:
            headers = self._headers(artifacts, content)
        except MissingSecretError as exc:
            return [DeliveryFailed(**receipt, status=None, attempts=0, error=str(exc))]

        started = time.monotonic()
        status: int | None = None
        error = ""
        for attempt in range(endpoint.retries + 1):
            if endpoint.budget is not None:
                await endpoint.budget.acquire()
            try:
                answer = await endpoint.http().request(
                    self.method, target.url, content=content, headers=headers
                )
            except httpx.TransportError as exc:
                status, error = None, f"{type(exc).__name__}: {exc}"
                if attempt < endpoint.retries:
                    await _sleep(_backoff(attempt))
                    continue
                break
            status = answer.status_code
            if answer.is_success:
                latency_ms = (time.monotonic() - started) * 1000
                return self._delivered(receipt, answer, attempt + 1, latency_ms)
            error = f"HTTP {status}: {answer.text[:ERROR_BODY_CHARS]}".rstrip(": ")
            if _retryable(status) and attempt < endpoint.retries:
                await _sleep(retry_wait(answer, attempt))
                continue
            break
        logger.warning(
            f"Sink '{sink}' could not deliver to {target.declared} after "
            f"{attempt + 1} attempt(s): {error}"
        )
        return [
            DeliveryFailed(**receipt, status=status, attempts=attempt + 1, error=error)
        ]

    def _delivered(
        self, receipt: dict, answer: httpx.Response, attempts: int, latency_ms: float
    ) -> list[BaseModel]:
        outputs: list[BaseModel] = []
        response_error = None
        if self.response is not None:
            try:
                outputs.append(self.response.model_validate(answer.json()))
            except (ValueError, ValidationError) as exc:
                response_error = (
                    f"The answer is not a {self.response.__name__}: "
                    f"{str(exc)[:ERROR_BODY_CHARS]}"
                )
        delivered = Delivered(
            **receipt,
            status=answer.status_code,
            attempts=attempts,
            latency_ms=round(latency_ms, 1),
            response_error=response_error,
        )
        return [delivered, *outputs]

    def _body(self, artifact: Artifact) -> Any:
        if self.body is not None:
            return self.body(artifact)
        return {
            "id": str(artifact.id),
            "type": artifact.type,
            "payload": artifact.payload,
            "produced_by": artifact.produced_by,
            "correlation_id": _correlation(artifact.correlation_id),
            "created_at": artifact.created_at.isoformat(),
        }

    def _headers(self, artifacts: list[Artifact], content: bytes) -> dict[str, str]:
        endpoint = self.target.endpoint
        ids = [str(artifact.id) for artifact in artifacts]
        # The target can drop a retried request it has already processed
        key = (
            ids[0]
            if len(ids) == 1
            else str(uuid.uuid5(uuid.NAMESPACE_URL, ",".join(ids)))
        )
        headers = {
            **endpoint.headers,
            "Content-Type": "application/json",
            "Idempotency-Key": key,
        }
        correlation = _correlation(artifacts[0].correlation_id) if artifacts else None
        if correlation is not None:
            headers["X-Flock-Correlation-Id"] = correlation
        if endpoint.auth is not None:
            headers.update(endpoint.auth.headers())
        if endpoint.sign is not None:
            headers.update(endpoint.sign.headers(content))
        return headers


class SinkOrdering(OrchestratorComponent):
    """Hands every scheduled sink run its turn within its correlation.

    Turns are taken when a run is scheduled, in the order the scheduler
    schedules them, before anything a run awaits could reorder them.
    """

    name: str | None = "sink_ordering"
    priority: int = -1000  # before every other component's hook
    # Housekeeping, traced at FLOCK_TRACE_LEVEL=all only (#601)
    __trace_level__ = "all"

    async def on_agent_scheduled(
        self,
        orchestrator: Any,
        agent: Any,
        artifacts: list[Artifact],
        task: asyncio.Task,
    ) -> None:
        for engine in agent.engines:
            if isinstance(engine, SinkEngine):
                engine._reserve(artifacts, task)


def _correlation(value: Any) -> str | None:
    return str(value) if value else None


def _retryable(status: int) -> bool:
    return status in RETRY_STATUSES or status >= 500


def _backoff(attempt: int) -> float:
    """After a timeout or a connection error: 0.5-1 s, then 1-2 s, ..."""
    return min(2.0**attempt * random.uniform(0.5, 1.0), MAX_RETRY_WAIT)  # nosec B311


def _common_visibility(artifacts: list[Artifact], sink: str) -> Visibility:
    """Receipts keep the delivered artifacts' readership; a batch of mixed
    readerships gives them to the sink alone."""
    visibilities = [artifact.visibility for artifact in artifacts]
    if visibilities and all(v == visibilities[0] for v in visibilities):
        return visibilities[0]
    return PrivateVisibility(agents={sink})


__all__ = ["SinkEngine", "SinkOrdering"]

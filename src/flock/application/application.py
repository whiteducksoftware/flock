"""Run a Flock application as isolated, observable workflows.

A :class:`FlockApplication` turns a factory that builds a configured
:class:`~flock.core.Flock` into a transport-independent execution API: every
workflow gets its own freshly built instance, a typed input, an explicit
output contract, an incremental stream of public outputs and exactly one
terminal :class:`~flock.application.WorkflowResult`.

The API has no dependency on any hosting framework. Hosts (ASGI services,
queue workers, agent runtimes such as ``flock.integrations.foundry``) map their own request
and lifecycle signals onto it.
"""

from __future__ import annotations

import asyncio
import inspect
import time
import weakref
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Mapping
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Literal, Protocol, Self, TypeVar

from pydantic import BaseModel, ValidationError

from flock.application.errors import (
    ApplicationNotRunning,
    CapacityExceeded,
    ContractError,
    InvalidWorkflowInput,
    SessionRequired,
    WorkflowIdConflict,
)
from flock.application.types import (
    CompletionPolicy,
    FailureCode,
    HistoryMode,
    OutputContract,
    WorkflowContext,
    WorkflowEvent,
    WorkflowFailure,
    WorkflowResult,
    WorkflowStatus,
)
from flock.core.conditions import bind_correlation
from flock.core.visibility import AgentIdentity
from flock.logging.logging import get_logger
from flock.orchestrator.workflow_runtime import WorkflowRuntime
from flock.registry import type_registry


if TYPE_CHECKING:
    from types import TracebackType

    from flock.core import Flock
    from flock.core.artifacts import Artifact
    from flock.core.conditions import RunCondition
    from flock.orchestrator.scheduler import AgentTaskOutcome


logger = get_logger(__name__)

WorkflowFactory = Callable[..., "Flock | Awaitable[Flock]"]
_T = TypeVar("_T")

_PROBE_ID = "__flock_contract_probe__"


class AdmissionController(Protocol):
    """Decides whether another workflow may start (reject, never queue)."""

    def try_acquire(self) -> bool: ...

    def release(self) -> None: ...


class CountingAdmission:
    """Admit at most ``limit`` concurrent workflows (``None`` = unlimited)."""

    def __init__(self, limit: int | None = None) -> None:
        if limit is not None and limit < 1:
            raise ValueError("limit must be >= 1")
        self._limit = limit
        self._active = 0

    @property
    def limit(self) -> int | None:
        """Maximum concurrent workflows (``None`` = unlimited)."""
        return self._limit

    def try_acquire(self) -> bool:
        if self._limit is not None and self._active >= self._limit:
            return False
        self._active += 1
        return True

    def release(self) -> None:
        self._active = max(0, self._active - 1)


class _FactoryError(Exception):
    """The factory failed or returned an unusable instance."""


class _StopRequested(Exception):  # noqa: N818 - a signal, not an error
    """The workflow was cancelled while a start-up step was still running."""


def _default_access_policy(artifact: Artifact, context: WorkflowContext) -> bool:
    caller = AgentIdentity(name="__caller__", tenant_id=context.principal_id)
    try:
        return bool(artifact.visibility.allows(caller))
    except Exception:  # pragma: no cover - defensive: unknown visibility = private
        return False


def _type_name(model: type[BaseModel]) -> str:
    return type_registry.register(model)


class _Workflow:
    """State of one admitted workflow (internal)."""

    def __init__(
        self,
        app: FlockApplication,
        value: BaseModel,
        context: WorkflowContext,
        deadline: float,
    ) -> None:
        self.app = app
        self.value = value
        self.context = context
        self.deadline = deadline
        self.outputs: list[WorkflowEvent] = []
        self.failure: WorkflowFailure | None = None
        self.fatal = False
        self.stop_reason: Literal["cancelled"] | None = None
        self.timed_out = False
        self.condition_met: bool | None = None
        self.frozen = False
        self.late_publications = 0
        self.failed_tasks = 0
        self.late_task_failures = 0
        self.build_started = False
        self.teardown_error: str | None = None
        self.runtime: WorkflowRuntime | None = None
        self.agent_names: set[str] = set()
        self.wake = asyncio.Event()
        # Set once on cancellation; unlike ``wake`` it is never cleared, so
        # start-up steps can race against it.
        self.stopped = asyncio.Event()
        self.changed = asyncio.Event()
        self.result: WorkflowResult | None = None
        self.driver: asyncio.Task[WorkflowResult] | None = None

    # -- signals -----------------------------------------------------------

    def request_stop(self, reason: Literal["cancelled"]) -> None:
        if self.stop_reason is None and not self.frozen:
            self.stop_reason = reason
            self.stopped.set()
        self.wake.set()

    def _fail(self, code: FailureCode, agent: str | None, *, fatal: bool) -> None:
        if self.failure is None:
            self.failure = WorkflowFailure.of(code, agent)
        if fatal:
            self.fatal = True
        self.wake.set()

    def on_publish(self, artifact: Artifact) -> None:
        """Publication listener: runs synchronously right after persistence.

        The publishing side swallows listener errors, so any failure here (for
        example a raising access policy) must end the workflow explicitly -
        otherwise the output would silently go missing.
        """
        try:
            self._observe(artifact)
        except Exception as exc:
            # No traceback: policies and payloads may carry private data.
            logger.error(  # noqa: TRY400
                f"Workflow {self.context.workflow_id}: output handling failed "
                f"for an artifact of {artifact.produced_by}: {type(exc).__name__}"
            )
            self._fail(FailureCode.INTERNAL_ERROR, artifact.produced_by, fatal=True)

    def _observe(self, artifact: Artifact) -> None:
        if self.frozen:
            self.late_publications += 1
            return
        app = self.app
        if artifact.type == app._workflow_error_type:
            agent = artifact.payload.get("failed_agent")
            self._fail(
                FailureCode.AGENT_FAILED,
                agent if isinstance(agent, str) else None,
                fatal=app.completion.on_error == "stop",
            )
            return
        model = app._output_models.get(artifact.type)
        if model is None or artifact.produced_by not in self.agent_names:
            return
        if not app._access_policy(artifact, self.context):
            return
        if len(self.outputs) >= app.max_outputs:
            self._fail(
                FailureCode.OUTPUT_LIMIT_EXCEEDED, artifact.produced_by, fatal=True
            )
            return
        try:
            value = model.model_validate(artifact.payload)
        except ValidationError:
            self._fail(FailureCode.INTERNAL_ERROR, artifact.produced_by, fatal=True)
            return
        self.outputs.append(
            WorkflowEvent(
                sequence=len(self.outputs),
                artifact=artifact.model_copy(deep=True),
                value=value,
            )
        )
        self.changed.set()
        self.wake.set()

    def on_task_outcome(self, outcome: AgentTaskOutcome) -> None:
        if self.frozen:
            # Outcomes of tasks cancelled during teardown never change the result.
            if outcome.outcome == "failed":
                self.late_task_failures += 1
            return
        if outcome.outcome == "failed":
            self.failed_tasks += 1
            self._fail(
                FailureCode.INTERNAL_ERROR,
                outcome.agent_name,
                fatal=self.app.completion.on_error == "stop",
            )

    # -- driver ------------------------------------------------------------

    async def drive(self) -> WorkflowResult:
        app = self.app
        session_key = app._session_key(self.context)
        session_locked = False
        try:
            try:
                async with asyncio.timeout_at(self.deadline) as deadline_scope:
                    if session_key is not None:
                        await self._unless_stopped(app._acquire_session(session_key))
                        session_locked = True
                    if self.stop_reason is not None:
                        raise _StopRequested
                    self.build_started = True
                    flock = await self._unless_stopped(app._build(self.context))
                    self.runtime = WorkflowRuntime(flock, self.context.workflow_id)
                    self.agent_names = {agent.name for agent in flock.agents}
                    self.runtime.install(
                        on_publish=self.on_publish,
                        on_task_outcome=self.on_task_outcome,
                    )
                    await self._unless_stopped(self.runtime.start(self.value))
                    await self._loop(self.runtime)
            except TimeoutError:
                if not deadline_scope.expired():
                    raise
                self.timed_out = True
        except _StopRequested:
            pass  # cancelled during start-up; stop_reason is already set
        except _FactoryError:
            logger.exception(f"Workflow {self.context.workflow_id}: factory failed")
            self._fail(FailureCode.FACTORY_ERROR, None, fatal=True)
        except asyncio.CancelledError:
            # Only the event loop cancels the driver directly (host shutdown).
            self.request_stop("cancelled")
        except Exception:
            logger.exception(f"Workflow {self.context.workflow_id}: unexpected error")
            self._fail(FailureCode.INTERNAL_ERROR, None, fatal=True)
        finally:
            self.frozen = True
            if self.runtime is not None:
                try:
                    await self.runtime.close(app.cancel_grace)
                except Exception as exc:
                    # The outcome stands (outputs may already be delivered);
                    # the failed cleanup is reported in the diagnostics.
                    self.teardown_error = type(exc).__name__
                    logger.exception(
                        f"Workflow {self.context.workflow_id}: teardown failed"
                    )
            if session_locked and session_key is not None:
                app._release_session(session_key)
            self.result = self._build_result()
            app._finish(self)
            self.changed.set()
        return self.result

    async def _unless_stopped(self, step: Awaitable[_T]) -> _T:
        """Await a start-up step unless the workflow is cancelled first.

        On cancellation the step is cancelled and awaited (a session lock that
        was granted in the meantime is released by the lock itself), then
        :class:`_StopRequested` ends the start-up.
        """
        task = asyncio.ensure_future(step)
        if self.stopped.is_set():
            task.cancel()
        stop = asyncio.ensure_future(self.stopped.wait())
        try:
            await asyncio.wait({task, stop}, return_when=asyncio.FIRST_COMPLETED)
        except BaseException:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise
        finally:
            stop.cancel()
        if task.done() and not task.cancelled():
            return task.result()  # the step wins ties: keep what it acquired
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        raise _StopRequested

    async def _loop(self, runtime: WorkflowRuntime) -> None:
        app = self.app
        until = app._until_for(self.context.workflow_id)
        if until is not None:
            self.condition_met = False
        while True:
            self.wake.clear()
            if self.stop_reason is not None or self.fatal:
                return
            if (
                until is not None
                and not self.condition_met
                and await until.evaluate(runtime.flock)
            ):
                self.condition_met = True
                if app.completion.on_condition == "stop":
                    return
            if runtime.is_quiescent():
                if await runtime.flush_partial_batches():
                    continue
                return
            await runtime.wait_for_progress(self.wake)

    def _build_result(self) -> WorkflowResult:
        app = self.app
        diagnostics: dict[str, Any] = {
            "late_publications": self.late_publications,
            "failed_tasks": self.failed_tasks,
            "late_task_failures": self.late_task_failures,
        }
        if self.teardown_error is not None:
            diagnostics["teardown_failed"] = self.teardown_error
        tripped: list[str] = []
        crashed: list[str] = []
        if self.runtime is not None:
            diagnostics.update(self.runtime.describe())
            tripped = list(self.runtime.diagnostics.tripped_agents)
            crashed = list(self.runtime.diagnostics.crashed_timers)

        failure = self.failure
        if self.stop_reason == "cancelled" and not self.fatal:
            status, failure = WorkflowStatus.CANCELLED, None
        elif self.timed_out and failure is None:
            status = WorkflowStatus.TIMED_OUT
        elif failure is not None:
            status = WorkflowStatus.FAILED
        elif tripped:
            status = WorkflowStatus.FAILED
            failure = WorkflowFailure.of(
                FailureCode.ITERATION_LIMIT_EXCEEDED, tripped[0]
            )
        elif crashed:
            status = WorkflowStatus.FAILED
            failure = WorkflowFailure.of(FailureCode.TIMER_FAILED, crashed[0])
        elif self.condition_met is False:
            status = WorkflowStatus.FAILED
            failure = WorkflowFailure.of(FailureCode.CONDITION_NOT_MET)
        else:
            produced = {event.artifact.type for event in self.outputs}
            missing = [name for name in app._required_names if name not in produced]
            if missing:
                status = WorkflowStatus.FAILED
                failure = WorkflowFailure.of(FailureCode.REQUIRED_OUTPUT_MISSING)
                diagnostics["missing_outputs"] = missing
            else:
                status = WorkflowStatus.SUCCEEDED
        return WorkflowResult(
            workflow_id=self.context.workflow_id,
            status=status,
            outputs=tuple(self.outputs),
            failure=failure,
            condition_met=self.condition_met,
            diagnostics=diagnostics,
        )


class WorkflowStream:
    """Handle of one running workflow.

    An async context manager that owns the workflow: leaving the block while it
    still runs cancels it and waits for its teardown. Iterate it for public
    outputs as they are published; the iteration ending is not an outcome -
    always check :meth:`result`.
    """

    def __init__(
        self,
        app: FlockApplication,
        value: BaseModel | Mapping[str, Any],
        context: WorkflowContext,
        timeout: float | None,
    ) -> None:
        self._app = app
        self._value = value
        self._context = context
        self._timeout = timeout
        self._workflow: _Workflow | None = None
        self._index = 0

    @property
    def workflow_id(self) -> str:
        return self._context.workflow_id

    async def __aenter__(self) -> Self:
        self._workflow = await self._app._admit(
            self._value, self._context, self._timeout
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        workflow = self._require()
        assert workflow.driver is not None
        if not workflow.driver.done():
            workflow.request_stop("cancelled")
        # Shielded: a second cancellation of the caller must not interrupt the
        # teardown; the driver still completes it in the background.
        await asyncio.shield(workflow.driver)

    def __aiter__(self) -> WorkflowStream:
        return self

    async def __anext__(self) -> WorkflowEvent:
        workflow = self._require()
        while True:
            if self._index < len(workflow.outputs):
                event = workflow.outputs[self._index]
                self._index += 1
                return event
            if workflow.result is not None:
                raise StopAsyncIteration
            workflow.changed.clear()
            if self._index < len(workflow.outputs) or workflow.result is not None:
                continue
            await workflow.changed.wait()

    async def result(self) -> WorkflowResult:
        """Wait for and return the terminal outcome."""
        workflow = self._require()
        assert workflow.driver is not None
        return await asyncio.shield(workflow.driver)

    def cancel(self) -> None:
        """Request cancellation; the result becomes ``cancelled``."""
        self._require().request_stop("cancelled")

    def _require(self) -> _Workflow:
        if self._workflow is None:
            raise RuntimeError("Use 'async with application.stream(...)' first.")
        return self._workflow


class FlockApplication:
    """Transport-independent execution API for a Flock application.

    Args:
        factory: Builds a fresh, configured ``Flock(no_output=True)`` for every
            workflow. Called as ``factory()`` or ``factory(context)``; may be
            async. Create shared, expensive resources (credentials, token
            providers, persistent stores) once outside the factory.
        input_type: Pydantic model accepted as workflow input.
        output_types: Public output types (an explicit allowlist).
        required_output_types: Outputs a successful workflow must produce.
        access_policy: ``(artifact, context) -> bool`` filter on top of the
            allowlist; defaults to the artifact's visibility for the caller.
        contract: Alternative to the four arguments above.
        completion: When a workflow is done (``until``, error handling).
        history: ``"conversation"`` requires a ``session_id`` and runs turns of
            the same principal and session one at a time; ``"stateless"``
            runs every workflow independently.
        max_outputs: Bound on buffered public outputs per workflow.
        default_timeout: Deadline (seconds) when a call passes none.
        max_timeout: Largest accepted deadline.
        cancel_grace: Seconds to wait for cancelled agent tasks at teardown.
        admission: Controller deciding whether a workflow may start.
        max_active_workflows: Shortcut for ``CountingAdmission(limit)``.
        id_retention: How long finished workflow ids stay reserved.
        max_retained_ids: Bound on reserved finished ids.
    """

    def __init__(
        self,
        factory: WorkflowFactory,
        *,
        input_type: type[BaseModel] | None = None,
        output_types: tuple[type[BaseModel], ...] = (),
        required_output_types: tuple[type[BaseModel], ...] = (),
        access_policy: Callable[[Artifact, WorkflowContext], bool] | None = None,
        contract: OutputContract | None = None,
        completion: CompletionPolicy | None = None,
        history: HistoryMode = "stateless",
        max_outputs: int = 1000,
        default_timeout: float = 600.0,
        max_timeout: float = 3600.0,
        cancel_grace: float = 5.0,
        admission: AdmissionController | None = None,
        max_active_workflows: int | None = None,
        id_retention: timedelta = timedelta(minutes=15),
        max_retained_ids: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if contract is None:
            if input_type is None:
                raise ValueError("Pass input_type/output_types or a contract.")
            contract = OutputContract(
                input_type=input_type,
                output_types=tuple(output_types),
                required_output_types=tuple(required_output_types),
                access_policy=access_policy,
            )
        if history not in ("stateless", "conversation"):
            raise ValueError("history must be 'stateless' or 'conversation'")
        if max_outputs < 1 or default_timeout <= 0 or max_timeout < default_timeout:
            raise ValueError("invalid limits: check max_outputs and timeouts")
        if max_retained_ids < 0 or id_retention < timedelta(0) or cancel_grace < 0:
            raise ValueError(
                "max_retained_ids, id_retention and cancel_grace must not be negative"
            )
        if admission is not None and max_active_workflows is not None:
            raise ValueError("Pass either admission or max_active_workflows.")

        self._factory = factory
        self._factory_takes_context = _takes_context(factory)
        self.contract = contract
        self.completion = completion or CompletionPolicy()
        self.history: HistoryMode = history
        self.max_outputs = max_outputs
        self.default_timeout = default_timeout
        self.max_timeout = max_timeout
        self.cancel_grace = cancel_grace
        self._admission: AdmissionController = admission or CountingAdmission(
            max_active_workflows
        )
        self._id_retention = id_retention.total_seconds()
        self._max_retained_ids = max_retained_ids
        self._clock = clock

        self._access_policy = contract.access_policy or _default_access_policy
        self._output_models: dict[str, type[BaseModel]] = {
            _type_name(model): model for model in contract.output_types
        }
        self._required_names = [
            _type_name(model) for model in contract.required_output_types
        ]
        from flock.models.system_artifacts import WorkflowError

        self._workflow_error_type = _type_name(WorkflowError)

        self._state: Literal["new", "running", "draining", "closed"] = "new"
        self._start_lock = asyncio.Lock()
        self._active: dict[str, _Workflow] = {}
        self._tombstones: OrderedDict[str, float] = OrderedDict()
        self._sessions: dict[tuple[str | None, str], list[Any]] = {}
        self._issued: weakref.WeakSet[Flock] = weakref.WeakSet()

    # -- lifecycle ---------------------------------------------------------

    @property
    def accepting(self) -> bool:
        """Whether new workflows are admitted (for readiness probes)."""
        return self._state == "running"

    @property
    def active_workflows(self) -> int:
        return len(self._active)

    @property
    def admission(self) -> AdmissionController:
        """The controller deciding whether another workflow may start."""
        return self._admission

    async def start(self) -> None:
        """Validate the factory and contract once; idempotent.

        Raises:
            ContractError: The factory or contract cannot work.
        """
        async with self._start_lock:
            if self._state == "running":
                return
            if self._state != "new":
                raise ApplicationNotRunning("The application was shut down.")
            await self._validate_contract()
            if self._state != "new":
                # shutdown() or begin_drain() ran while the contract was validated
                raise ApplicationNotRunning("The application was shut down.")
            self._state = "running"

    def begin_drain(self) -> None:
        """Stop admitting new workflows; running ones continue."""
        if self._state in ("new", "running"):
            self._state = "draining"

    async def shutdown(self, grace: float | None = None) -> None:
        """Stop admission, let running workflows finish for ``grace`` seconds,
        then cancel the rest and wait for their teardown."""
        self.begin_drain()
        drivers = [w.driver for w in self._active.values() if w.driver is not None]
        if drivers and grace:
            await asyncio.wait(drivers, timeout=grace)
        for workflow in list(self._active.values()):
            workflow.request_stop("cancelled")
        if drivers:
            await asyncio.gather(
                *(asyncio.shield(driver) for driver in drivers), return_exceptions=True
            )
        self._state = "closed"

    async def __aenter__(self) -> Self:
        await self.start()
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.shutdown(grace=self.cancel_grace)

    # -- execution ---------------------------------------------------------

    def stream(
        self,
        value: BaseModel | Mapping[str, Any],
        *,
        context: WorkflowContext,
        timeout: float | None = None,
    ) -> WorkflowStream:
        """Start a workflow and observe its public outputs incrementally.

        Use as ``async with app.stream(...) as workflow``. Admission errors
        (:class:`~flock.application.WorkflowRejected`) are raised on entry.
        """
        return WorkflowStream(self, value, context, timeout)

    async def run(
        self,
        value: BaseModel | Mapping[str, Any],
        *,
        context: WorkflowContext,
        timeout: float | None = None,  # noqa: ASYNC109 - the workflow deadline
    ) -> WorkflowResult:
        """Run a workflow to completion and return its outcome."""
        async with self.stream(value, context=context, timeout=timeout) as workflow:
            return await workflow.result()

    # -- internals -----------------------------------------------------------

    async def _admit(
        self,
        value: BaseModel | Mapping[str, Any],
        context: WorkflowContext,
        timeout: float | None,  # noqa: ASYNC109 - the workflow deadline
    ) -> _Workflow:
        coerced = self._coerce_input(value)
        seconds = self.default_timeout if timeout is None else timeout
        if seconds <= 0 or seconds > self.max_timeout:
            raise InvalidWorkflowInput(
                f"timeout must be in (0, {self.max_timeout}] seconds"
            )
        if self._state == "new":
            await self.start()
        if self._state != "running":
            raise ApplicationNotRunning("The application is not accepting workflows.")
        if self.history == "conversation" and context.session_id is None:
            raise SessionRequired("Conversation history mode needs a session_id.")

        # Synchronous from here: check and register without interleaving.
        self._prune_tombstones()
        workflow_id = context.workflow_id
        if workflow_id in self._active or workflow_id in self._tombstones:
            # Same answer whoever owns the id, so ids cannot be probed.
            raise WorkflowIdConflict(f"Workflow id {workflow_id!r} is not available.")
        if not self._admission.try_acquire():
            raise CapacityExceeded("Too many active workflows; retry later.")

        loop = asyncio.get_running_loop()
        workflow = _Workflow(self, coerced, context, loop.time() + seconds)
        self._active[workflow_id] = workflow
        workflow.driver = loop.create_task(
            workflow.drive(), name=f"flock-workflow-{workflow_id}"
        )
        return workflow

    def _coerce_input(self, value: BaseModel | Mapping[str, Any]) -> BaseModel:
        input_type = self.contract.input_type
        if isinstance(value, input_type):
            return value
        try:
            if isinstance(value, BaseModel):
                return input_type.model_validate(value.model_dump())
            if isinstance(value, Mapping):
                return input_type.model_validate(dict(value))
        except ValidationError as exc:
            raise InvalidWorkflowInput(
                f"Input does not match {input_type.__name__}: {exc.error_count()} error(s)"
            ) from exc
        raise InvalidWorkflowInput(
            f"Input must be a {input_type.__name__} or a mapping of its fields."
        )

    def _finish(self, workflow: _Workflow) -> None:
        workflow_id = workflow.context.workflow_id
        if self._active.get(workflow_id) is workflow:
            del self._active[workflow_id]
            self._admission.release()
        if workflow.build_started:
            self._tombstones[workflow_id] = self._clock()
            self._tombstones.move_to_end(workflow_id)
            while len(self._tombstones) > self._max_retained_ids:
                self._tombstones.popitem(last=False)

    def _prune_tombstones(self) -> None:
        cutoff = self._clock() - self._id_retention
        while self._tombstones:
            workflow_id, finished_at = next(iter(self._tombstones.items()))
            if finished_at > cutoff:
                break
            del self._tombstones[workflow_id]

    def _session_key(self, context: WorkflowContext) -> tuple[str | None, str] | None:
        if self.history != "conversation" or context.session_id is None:
            return None
        return (context.principal_id, context.session_id)

    async def _acquire_session(self, key: tuple[str | None, str]) -> None:
        entry = self._sessions.get(key)
        if entry is None:
            entry = [asyncio.Lock(), 0]
            self._sessions[key] = entry
        entry[1] += 1
        try:
            await entry[0].acquire()
        except BaseException:
            self._drop_session_waiter(key)
            raise

    def _release_session(self, key: tuple[str | None, str]) -> None:
        entry = self._sessions.get(key)
        if entry is None:  # pragma: no cover - defensive
            return
        entry[0].release()
        self._drop_session_waiter(key)

    def _drop_session_waiter(self, key: tuple[str | None, str]) -> None:
        entry = self._sessions.get(key)
        if entry is None:  # pragma: no cover - defensive
            return
        entry[1] -= 1
        if entry[1] <= 0:
            del self._sessions[key]

    async def _build(self, context: WorkflowContext) -> Flock:
        try:
            built = (
                self._factory(context)
                if self._factory_takes_context
                else self._factory()
            )
            if inspect.isawaitable(built):
                built = await built
        except Exception as exc:
            raise _FactoryError("factory raised") from exc
        problem = self._pristine_problem(built)
        if problem:
            raise _FactoryError(problem)
        self._issued.add(built)
        return built

    def _pristine_problem(self, flock: Any) -> str | None:
        from flock.core import Flock

        if not isinstance(flock, Flock):
            return "the factory must return a Flock instance"
        if flock in self._issued:
            return "the factory returned an instance that was already used"
        if not flock.no_output:
            return "the factory must build Flock(no_output=True) for hosted use"
        if (
            flock.metrics.get("artifacts_published", 0)
            or flock._component_runner._initialized
            or flock._server_task is not None
        ):
            return "the factory must return a fresh, unstarted Flock"
        return None

    def _until_for(self, workflow_id: str) -> RunCondition | None:
        until = self.completion.until
        if until is None:
            return None
        return bind_correlation(until, workflow_id, strict=True)

    async def _validate_contract(self) -> None:
        try:
            probe = await self._build(WorkflowContext(workflow_id=_PROBE_ID))
        except _FactoryError as exc:
            cause = exc.__cause__
            detail = f"{exc}: {type(cause).__name__}: {cause}" if cause else str(exc)
            raise ContractError(f"Invalid factory - {detail}") from exc
        try:
            self._check_contract(probe)
        finally:
            # The probe is only inspected; release what the factory opened for it.
            try:
                await probe.shutdown(include_components=False)
            except Exception:  # pragma: no cover - best effort
                logger.exception("Contract probe shutdown failed")

    def _check_contract(self, probe: Flock) -> None:
        problems: list[str] = []
        contract = self.contract
        input_name = _type_name(contract.input_type)
        consumed = {
            name
            for agent in probe.agents
            for subscription in agent.subscriptions
            if subscription.accepts_events()
            for name in subscription.type_names
        }
        if input_name not in consumed:
            problems.append(f"no agent consumes the input type {input_name}")

        published = {
            output.spec.type_name for agent in probe.agents for output in agent.outputs
        }
        problems.extend(
            f"no agent publishes the output type {name}"
            for name in self._output_models
            if name not in published
        )

        from flock.models.system_artifacts import TimerTick

        internal = {self._workflow_error_type, _type_name(TimerTick)}
        problems.extend(
            f"{name} is internal and cannot be a public output"
            for name in self._output_models
            if name in internal
        )

        for model in (contract.input_type, *contract.output_types):
            name = _type_name(model)
            if type_registry.resolve(name) is not model:
                problems.append(
                    f"type name {name} is registered to another class; define "
                    "artifact models once at module level with unique names"
                )

        scheduled = [a.name for a in probe.agents if getattr(a, "schedule_spec", None)]
        if scheduled and self.completion.until is None:
            problems.append(
                "scheduled agents (" + ", ".join(sorted(scheduled)) + ") run "
                "open-ended; set CompletionPolicy(until=...) and rely on the deadline"
            )
        if self.completion.until is not None:
            try:
                bind_correlation(self.completion.until, _PROBE_ID, strict=True)
            except ValueError as exc:
                problems.append(str(exc))

        if problems:
            raise ContractError("; ".join(problems))

        from flock.core import Agent

        if Agent._websocket_broadcast_global is not None:
            logger.warning(
                "A dashboard is being served in this process; it will receive every "
                "workflow's live output. Do not co-host the dashboard with hosted "
                "workflows."
            )


def _takes_context(factory: Callable[..., Any]) -> bool:
    try:
        signature = inspect.signature(factory)
    except (TypeError, ValueError):  # pragma: no cover - builtins
        return False
    positional = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    if any(
        p.kind is inspect.Parameter.VAR_POSITIONAL
        for p in signature.parameters.values()
    ):
        return True
    return bool(positional)


__all__ = [
    "AdmissionController",
    "CountingAdmission",
    "FlockApplication",
    "WorkflowFactory",
    "WorkflowStream",
]

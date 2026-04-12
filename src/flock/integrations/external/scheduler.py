"""ExternalAgentScheduler — OrchestratorComponent that bridges changelog
events to external agent processes.

Responsibilities:
  1. Discover agents with agent_kind="external" from the orchestrator registry.
  2. Subscribe to the StreamDispatcher for changelog events.
  3. Match incoming events against external agent subscriptions (type_names).
  4. Maintain a serial asyncio.Queue per agent name.
  5. Spawn via a registered ExternalAgentRuntime adapter.
  6. Track active processes for graceful shutdown.
"""

from __future__ import annotations

import asyncio
import inspect
import os
import signal
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Annotated, Union

from pydantic import Discriminator, Field, PrivateAttr, Tag

from flock.components.orchestrator.base import OrchestratorComponent
from flock.core.visibility import (
    AfterVisibility,
    AgentIdentity,
    LabelledVisibility,
    PrivateVisibility,
    PublicVisibility,
    TenantVisibility,
    Visibility,
)
from flock.integrations.external.models import (
    AgentOutcome,
    ExternalSessionStore,
    SQLiteExternalSessionStore,
    SpawnConfig,
    SpawnResult,
)
from flock.integrations.external.runtime import ExternalAgentRuntime
from flock.logging.logging import get_logger
from flock.models.changelog import ChangelogEvent, ChangelogEventType, ChangelogFilter


if TYPE_CHECKING:
    from flock.auth.token_store import TokenStore
    from flock.components.server.changelog.stream_dispatcher import (
        StreamDispatcher,
        Subscription as StreamSubscription,
    )
    from flock.core import Flock
    from flock.core.agent import Agent

# Discriminated union for reconstructing Visibility from serialized dicts.
_VisibilityUnion = Annotated[
    Union[
        Annotated[PublicVisibility, Tag("Public")],
        Annotated[PrivateVisibility, Tag("Private")],
        Annotated[LabelledVisibility, Tag("Labelled")],
        Annotated[TenantVisibility, Tag("Tenant")],
        Annotated[AfterVisibility, Tag("After")],
    ],
    Discriminator("kind"),
]

logger = get_logger(__name__)

# Grace period (seconds) between SIGTERM and SIGKILL during shutdown.
_SHUTDOWN_GRACE: float = 5.0


def _reconstruct_visibility(data: dict[str, Any]) -> Visibility:
    """Reconstruct a :class:`Visibility` subclass from a serialized dict.

    The ``kind`` discriminator field is used to select the correct subclass
    via Pydantic's ``TypeAdapter``.
    """
    from pydantic import TypeAdapter

    _adapter: TypeAdapter[Visibility] = TypeAdapter(_VisibilityUnion)
    return _adapter.validate_python(data)


class ExternalAgentScheduler(OrchestratorComponent):
    """Orchestrator component that dispatches changelog events to external agents.

    External agents are discovered from the Flock agent registry — any agent
    with ``agent_kind="external"`` is managed by this scheduler.  Type matching
    uses the standard ``Subscription.type_names`` from ``.consumes()``.

    Runtime adapters (``ExternalAgentRuntime`` implementations) are registered
    by adapter name via ``configure()``.

    The scheduler owns one ``asyncio.Queue`` per external agent and processes
    events serially (one spawn at a time per agent).
    """

    name: str | None = "ExternalAgentScheduler"
    priority: int = 100  # Run after core components

    # --- injected dependencies (not serialized) ---
    _stream_dispatcher: StreamDispatcher | None = PrivateAttr(default=None)
    _adapters: dict[str, ExternalAgentRuntime] = PrivateAttr(default_factory=dict)

    # --- discovered at init from orchestrator.agents ---
    _external_agents: dict[str, Agent] = PrivateAttr(default_factory=dict)

    # --- internal state ---
    _session_store: ExternalSessionStore | SQLiteExternalSessionStore = PrivateAttr(
        default_factory=ExternalSessionStore
    )
    _queues: dict[str, asyncio.Queue[ChangelogEvent]] = PrivateAttr(
        default_factory=dict
    )
    _workers: dict[str, asyncio.Task[None]] = PrivateAttr(default_factory=dict)
    _active_spawns: dict[str, SpawnResult] = PrivateAttr(default_factory=dict)
    _stream_sub: StreamSubscription | None = PrivateAttr(default=None)
    _listener_task: asyncio.Task[None] | None = PrivateAttr(default=None)
    _started: bool = PrivateAttr(default=False)
    _token_store: TokenStore | None = PrivateAttr(default=None)
    _api_url: str | None = PrivateAttr(default=None)

    # ------------------------------------------------------------------
    # Construction helper (call after __init__)
    # ------------------------------------------------------------------

    def configure(
        self,
        *,
        stream_dispatcher: StreamDispatcher,
        adapters: dict[str, ExternalAgentRuntime],
    ) -> ExternalAgentScheduler:
        """Inject runtime dependencies.  Returns self for chaining."""
        self._stream_dispatcher = stream_dispatcher
        self._adapters = dict(adapters)
        return self

    def set_token_store(
        self,
        store: TokenStore,
        *,
        api_url: str | None = None,
    ) -> ExternalAgentScheduler:
        """Attach a token store for automatic credential injection.

        Args:
            store: Token store used to create short-lived tokens.
            api_url: Base URL of the Flock REST API.  Falls back to
                     the ``FLOCK_API_URL`` environment variable.

        Returns:
            self for chaining.
        """
        self._token_store = store
        self._api_url = api_url or os.environ.get("FLOCK_API_URL")
        return self

    def set_session_store(
        self,
        store: ExternalSessionStore | SQLiteExternalSessionStore,
    ) -> ExternalAgentScheduler:
        """Replace the default in-memory session store.

        Pass a :class:`SQLiteExternalSessionStore` to persist sessions
        across restarts.

        Returns:
            self for chaining.
        """
        self._session_store = store
        return self

    # ------------------------------------------------------------------
    # Lifecycle: on_initialize
    # ------------------------------------------------------------------

    async def on_initialize(self, orchestrator: Flock) -> None:
        """Discover external agents, subscribe to changelog, start workers."""
        if self._started:
            return
        if self._stream_dispatcher is None:
            logger.warning(
                "ExternalAgentScheduler: no StreamDispatcher configured — skipping"
            )
            return

        # Discover external agents from the orchestrator's agent registry
        for agent in orchestrator.agents:
            if agent.agent_kind == "external":
                if agent.adapter_name is None:
                    logger.warning(
                        f"External agent {agent.name!r} has no adapter_name — skipping"
                    )
                    continue
                if agent.adapter_name not in self._adapters:
                    logger.warning(
                        f"External agent {agent.name!r} uses adapter "
                        f"{agent.adapter_name!r} which is not registered — skipping"
                    )
                    continue
                if agent.working_dir is None:
                    logger.warning(
                        f"External agent {agent.name!r} has no working_dir — using /tmp"
                    )
                self._external_agents[agent.name] = agent

        if not self._external_agents:
            logger.info("ExternalAgentScheduler: no external agents found")
            return

        # Subscribe to all artifact_published events
        self._stream_sub = await self._stream_dispatcher.subscribe(
            filters=ChangelogFilter(
                event_types={ChangelogEventType.artifact_published}
            ),
        )

        # Create per-agent queues and worker tasks
        for agent_name in self._external_agents:
            queue: asyncio.Queue[ChangelogEvent] = asyncio.Queue()
            self._queues[agent_name] = queue
            task = asyncio.create_task(
                self._worker_loop(agent_name, queue),
                name=f"ext-worker-{agent_name}",
            )
            self._workers[agent_name] = task

        # Start the listener
        self._listener_task = asyncio.create_task(
            self._listener_loop(), name="ext-scheduler-listener"
        )
        self._started = True
        logger.info(
            f"ExternalAgentScheduler started: "
            f"{list(self._external_agents.keys())}"
        )

    # ------------------------------------------------------------------
    # Lifecycle: on_shutdown
    # ------------------------------------------------------------------

    async def on_shutdown(self, orchestrator: Flock) -> None:
        """Terminate all active processes and cancel worker tasks."""
        if not self._started:
            return
        self._started = False

        # 1. Cancel the stream listener
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

        # 2. Cancel all per-agent worker tasks
        for name, task in self._workers.items():
            if not task.done():
                task.cancel()
        await asyncio.gather(*self._workers.values(), return_exceptions=True)

        # 3. Terminate any still-running spawned processes
        await self._terminate_all_active()

        # 4. Unsubscribe from the stream
        if self._stream_dispatcher and self._stream_sub:
            await self._stream_dispatcher.unsubscribe(self._stream_sub.id)

        self._queues.clear()
        self._workers.clear()
        self._external_agents.clear()
        logger.info("ExternalAgentScheduler shutdown complete")

    # ------------------------------------------------------------------
    # Stream listener
    # ------------------------------------------------------------------

    async def _listener_loop(self) -> None:
        """Read serialized events from the stream subscription and route them."""
        if self._stream_sub is None:
            raise RuntimeError("StreamDispatcher subscription not initialized")
        try:
            while True:
                serialized = await self._stream_sub.queue.get()
                try:
                    event = ChangelogEvent.model_validate_json(serialized)
                except Exception:
                    logger.exception("Failed to deserialize changelog event")
                    continue
                await self._route_event(event)
        except asyncio.CancelledError:
            return

    async def _route_event(self, event: ChangelogEvent) -> None:
        """Match a changelog event against external agent subscriptions."""
        artifact_type = event.artifact_type
        if artifact_type is None:
            return

        for agent_name, agent in self._external_agents.items():
            queue = self._queues.get(agent_name)
            if queue is None:
                continue

            # Use the agent's subscriptions for type matching
            matched = False
            for sub in agent.subscriptions:
                if artifact_type in sub.type_names:
                    matched = True
                    break

            if not matched:
                continue

            # Visibility check: ensure the agent is allowed to see this artifact
            if event.visibility is not None:
                try:
                    vis: Visibility = _reconstruct_visibility(event.visibility)
                    identity = AgentIdentity(
                        name=agent.name,
                        labels=getattr(agent, "labels", set()),
                        tenant_id=getattr(agent, "tenant_id", None),
                    )
                    if not vis.allows(identity):
                        logger.debug(
                            f"Agent {agent_name} blocked by visibility "
                            f"({vis.kind}) for event (type={artifact_type})"
                        )
                        continue
                except Exception:
                    logger.warning(
                        f"Could not reconstruct visibility for event "
                        f"(type={artifact_type}) — allowing by default",
                        exc_info=True,
                    )

            # Prevent self-trigger: skip if the agent produced this artifact
            if agent.prevent_self_trigger and event.produced_by == agent_name:
                continue

            logger.debug(
                f"Routing event (type={artifact_type}) → agent {agent_name}"
            )
            await queue.put(event)

    # ------------------------------------------------------------------
    # Per-agent serial worker
    # ------------------------------------------------------------------

    async def _worker_loop(
        self, agent_name: str, queue: asyncio.Queue[ChangelogEvent]
    ) -> None:
        """Process events one at a time for a single external agent."""
        try:
            while True:
                event = await queue.get()
                try:
                    await self._handle_event(agent_name, event)
                except Exception:
                    logger.exception(
                        f"Error handling event for agent {agent_name}"
                    )
                finally:
                    queue.task_done()
        except asyncio.CancelledError:
            return

    async def _handle_event(
        self, agent_name: str, event: ChangelogEvent
    ) -> AgentOutcome:
        """Resolve config from agent, build SpawnConfig, spawn, monitor."""
        agent = self._external_agents[agent_name]
        adapter = self._adapters.get(agent.adapter_name or "")
        if adapter is None:
            logger.error(
                f"No adapter '{agent.adapter_name}' for agent {agent_name}"
            )
            return AgentOutcome(
                success=False,
                returncode=-1,
                stdout="",
                stderr=f"Missing adapter: {agent.adapter_name}",
                session_id="",
            )

        # --- Guard hook point ---
        # Future: for guard in agent.guards:
        #     verdict = await guard.scan_input(prompt, [event.payload_summary])
        #     if not verdict.safe and guard.config.on_input_flagged == "block":
        #         emit guard_blocked event; continue

        # Resolve session mode from the first subscription that matches
        artifact_type = event.artifact_type or ""
        session_mode = "new"
        for sub in agent.subscriptions:
            if artifact_type in sub.type_names and sub.session_mode:
                session_mode = sub.session_mode
                break

        session_id: str | None = None
        if session_mode == "resume":
            result = self._session_store.get(agent_name, artifact_type)
            stored = (await result) if inspect.isawaitable(result) else result
            if stored is not None:
                session_id = stored
            else:
                logger.warning(
                    f"Agent {agent_name}: session_mode='resume' but no stored "
                    f"session for {artifact_type!r} — falling back to 'new'"
                )
                session_mode = "new"

        # Build prompt from the event
        prompt = self._build_prompt(event)
        working_dir = Path(agent.working_dir or "/tmp")
        timeout = agent.spawn_timeout

        # Build env vars: start with injected credentials, then let
        # agent.spawn_env override (explicit user config wins).
        env_vars: dict[str, str] = {}
        if self._token_store is not None:
            try:
                env_vars.update(
                    await self._create_agent_credentials(agent, timeout)
                )
            except Exception:
                logger.warning(
                    f"Failed to create credentials for agent {agent_name}",
                    exc_info=True,
                )
        env_vars.update(agent.spawn_env)  # agent overrides take precedence

        spawn_cfg = SpawnConfig(
            prompt=prompt,
            working_dir=working_dir,
            env_vars=env_vars,
            session_id=session_id,
            session_mode=session_mode,
            timeout=timeout,
        )

        # Spawn
        try:
            result = await adapter.spawn(spawn_cfg)
        except Exception:
            logger.exception(f"Spawn failed for agent {agent_name}")
            return AgentOutcome(
                success=False,
                returncode=-1,
                stdout="",
                stderr="spawn raised exception",
                session_id=session_id or "",
            )

        self._active_spawns[agent_name] = result

        # Monitor with timeout.  The try/finally guarantees
        # _active_spawns cleanup even on CancelledError (shutdown).
        try:
            try:
                outcome = await asyncio.wait_for(
                    adapter.monitor(result), timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"Agent {agent_name} timed out after {timeout}s")
                try:
                    await adapter.terminate(result)
                except Exception:
                    logger.exception(f"Terminate failed for agent {agent_name}")
                outcome = AgentOutcome(
                    success=False,
                    returncode=-1,
                    stdout="",
                    stderr=f"timeout after {timeout}s",
                    session_id=result.session_id,
                )
            except asyncio.CancelledError:
                # Shutdown in progress — terminate this process
                try:
                    await adapter.terminate(result)
                except Exception:
                    pass
                raise
        finally:
            self._active_spawns.pop(agent_name, None)

        # Persist session for future resume
        if outcome.session_id:
            result = self._session_store.set(
                agent_name, artifact_type, outcome.session_id
            )
            if inspect.isawaitable(result):
                await result

        if outcome.success:
            logger.info(f"Agent {agent_name} completed successfully")
        else:
            logger.warning(
                f"Agent {agent_name} failed: rc={outcome.returncode}, "
                f"stderr={outcome.stderr[:200]}"
            )
        return outcome

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_prompt(event: ChangelogEvent) -> str:
        """Derive a prompt string from a changelog event."""
        parts: list[str] = []
        if event.artifact_type:
            parts.append(f"[{event.artifact_type}]")
        if event.produced_by:
            parts.append(f"from {event.produced_by}")
        if event.correlation_id:
            parts.append(f"correlation_id={event.correlation_id}")
        if event.artifact_id:
            parts.append(f"artifact_id={event.artifact_id}")
        summary = event.payload_summary
        if summary:
            for key, value in summary.items():
                parts.append(f"{key}={value}")
        return " ".join(parts) if parts else "changelog event"

    async def _create_agent_credentials(
        self, agent: Agent, timeout: float
    ) -> dict[str, str]:
        """Create a short-lived token for *agent* and return env vars to inject."""
        from flock.auth.token_models import TokenCreateRequest
        from flock.auth.token_store import create_token

        # Collect the artifact type names this agent publishes
        publishes_types: set[str] = set()
        for group in agent.output_groups:
            for out in group.outputs:
                publishes_types.add(out.spec.type_name)

        expires_at = datetime.now(UTC) + timedelta(seconds=timeout * 2)

        request = TokenCreateRequest(
            identity_name=agent.name,
            identity_labels=getattr(agent, "labels", set()),
            identity_tenant_id=getattr(agent, "tenant_id", None),
            allowed_types=publishes_types,
            scopes={"artifact:publish", "artifact:read"},
            expires_at=expires_at,
        )
        raw_token, record = create_token(request)

        assert self._token_store is not None  # caller checks before calling
        await self._token_store.store(record)

        env: dict[str, str] = {"FLOCK_API_TOKEN": raw_token}
        if self._api_url:
            env["FLOCK_API_URL"] = self._api_url
        return env

    async def _terminate_all_active(self) -> None:
        """SIGTERM → grace → SIGKILL for every active spawn."""
        if not self._active_spawns:
            return

        for agent_name, result in list(self._active_spawns.items()):
            proc = result.process
            if proc.returncode is not None:
                continue  # already exited
            try:
                proc.send_signal(signal.SIGTERM)
            except (ProcessLookupError, OSError):
                continue

        # Wait briefly for graceful exits
        await asyncio.sleep(min(_SHUTDOWN_GRACE, 2.0))

        for agent_name, result in list(self._active_spawns.items()):
            proc = result.process
            if proc.returncode is not None:
                continue
            try:
                proc.kill()
            except (ProcessLookupError, OSError):
                pass

        self._active_spawns.clear()

    @property
    def session_store(self) -> ExternalSessionStore | SQLiteExternalSessionStore:
        """Expose session store for testing and introspection."""
        return self._session_store

    @property
    def active_agent_count(self) -> int:
        """Number of agents currently running a spawned process."""
        return len(self._active_spawns)

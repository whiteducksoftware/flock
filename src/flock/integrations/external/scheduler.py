"""ExternalAgentScheduler — OrchestratorComponent that bridges changelog
events to external agent processes.

Responsibilities:
  1. Discover agents with agent_kind="external" from the orchestrator registry.
  2. Subscribe to the StreamDispatcher for changelog events.
  3. Match incoming events against external agent subscriptions (type match).
  4. Maintain a serial asyncio.Queue per agent name.
  5. Spawn via a registered ExternalAgentRuntime adapter.
  6. Track active processes for graceful shutdown.
"""

from __future__ import annotations

import asyncio
import signal
from typing import TYPE_CHECKING, Any

from pydantic import Field, PrivateAttr

from flock.components.orchestrator.base import OrchestratorComponent
from flock.integrations.external.models import (
    AgentOutcome,
    ExternalAgentConfig,
    ExternalSessionStore,
    SpawnConfig,
    SpawnResult,
)
from flock.integrations.external.runtime import ExternalAgentRuntime
from flock.logging.logging import get_logger
from flock.models.changelog import ChangelogEvent, ChangelogFilter


if TYPE_CHECKING:
    from flock.components.server.changelog.stream_dispatcher import (
        StreamDispatcher,
        Subscription as StreamSubscription,
    )
    from flock.core import Flock

logger = get_logger(__name__)

# Grace period (seconds) between SIGTERM and SIGKILL during shutdown.
_SHUTDOWN_GRACE: float = 5.0


class ExternalAgentScheduler(OrchestratorComponent):
    """Orchestrator component that dispatches changelog events to external agents.

    Inject dependencies at construction time:
        - stream_dispatcher: The StreamDispatcher that publishes changelog events.
        - adapters: Mapping of adapter_name → ExternalAgentRuntime implementation.
        - external_agents: Mapping of agent_name → ExternalAgentConfig.

    The scheduler owns one asyncio.Queue per registered agent and processes
    events serially (one spawn at a time per agent).
    """

    name: str | None = "ExternalAgentScheduler"
    priority: int = 100  # Run after core components

    # --- injected dependencies (not serialized) ---
    _stream_dispatcher: StreamDispatcher | None = PrivateAttr(default=None)
    _adapters: dict[str, ExternalAgentRuntime] = PrivateAttr(default_factory=dict)
    _external_agents: dict[str, ExternalAgentConfig] = PrivateAttr(default_factory=dict)

    # --- internal state ---
    _session_store: ExternalSessionStore = PrivateAttr(
        default_factory=ExternalSessionStore
    )
    _queues: dict[str, asyncio.Queue[ChangelogEvent]] = PrivateAttr(default_factory=dict)
    _workers: dict[str, asyncio.Task[None]] = PrivateAttr(default_factory=dict)
    _active_spawns: dict[str, SpawnResult] = PrivateAttr(default_factory=dict)
    _stream_sub: StreamSubscription | None = PrivateAttr(default=None)
    _listener_task: asyncio.Task[None] | None = PrivateAttr(default=None)
    _started: bool = PrivateAttr(default=False)

    # ------------------------------------------------------------------
    # Construction helper (call after __init__)
    # ------------------------------------------------------------------

    def configure(
        self,
        *,
        stream_dispatcher: StreamDispatcher,
        adapters: dict[str, ExternalAgentRuntime],
        external_agents: dict[str, ExternalAgentConfig],
    ) -> ExternalAgentScheduler:
        """Inject runtime dependencies.  Returns self for chaining."""
        self._stream_dispatcher = stream_dispatcher
        self._adapters = dict(adapters)
        self._external_agents = dict(external_agents)
        return self

    # ------------------------------------------------------------------
    # Lifecycle: on_initialize
    # ------------------------------------------------------------------

    async def on_initialize(self, orchestrator: Flock) -> None:
        """Subscribe to the changelog stream and start per-agent workers."""
        if self._started:
            return
        if self._stream_dispatcher is None:
            logger.warning(
                "ExternalAgentScheduler: no StreamDispatcher configured — skipping"
            )
            return
        if not self._external_agents:
            logger.info("ExternalAgentScheduler: no external agents registered")
            return

        # Build a ChangelogFilter from all subscribed artifact types.
        all_types: set[str] = set()
        for agent_name, cfg in self._external_agents.items():
            # We will rely on the caller to set up the types.
            # For now, subscribe to all artifact_published events.
            pass

        self._stream_sub = await self._stream_dispatcher.subscribe(
            filters=ChangelogFilter(event_types={"artifact_published"}),
        )

        # Create per-agent queues and worker tasks.
        for agent_name in self._external_agents:
            queue: asyncio.Queue[ChangelogEvent] = asyncio.Queue()
            self._queues[agent_name] = queue
            task = asyncio.create_task(
                self._worker_loop(agent_name, queue),
                name=f"ext-worker-{agent_name}",
            )
            self._workers[agent_name] = task

        # Start the listener that reads from the stream subscription.
        self._listener_task = asyncio.create_task(
            self._listener_loop(), name="ext-scheduler-listener"
        )
        self._started = True
        logger.info(
            f"ExternalAgentScheduler started: {len(self._external_agents)} agents"
        )

    # ------------------------------------------------------------------
    # Lifecycle: on_shutdown
    # ------------------------------------------------------------------

    async def on_shutdown(self, orchestrator: Flock) -> None:
        """Terminate all active processes and cancel worker tasks."""
        if not self._started:
            return
        self._started = False

        # 1. Cancel the stream listener.
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

        # 2. Cancel all per-agent worker tasks.
        for name, task in self._workers.items():
            if not task.done():
                task.cancel()
        await asyncio.gather(*self._workers.values(), return_exceptions=True)

        # 3. Terminate any still-running spawned processes.
        await self._terminate_all_active()

        # 4. Unsubscribe from the stream.
        if self._stream_dispatcher and self._stream_sub:
            await self._stream_dispatcher.unsubscribe(self._stream_sub.id)

        self._queues.clear()
        self._workers.clear()
        logger.info("ExternalAgentScheduler shutdown complete")

    # ------------------------------------------------------------------
    # Stream listener
    # ------------------------------------------------------------------

    async def _listener_loop(self) -> None:
        """Read serialized events from the stream subscription and route them."""
        assert self._stream_sub is not None
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
        """Match a changelog event to external agents and enqueue."""
        artifact_type = event.artifact_type
        if artifact_type is None:
            return

        for agent_name, cfg in self._external_agents.items():
            queue = self._queues.get(agent_name)
            if queue is None:
                continue
            # Type matching: the scheduler accepts the event if the
            # external agent's subscribed types include this artifact_type.
            # For simplicity, we store subscribed types on the config
            # via the `subscribed_types` set populated by the caller.
            subscribed_types = getattr(cfg, "subscribed_types", None)
            if subscribed_types is not None and artifact_type not in subscribed_types:
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
        """Resolve config, build SpawnConfig, spawn, monitor, record."""
        cfg = self._external_agents[agent_name]
        adapter = self._adapters.get(cfg.adapter_name)
        if adapter is None:
            logger.error(
                f"No adapter '{cfg.adapter_name}' registered for agent {agent_name}"
            )
            return AgentOutcome(
                success=False,
                returncode=-1,
                stdout="",
                stderr=f"Missing adapter: {cfg.adapter_name}",
                session_id="",
            )

        # --- Guard hook point ---
        # Future: if cfg.guard is not None:
        #     verdict = await cfg.guard.scan_input(prompt_text, documents=[...])
        #     if not verdict.safe:
        #         logger.warning(f"Guard blocked input for {agent_name}: {verdict.reason}")
        #         return AgentOutcome(success=False, returncode=-1, ...)

        # Resolve session
        artifact_type = event.artifact_type or ""
        session_id: str | None = None
        effective_mode = cfg.session_mode

        if cfg.session_mode == "resume":
            stored = self._session_store.get(agent_name, artifact_type)
            if stored is not None:
                session_id = stored
            else:
                logger.warning(
                    f"Agent {agent_name}: session_mode='resume' but no stored "
                    f"session for artifact_type={artifact_type!r} — falling back to 'new'"
                )
                effective_mode = "new"

        # Build prompt from the event payload summary
        prompt = self._build_prompt(event)

        spawn_cfg = SpawnConfig(
            prompt=prompt,
            working_dir=cfg.working_dir,
            env_vars=cfg.env_vars,
            session_id=session_id,
            session_mode=effective_mode,
            timeout=cfg.timeout,
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

        # Monitor with timeout
        try:
            outcome = await asyncio.wait_for(
                adapter.monitor(result), timeout=cfg.timeout
            )
        except asyncio.TimeoutError:
            logger.warning(f"Agent {agent_name} timed out after {cfg.timeout}s")
            try:
                await adapter.terminate(result)
            except Exception:
                logger.exception(f"Terminate failed for agent {agent_name}")
            outcome = AgentOutcome(
                success=False,
                returncode=-1,
                stdout="",
                stderr=f"timeout after {cfg.timeout}s",
                session_id=result.session_id,
            )
        finally:
            self._active_spawns.pop(agent_name, None)

        # Persist session for future resume
        if outcome.session_id:
            self._session_store.set(agent_name, artifact_type, outcome.session_id)

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
        summary = event.payload_summary
        if summary:
            for key, value in summary.items():
                parts.append(f"{key}={value}")
        return " ".join(parts) if parts else "changelog event"

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
    def session_store(self) -> ExternalSessionStore:
        """Expose session store for testing and introspection."""
        return self._session_store

    @property
    def active_agent_count(self) -> int:
        """Number of agents currently running a spawned process."""
        return len(self._active_spawns)

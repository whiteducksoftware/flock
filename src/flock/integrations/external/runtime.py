"""ExternalAgentRuntime — structural typing protocol for agent adapters.

Any object that implements spawn / monitor / terminate can serve as an
external agent runtime.  The protocol is intentionally minimal so that
adapters for Claude Code CLI, Codex, custom Docker runners, etc. share
a single contract.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from flock.integrations.external.models import AgentOutcome, SpawnConfig, SpawnResult


@runtime_checkable
class ExternalAgentRuntime(Protocol):
    """Protocol that external agent adapters must satisfy.

    Lifecycle:
        1. spawn()     — launch the process, return a handle
        2. monitor()   — await completion, return the outcome
        3. terminate() — force-kill a running process (cleanup / timeout)
    """

    async def spawn(self, config: SpawnConfig) -> SpawnResult:
        """Launch an external agent process.

        Args:
            config: Fully resolved spawn configuration.

        Returns:
            A SpawnResult handle used by monitor() and terminate().
        """
        ...

    async def monitor(self, result: SpawnResult) -> AgentOutcome:
        """Wait for the spawned process to finish and collect its output.

        Args:
            result: Handle from a prior spawn() call.

        Returns:
            AgentOutcome describing success/failure and captured stdio.
        """
        ...

    async def terminate(self, result: SpawnResult) -> None:
        """Forcibly stop a running process.

        Implementations should attempt SIGTERM first, then SIGKILL after a
        short grace period.

        Args:
            result: Handle from a prior spawn() call.
        """
        ...

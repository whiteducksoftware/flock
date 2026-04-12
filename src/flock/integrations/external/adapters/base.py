"""BaseExternalRuntime — shared subprocess lifecycle for CLI agent adapters.

Extracts the common env-building, output-reading, and process-termination
logic that ``ClaudeCodeRuntime`` and ``CodexRuntime`` both need.  Concrete
adapters subclass this and provide their own ``spawn()``, ``monitor()``,
and ``_build_args()`` implementations.
"""

from __future__ import annotations

import asyncio
import logging
import os

from flock.integrations.external.models import SpawnResult

logger = logging.getLogger(__name__)

# Default grace period between SIGTERM and SIGKILL.
_TERMINATE_GRACE_SECONDS: float = 30.0

# ---------------------------------------------------------------------------
# Environment allowlist — only these vars propagate to the subprocess.
# ---------------------------------------------------------------------------
_SAFE_ENV_VARS: frozenset[str] = frozenset({
    "PATH", "HOME", "USER", "LANG", "LC_ALL", "LC_CTYPE",
    "TERM", "TMPDIR", "TMP", "TEMP",
    "SHELL", "LOGNAME", "HOSTNAME",
    # Flock-specific (injected by scheduler)
    "FLOCK_API_TOKEN", "FLOCK_API_URL",
})


class BaseExternalRuntime:
    """Common subprocess lifecycle shared by all CLI agent adapters.

    Subclasses must define:
        _ADAPTER_REQUIRED_VARS  — frozenset of env var names the CLI needs
        spawn()                 — launch the CLI process
        monitor()               — read output and parse results
        _build_args()           — construct the CLI argument list
    """

    # Subclasses override this with their adapter-specific keys.
    _ADAPTER_REQUIRED_VARS: frozenset[str] = frozenset()

    # ------------------------------------------------------------------
    # _build_env
    # ------------------------------------------------------------------

    def _build_env(
        self,
        config: object,
        *,
        additional_env: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Build a minimal environment for the subprocess.

        Only allowlisted variables from the parent process are propagated
        to prevent leaking secrets (DATABASE_URL, other API keys, etc.)
        to untrusted external agent subprocesses.  Explicit overrides from
        ``config.env_vars`` and ``additional_env`` are always applied on top.

        Parameters
        ----------
        config:
            A ``SpawnConfig`` (or anything with ``.env_vars``).
        additional_env:
            Extra env vars from the adapter-specific config (e.g.
            ``ClaudeCodeConfig.additional_env``).
        """
        # Start with safe subset of parent environment
        env = {k: v for k, v in os.environ.items() if k in _SAFE_ENV_VARS}
        # Add adapter-specific required vars
        for key in self._ADAPTER_REQUIRED_VARS:
            if key in os.environ:
                env[key] = os.environ[key]
        # Merge config env vars (explicit overrides)
        env.update(config.env_vars)  # type: ignore[attr-defined]
        # Merge additional env
        if additional_env:
            env.update(additional_env)
        return env

    # ------------------------------------------------------------------
    # _read_output
    # ------------------------------------------------------------------

    @staticmethod
    async def _read_output(
        proc: asyncio.subprocess.Process,
    ) -> tuple[bytes, bytes]:
        """Read stdout and stderr from a process concurrently."""
        assert proc.stdout is not None
        assert proc.stderr is not None

        stdout_bytes, stderr_bytes = await asyncio.gather(
            proc.stdout.read(),
            proc.stderr.read(),
        )
        await proc.wait()
        return stdout_bytes, stderr_bytes

    # ------------------------------------------------------------------
    # terminate
    # ------------------------------------------------------------------

    async def terminate(self, result: SpawnResult) -> None:
        """Stop a running process.

        Sends SIGTERM, waits up to ``_TERMINATE_GRACE_SECONDS``, then
        SIGKILL if the process hasn't exited.
        """
        proc = result.process

        if proc.returncode is not None:
            # Already exited.
            return

        try:
            proc.terminate()  # SIGTERM
        except ProcessLookupError:
            return  # Already gone.

        try:
            await asyncio.wait_for(proc.wait(), timeout=_TERMINATE_GRACE_SECONDS)
        except asyncio.TimeoutError:
            logger.warning(
                "%s.terminate: pid=%d did not exit after SIGTERM, "
                "sending SIGKILL",
                type(self).__name__,
                result.pid,
            )
            try:
                proc.kill()  # SIGKILL
            except ProcessLookupError:
                return
            await proc.wait()

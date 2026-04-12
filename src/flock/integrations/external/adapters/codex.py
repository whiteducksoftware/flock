"""CodexRuntime — ExternalAgentRuntime adapter for the OpenAI Codex CLI.

Spawns ``codex`` as a subprocess with ``--json --full-auto``, feeds the
prompt via stdin, and parses the JSONL event stream output.  Supports
session resumption via ``codex exec resume <session_id>``.

Security: The prompt is ALWAYS passed through stdin, never interpolated
into CLI arguments, to prevent flag-injection attacks.

CLI invocation:
    New:    codex exec --json --full-auto --skip-git-repo-check -C <cwd>
    Resume: codex exec resume <session_id> <prompt>  (prompt also on stdin)
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from flock.integrations.external.adapters.base import (
    BaseExternalRuntime,
    _TERMINATE_GRACE_SECONDS,  # noqa: F401 — re-exported for test patching
)
from flock.integrations.external.models import AgentOutcome, SpawnConfig, SpawnResult

logger = logging.getLogger(__name__)


@dataclass
class CodexConfig:
    """Optional knobs for the Codex CLI invocation.

    Attributes:
        additional_env: Extra environment variables merged into the process env.
            ``OPENAI_API_KEY`` is typically set here or already in the
            environment.
    """

    additional_env: dict[str, str] = field(default_factory=dict)


class CodexRuntime(BaseExternalRuntime):
    """ExternalAgentRuntime implementation for the OpenAI Codex CLI.

    Lifecycle:
        spawn()     — start ``codex`` subprocess, write prompt to stdin
        monitor()   — read stdout/stderr, wait for exit, parse JSONL output
        terminate() — SIGTERM then SIGKILL after grace period

    The Codex CLI with ``--json`` emits a JSONL event stream on stdout.
    We parse ``thread.started`` for the session_id and ``turn.completed``
    for the result text.  If parsing fails, raw stdout is returned as a
    graceful degradation.
    """

    _ADAPTER_REQUIRED_VARS: frozenset[str] = frozenset({
        "OPENAI_API_KEY",
    })

    def __init__(self, config: CodexConfig | None = None) -> None:
        self._config = config or CodexConfig()

    # ------------------------------------------------------------------
    # spawn
    # ------------------------------------------------------------------

    async def spawn(self, config: SpawnConfig) -> SpawnResult:
        """Launch a Codex CLI process.

        The prompt is written to stdin.  The process is started but output
        is NOT read here — call :meth:`monitor` for that.

        Raises:
            FileNotFoundError: If the ``codex`` binary is not on PATH.
            OSError: For other subprocess creation failures.
        """
        args = self._build_args(config)
        env = self._build_env(config)
        prompt_bytes = config.prompt.encode("utf-8")

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(config.working_dir),
                env=env,
            )
        except FileNotFoundError:
            raise FileNotFoundError(
                "Codex CLI ('codex') not found. "
                "Install it with: npm install -g @openai/codex"
            ) from None

        # Write prompt to stdin and close the stream so the CLI can
        # proceed.  We do NOT await output here — that's monitor()'s job.
        if proc.stdin is None:
            raise RuntimeError("Subprocess stdin not available")
        try:
            proc.stdin.write(prompt_bytes)
            await proc.stdin.drain()
            proc.stdin.close()
            await proc.stdin.wait_closed()
        except (BrokenPipeError, OSError, ConnectionResetError) as exc:
            # Subprocess exited early — kill and raise
            proc.kill()
            await proc.wait()
            raise RuntimeError(
                f"Codex process exited before accepting input: {exc}"
            ) from exc

        session_id = config.session_id or "pending"

        logger.debug(
            "CodexRuntime.spawn: pid=%d, session_id=%s, cwd=%s",
            proc.pid,
            session_id,
            config.working_dir,
        )
        return SpawnResult(pid=proc.pid, session_id=session_id, process=proc)

    # ------------------------------------------------------------------
    # monitor
    # ------------------------------------------------------------------

    async def monitor(self, result: SpawnResult) -> AgentOutcome:
        """Wait for the Codex process to exit and parse its JSONL output.

        Parses the JSONL event stream for:
        - ``thread.started`` event to extract session_id
        - ``turn.completed`` event to extract the result text

        Falls back to raw stdout if JSONL parsing fails.
        """
        proc = result.process

        # Read all remaining output and wait for the process to exit.
        stdout_bytes, stderr_bytes = await self._read_output(proc)

        stdout_text = stdout_bytes.decode("utf-8", errors="replace")
        stderr_text = stderr_bytes.decode("utf-8", errors="replace")

        returncode = proc.returncode if proc.returncode is not None else -1
        success = returncode == 0

        # Parse JSONL output for session_id and result text.
        session_id = result.session_id
        parsed = _parse_codex_jsonl(stdout_text)
        if parsed is not None:
            if parsed.get("session_id"):
                session_id = parsed["session_id"]
            # Replace raw stdout with extracted result text if available.
            result_text = parsed.get("result_text")
            if result_text is not None:
                stdout_text = result_text

        logger.debug(
            "CodexRuntime.monitor: pid=%d, returncode=%d, session_id=%s",
            result.pid,
            returncode,
            session_id,
        )
        return AgentOutcome(
            success=success,
            returncode=returncode,
            stdout=stdout_text,
            stderr=stderr_text,
            session_id=session_id,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_args(self, config: SpawnConfig) -> list[str]:
        """Construct the CLI argument list."""
        if config.session_mode == "resume" and config.session_id:
            # Resume an existing session.
            return [
                "codex",
                "exec",
                "resume",
                config.session_id,
                config.prompt,
            ]

        # New session.
        return [
            "codex",
            "exec",
            "--json",
            "--full-auto",
            "--skip-git-repo-check",
            "-C", str(config.working_dir),
        ]

    def _build_env(self, config: SpawnConfig) -> dict[str, str]:
        """Build a minimal environment for the subprocess."""
        env = super()._build_env(
            config,
            additional_env=self._config.additional_env or None,
        )
        # Codex-specific default
        env["CODEX_QUIET_MODE"] = "1"
        return env


# ---------------------------------------------------------------------------
# JSONL output parsing
# ---------------------------------------------------------------------------


def _parse_codex_jsonl(stdout: str) -> dict[str, Any] | None:
    """Parse Codex JSONL event stream output.

    Codex with ``--json`` emits one JSON object per line.  We look for:
    - ``thread.started`` event with a ``thread_id`` or ``session_id``
    - ``turn.completed`` event with a ``result`` or ``message`` field

    Returns a dict with ``session_id`` and/or ``result_text`` keys,
    or ``None`` if no events could be parsed.
    """
    stdout = stdout.strip()
    if not stdout:
        return None

    session_id: str | None = None
    result_text: str | None = None

    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue

        if not isinstance(event, dict):
            continue

        event_type = event.get("type") or event.get("event")

        # Extract session_id from thread.started
        if event_type == "thread.started":
            session_id = (
                event.get("thread_id")
                or event.get("session_id")
                or event.get("id")
            )
            if isinstance(session_id, str):
                session_id = session_id
            else:
                session_id = str(session_id) if session_id is not None else None

        # Extract result text from turn.completed
        if event_type == "turn.completed":
            result_text = (
                event.get("result")
                or event.get("message")
                or event.get("text")
                or event.get("output")
            )
            if isinstance(result_text, list):
                # Handle content block arrays
                parts = []
                for block in result_text:
                    if isinstance(block, dict):
                        parts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        parts.append(block)
                result_text = "\n".join(parts)
            elif result_text is not None:
                result_text = str(result_text)

    # Build result
    parsed: dict[str, Any] = {}
    if session_id is not None:
        parsed["session_id"] = session_id
    if result_text is not None:
        parsed["result_text"] = result_text

    return parsed if parsed else None

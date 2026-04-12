"""ClaudeCodeRuntime — ExternalAgentRuntime adapter for the Claude Code CLI.

Spawns ``claude`` as a subprocess with ``--output-format json``, feeds the
prompt via stdin (``-p -``), and parses structured JSON output.  Supports
session resumption via ``--resume <session_id>``.

Security: The prompt is ALWAYS passed through stdin, never interpolated
into CLI arguments, to prevent flag-injection attacks.
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
class ClaudeCodeConfig:
    """Optional knobs for the Claude Code CLI invocation.

    These are merged into the SpawnConfig's env_vars / CLI args at spawn
    time.  All fields are optional — sensible defaults come from the CLI
    itself or the environment.
    """

    model: str | None = None
    max_turns: int | None = None
    max_budget_usd: float | None = None
    allowed_tools: list[str] = field(default_factory=list)
    additional_env: dict[str, str] = field(default_factory=dict)


class ClaudeCodeRuntime(BaseExternalRuntime):
    """ExternalAgentRuntime implementation for the Claude Code CLI.

    Lifecycle:
        spawn()     — start ``claude`` subprocess, write prompt to stdin
        monitor()   — read stdout/stderr, wait for exit, parse JSON output
        terminate() — SIGTERM then SIGKILL after grace period
    """

    _ADAPTER_REQUIRED_VARS: frozenset[str] = frozenset({
        "ANTHROPIC_API_KEY",
    })

    def __init__(self, config: ClaudeCodeConfig | None = None) -> None:
        self._config = config or ClaudeCodeConfig()

    # ------------------------------------------------------------------
    # spawn
    # ------------------------------------------------------------------

    async def spawn(self, config: SpawnConfig) -> SpawnResult:
        """Launch a Claude Code CLI process.

        The prompt is written to stdin (via ``-p -``).  The process is
        started but output is NOT read here — call :meth:`monitor` for
        that.

        Raises:
            FileNotFoundError: If the ``claude`` binary is not on PATH.
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
                "Claude Code CLI ('claude') not found. "
                "Install it with: npm install -g @anthropic-ai/claude-code"
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
                f"Claude Code process exited before accepting input: {exc}"
            ) from exc

        session_id = config.session_id or "pending"

        logger.debug(
            "ClaudeCodeRuntime.spawn: pid=%d, session_id=%s, cwd=%s",
            proc.pid,
            session_id,
            config.working_dir,
        )
        return SpawnResult(pid=proc.pid, session_id=session_id, process=proc)

    # ------------------------------------------------------------------
    # monitor
    # ------------------------------------------------------------------

    async def monitor(self, result: SpawnResult) -> AgentOutcome:
        """Wait for the Claude Code process to exit and parse its output.

        Reads stdout/stderr from the process, parses the JSON output to
        extract the result text and session_id.
        """
        proc = result.process

        # Read all remaining output and wait for the process to exit.
        stdout_bytes, stderr_bytes = await self._read_output(proc)

        stdout_text = stdout_bytes.decode("utf-8", errors="replace")
        stderr_text = stderr_bytes.decode("utf-8", errors="replace")

        returncode = proc.returncode if proc.returncode is not None else -1
        success = returncode == 0

        # Parse JSON output for session_id and result text.
        session_id = result.session_id
        parsed = self._parse_json_output(stdout_text)
        if parsed is not None:
            session_id = parsed.get("session_id", session_id)
            # Replace raw stdout with extracted result text if available.
            result_text = parsed.get("result_text")
            if result_text is not None:
                stdout_text = result_text

        logger.debug(
            "ClaudeCodeRuntime.monitor: pid=%d, returncode=%d, session_id=%s",
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
        args = [
            "claude",
            "--bare",
            "-p", "-",
            "--output-format", "json",
            "--dangerously-skip-permissions",
        ]

        # Session resume
        if config.session_id and config.session_mode == "resume":
            args.extend(["--resume", config.session_id])

        # Optional config knobs
        if self._config.model:
            args.extend(["--model", self._config.model])
        if self._config.max_turns is not None:
            args.extend(["--max-turns", str(self._config.max_turns)])

        return args

    def _build_env(self, config: SpawnConfig) -> dict[str, str]:
        """Build a minimal environment for the subprocess."""
        return super()._build_env(
            config,
            additional_env=self._config.additional_env or None,
        )

    @staticmethod
    def _parse_json_output(stdout: str) -> dict[str, Any] | None:
        """Attempt to parse Claude Code JSON output.

        Returns a dict with ``session_id`` and ``result_text`` keys if
        parsing succeeds, or ``None`` on failure (caller falls back to
        raw stdout).

        The Claude Code CLI ``--output-format json`` emits an object (or
        sometimes an array of content blocks).  We handle both shapes:

        - Top-level object with ``result`` or ``content`` field
        - Array of content blocks (we join text blocks)
        - ``session_id`` may be top-level or under ``metadata``
        """
        stdout = stdout.strip()
        if not stdout:
            return None

        try:
            data = json.loads(stdout)
        except (json.JSONDecodeError, ValueError):
            logger.debug("ClaudeCodeRuntime: JSON parse failed, using raw stdout")
            return None

        result_text: str | None = None
        session_id: str | None = None

        if isinstance(data, dict):
            # Try common field names for the response text.
            result_text = (
                data.get("result")
                or data.get("content")
                or data.get("text")
                or data.get("output")
            )
            # Handle content that's a list of blocks.
            if isinstance(result_text, list):
                result_text = "\n".join(
                    block.get("text", "") for block in result_text if isinstance(block, dict)
                )

            # Session ID: top-level or under metadata.
            session_id = data.get("session_id")
            if session_id is None:
                metadata = data.get("metadata")
                if isinstance(metadata, dict):
                    session_id = metadata.get("session_id")

        elif isinstance(data, list):
            # Array of content blocks.
            parts = []
            for block in data:
                if isinstance(block, dict):
                    text = block.get("text") or block.get("content") or ""
                    if text:
                        parts.append(str(text))
            result_text = "\n".join(parts) if parts else None

        parsed: dict[str, Any] = {}
        if result_text is not None:
            parsed["result_text"] = str(result_text)
        if session_id is not None:
            parsed["session_id"] = str(session_id)
        return parsed if parsed else None

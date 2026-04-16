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
    bare: bool = False
    """Use ``--bare`` mode (skips hooks, plugins, CLAUDE.md).

    **Warning:** bare mode also skips OAuth/keychain reads, so subscription
    auth won't work.  Set this to True only when ``ANTHROPIC_API_KEY`` is
    provided explicitly (e.g. in CI).  Default False uses the logged-in
    session's authentication.
    """


class ClaudeCodeRuntime(BaseExternalRuntime):
    """ExternalAgentRuntime implementation for the Claude Code CLI.

    Lifecycle:
        spawn()     — start ``claude`` subprocess, write prompt to stdin
        monitor()   — read stdout/stderr, wait for exit, parse JSON output
        terminate() — SIGTERM then SIGKILL after grace period
    """

    _ADAPTER_REQUIRED_VARS: frozenset[str] = frozenset({
        "ANTHROPIC_API_KEY",  # Optional — only needed when bare=True (CI mode)
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

        # Leave session_id unresolved (None) unless the caller supplied one;
        # monitor() will populate it from the parsed JSON.  A None value
        # prevents the engine from persisting an unresolved session.
        session_id = config.session_id

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
            "-p", "-",
            "--output-format", "json",
            "--dangerously-skip-permissions",
        ]

        # --bare skips hooks/plugins/CLAUDE.md for faster, deterministic
        # invocations (CI).  It also skips OAuth, so subscription auth
        # won't work — only ANTHROPIC_API_KEY.
        if self._config.bare:
            args.insert(1, "--bare")

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

        result_text: str | None = None
        session_id: str | None = None

        # Claude Code --output-format json emits either:
        # 1. A JSON array of event objects: [{...},{...},{...}]
        # 2. JSONL (one JSON object per line): {...}\n{...}\n{...}
        # Parse both: try array first, then fall back to line-by-line.
        events: list[dict[str, Any]] = []
        try:
            parsed_array = json.loads(stdout)
            if isinstance(parsed_array, list):
                events = [e for e in parsed_array if isinstance(e, dict)]
        except (json.JSONDecodeError, ValueError):
            pass

        if not events:
            for line in stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        events.append(obj)
                except (json.JSONDecodeError, ValueError):
                    continue

        for obj in events:
            # The "result" event has the final text and session_id
            if obj.get("type") == "result":
                result_text = result_text or obj.get("result")
                session_id = session_id or obj.get("session_id")
            # The "assistant" event has the message content
            elif obj.get("type") == "assistant":
                msg = obj.get("message", {})
                content = msg.get("content", [])
                if isinstance(content, list):
                    text_parts = [
                        block.get("text", "")
                        for block in content
                        if isinstance(block, dict) and block.get("type") == "text"
                    ]
                    if text_parts and result_text is None:
                        result_text = "\n".join(text_parts)
                session_id = session_id or obj.get("session_id")
            # system/init event also carries session_id
            elif obj.get("type") == "system":
                session_id = session_id or obj.get("session_id")

        # Fallback: try parsing as single JSON object (legacy format)
        if result_text is None:
            try:
                data = json.loads(stdout)
                if isinstance(data, dict):
                    result_text = (
                        data.get("result")
                        or data.get("content")
                        or data.get("text")
                    )
                    if isinstance(result_text, list):
                        result_text = "\n".join(
                            b.get("text", "") for b in result_text if isinstance(b, dict)
                        )
                    sid = data.get("session_id")
                    if sid is None:
                        meta = data.get("metadata")
                        if isinstance(meta, dict):
                            sid = meta.get("session_id")
                    session_id = session_id or sid
            except (json.JSONDecodeError, ValueError):
                pass

        if result_text is None and session_id is None:
            logger.debug("ClaudeCodeRuntime: no result parsed from output")
            return None

        parsed: dict[str, Any] = {}
        if result_text is not None:
            parsed["result_text"] = str(result_text)
        if session_id is not None:
            parsed["session_id"] = str(session_id)
        return parsed

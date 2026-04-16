"""Tests for CodexRuntime — ExternalAgentRuntime adapter for the Codex CLI.

Uses unittest.mock.AsyncMock and unittest.mock.patch to mock
asyncio.create_subprocess_exec so no real Codex CLI is needed.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from flock.integrations.external.adapters.codex import (
    CodexConfig,
    CodexRuntime,
    _parse_codex_jsonl,
)
from flock.integrations.external.models import SpawnConfig, SpawnResult
from flock.integrations.external.runtime import ExternalAgentRuntime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spawn_config(
    prompt: str = "Fix the bug in main.py",
    session_mode: str = "new",
    session_id: str | None = None,
    working_dir: Path | None = None,
    env_vars: dict[str, str] | None = None,
) -> SpawnConfig:
    return SpawnConfig(
        prompt=prompt,
        working_dir=working_dir or Path("/tmp/test-repo"),
        env_vars=env_vars or {},
        session_id=session_id,
        session_mode=session_mode,
    )


def _make_mock_process(
    pid: int = 42,
    returncode: int = 0,
    stdout: bytes = b"",
    stderr: bytes = b"",
) -> MagicMock:
    """Create a mock asyncio.subprocess.Process."""
    proc = MagicMock()
    proc.pid = pid
    proc.returncode = returncode

    # stdin mock
    stdin_mock = MagicMock()
    stdin_mock.write = MagicMock()
    stdin_mock.drain = AsyncMock()
    stdin_mock.close = MagicMock()
    stdin_mock.wait_closed = AsyncMock()
    proc.stdin = stdin_mock

    # stdout/stderr as async readers
    stdout_mock = MagicMock()
    stdout_mock.read = AsyncMock(return_value=stdout)
    proc.stdout = stdout_mock

    stderr_mock = MagicMock()
    stderr_mock.read = AsyncMock(return_value=stderr)
    proc.stderr = stderr_mock

    # wait / communicate
    proc.wait = AsyncMock(return_value=returncode)
    proc.communicate = AsyncMock(return_value=(stdout, stderr))

    # terminate / kill
    proc.terminate = MagicMock()
    proc.kill = MagicMock()

    return proc


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    def test_codex_runtime_satisfies_protocol(self) -> None:
        """CodexRuntime is recognized as an ExternalAgentRuntime."""
        runtime = CodexRuntime()
        assert isinstance(runtime, ExternalAgentRuntime)


# ---------------------------------------------------------------------------
# Happy path: spawn with new mode
# ---------------------------------------------------------------------------


class TestCodexSpawnNew:
    async def test_spawn_new_correct_cli_args(self) -> None:
        """New session spawn builds correct CLI args with --json --full-auto."""
        config = _make_spawn_config()
        proc = _make_mock_process(pid=123)

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            runtime = CodexRuntime()
            result = await runtime.spawn(config)

            # Verify CLI args
            call_args = asyncio.create_subprocess_exec.call_args
            args = call_args[0]  # positional args

            assert args[0] == "codex"
            assert args[1] == "exec"
            assert "--json" in args
            assert "--full-auto" in args
            assert "--skip-git-repo-check" in args
            assert "-C" in args
            idx = list(args).index("-C")
            assert args[idx + 1] == str(config.working_dir)

            # Verify result — session_id is None until monitor() parses one
            # out of the JSONL stream.
            assert result.pid == 123
            assert result.session_id is None

    async def test_spawn_new_writes_prompt_to_stdin(self) -> None:
        """Prompt is written to stdin, not passed as a CLI argument."""
        config = _make_spawn_config(prompt="Hello Codex")
        proc = _make_mock_process()

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            runtime = CodexRuntime()
            await runtime.spawn(config)

            proc.stdin.write.assert_called_once_with(b"Hello Codex")
            proc.stdin.close.assert_called_once()

    async def test_spawn_new_sets_codex_quiet_mode(self) -> None:
        """CODEX_QUIET_MODE=1 is always set in the environment."""
        config = _make_spawn_config()
        proc = _make_mock_process()

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)) as mock_exec:
            runtime = CodexRuntime()
            await runtime.spawn(config)

            call_kwargs = mock_exec.call_args[1]
            env = call_kwargs["env"]
            assert env["CODEX_QUIET_MODE"] == "1"

    async def test_spawn_new_merges_additional_env(self) -> None:
        """CodexConfig.additional_env is merged into the process environment."""
        config = _make_spawn_config(env_vars={"MY_VAR": "from_spawn"})
        proc = _make_mock_process()
        adapter_config = CodexConfig(additional_env={"EXTRA": "from_config"})

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)) as mock_exec:
            runtime = CodexRuntime(config=adapter_config)
            await runtime.spawn(config)

            call_kwargs = mock_exec.call_args[1]
            env = call_kwargs["env"]
            assert env["MY_VAR"] == "from_spawn"
            assert env["EXTRA"] == "from_config"
            assert env["CODEX_QUIET_MODE"] == "1"

    async def test_spawn_sets_cwd(self) -> None:
        """Working directory is set from SpawnConfig."""
        config = _make_spawn_config(working_dir=Path("/my/project"))
        proc = _make_mock_process()

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)) as mock_exec:
            runtime = CodexRuntime()
            await runtime.spawn(config)

            call_kwargs = mock_exec.call_args[1]
            assert call_kwargs["cwd"] == "/my/project"

    async def test_spawn_uses_pipe_for_stdin_stdout_stderr(self) -> None:
        """Process is created with PIPE for stdin, stdout, and stderr."""
        config = _make_spawn_config()
        proc = _make_mock_process()

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)) as mock_exec:
            runtime = CodexRuntime()
            await runtime.spawn(config)

            call_kwargs = mock_exec.call_args[1]
            assert call_kwargs["stdin"] == asyncio.subprocess.PIPE
            assert call_kwargs["stdout"] == asyncio.subprocess.PIPE
            assert call_kwargs["stderr"] == asyncio.subprocess.PIPE


# ---------------------------------------------------------------------------
# Happy path: spawn with resume mode
# ---------------------------------------------------------------------------


class TestCodexSpawnResume:
    async def test_spawn_resume_uses_resume_command(self) -> None:
        """Resume mode uses 'codex exec resume <session_id>' invocation.

        The JSONL / full-auto / -C flags MUST be preserved so that
        :meth:`monitor` can parse the event stream identically to a new
        session.  The prompt MUST stay out of argv to preserve the
        stdin-only security invariant.
        """
        config = _make_spawn_config(
            session_mode="resume",
            session_id="thread_abc123",
            prompt="Continue the work",
        )
        proc = _make_mock_process(pid=456)

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            runtime = CodexRuntime()
            result = await runtime.spawn(config)

            call_args = asyncio.create_subprocess_exec.call_args
            args = call_args[0]

            assert args[0] == "codex"
            assert args[1] == "exec"
            assert args[2] == "resume"
            assert args[3] == "thread_abc123"

            # JSONL + full-auto + cwd flags MUST be present so monitor()'s
            # parser path is identical to the new-session branch.
            assert "--json" in args
            assert "--full-auto" in args
            assert "--skip-git-repo-check" in args
            assert "-C" in args

            # The prompt must NEVER appear in argv (stdin-only invariant).
            assert "Continue the work" not in args

            # Prompt is still written to stdin.
            proc.stdin.write.assert_called_once_with(b"Continue the work")

            assert result.session_id == "thread_abc123"

    async def test_spawn_resume_without_session_id_falls_back_to_new(self) -> None:
        """Resume mode with no session_id builds new-session args."""
        config = _make_spawn_config(session_mode="resume", session_id=None)
        proc = _make_mock_process()

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            runtime = CodexRuntime()
            await runtime.spawn(config)

            call_args = asyncio.create_subprocess_exec.call_args
            args = call_args[0]

            # Should be the new-session invocation
            assert args[0] == "codex"
            assert args[1] == "exec"
            assert "--json" in args
            assert "--full-auto" in args


# ---------------------------------------------------------------------------
# Happy path: JSONL output parsing
# ---------------------------------------------------------------------------


class TestCodexJsonlParsing:
    async def test_monitor_parses_turn_completed(self) -> None:
        """Result text is extracted from turn.completed event."""
        jsonl = (
            '{"type": "thread.started", "thread_id": "thread_xyz"}\n'
            '{"type": "turn.completed", "result": "Bug fixed in main.py"}\n'
        )
        config = _make_spawn_config()
        proc = _make_mock_process(stdout=jsonl.encode())

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            runtime = CodexRuntime()
            result = await runtime.spawn(config)
            outcome = await runtime.monitor(result)

            assert outcome.success is True
            assert outcome.stdout == "Bug fixed in main.py"
            assert outcome.session_id == "thread_xyz"

    async def test_monitor_extracts_session_id_from_thread_started(self) -> None:
        """Session ID is captured from thread.started event."""
        jsonl = '{"type": "thread.started", "thread_id": "sess_unique_42"}\n'
        config = _make_spawn_config()
        proc = _make_mock_process(stdout=jsonl.encode())

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            runtime = CodexRuntime()
            result = await runtime.spawn(config)
            outcome = await runtime.monitor(result)

            assert outcome.session_id == "sess_unique_42"

    async def test_monitor_handles_session_id_field_name(self) -> None:
        """Supports session_id as an alternative to thread_id."""
        jsonl = '{"type": "thread.started", "session_id": "alt_sess_99"}\n'
        config = _make_spawn_config()
        proc = _make_mock_process(stdout=jsonl.encode())

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            runtime = CodexRuntime()
            result = await runtime.spawn(config)
            outcome = await runtime.monitor(result)

            assert outcome.session_id == "alt_sess_99"


# ---------------------------------------------------------------------------
# Edge case: JSONL schema change / graceful degradation
# ---------------------------------------------------------------------------


class TestCodexGracefulDegradation:
    async def test_unparseable_output_returns_raw_stdout(self) -> None:
        """If JSONL parsing fails entirely, raw stdout is returned."""
        raw_output = "Some unexpected plain text output\nwith multiple lines"
        config = _make_spawn_config()
        proc = _make_mock_process(stdout=raw_output.encode())

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            runtime = CodexRuntime()
            result = await runtime.spawn(config)
            outcome = await runtime.monitor(result)

            assert outcome.stdout == raw_output
            assert outcome.session_id is None  # no session extracted

    async def test_unknown_event_types_ignored(self) -> None:
        """Unknown event types are silently skipped during parsing."""
        jsonl = (
            '{"type": "system.init", "version": "2.0"}\n'
            '{"type": "tool.call", "tool": "bash"}\n'
            '{"type": "turn.completed", "result": "All good"}\n'
        )
        config = _make_spawn_config()
        proc = _make_mock_process(stdout=jsonl.encode())

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            runtime = CodexRuntime()
            result = await runtime.spawn(config)
            outcome = await runtime.monitor(result)

            assert outcome.stdout == "All good"

    async def test_mixed_valid_and_invalid_lines(self) -> None:
        """Mix of valid JSON and garbage lines: valid events still parsed."""
        jsonl = (
            "not json at all\n"
            '{"type": "thread.started", "thread_id": "t_mixed"}\n'
            "{broken json\n"
            '{"type": "turn.completed", "result": "Recovered result"}\n'
        )
        config = _make_spawn_config()
        proc = _make_mock_process(stdout=jsonl.encode())

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            runtime = CodexRuntime()
            result = await runtime.spawn(config)
            outcome = await runtime.monitor(result)

            assert outcome.session_id == "t_mixed"
            assert outcome.stdout == "Recovered result"

    async def test_empty_stdout(self) -> None:
        """Empty stdout produces raw empty output, not a crash."""
        config = _make_spawn_config()
        proc = _make_mock_process(stdout=b"")

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            runtime = CodexRuntime()
            result = await runtime.spawn(config)
            outcome = await runtime.monitor(result)

            assert outcome.stdout == ""
            assert outcome.session_id is None

    async def test_nonzero_returncode_is_failure(self) -> None:
        """Non-zero exit code results in success=False."""
        config = _make_spawn_config()
        proc = _make_mock_process(returncode=1, stderr=b"Error: rate limited")

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            runtime = CodexRuntime()
            result = await runtime.spawn(config)
            outcome = await runtime.monitor(result)

            assert outcome.success is False
            assert outcome.returncode == 1
            assert outcome.stderr == "Error: rate limited"

    async def test_result_as_content_block_array(self) -> None:
        """turn.completed with result as array of content blocks."""
        jsonl = (
            '{"type": "turn.completed", "result": [{"text": "Part 1"}, {"text": "Part 2"}]}\n'
        )
        config = _make_spawn_config()
        proc = _make_mock_process(stdout=jsonl.encode())

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=proc)):
            runtime = CodexRuntime()
            result = await runtime.spawn(config)
            outcome = await runtime.monitor(result)

            assert "Part 1" in outcome.stdout
            assert "Part 2" in outcome.stdout


# ---------------------------------------------------------------------------
# Error path: CLI not installed
# ---------------------------------------------------------------------------


class TestCodexCliNotInstalled:
    async def test_spawn_raises_file_not_found(self) -> None:
        """Missing codex CLI produces a clear FileNotFoundError message."""
        config = _make_spawn_config()

        with patch(
            "asyncio.create_subprocess_exec",
            AsyncMock(side_effect=FileNotFoundError("codex")),
        ):
            runtime = CodexRuntime()
            with pytest.raises(FileNotFoundError, match="Codex CLI.*not found"):
                await runtime.spawn(config)

    async def test_error_message_names_the_tool(self) -> None:
        """The error message specifically names 'codex' and installation info."""
        config = _make_spawn_config()

        with patch(
            "asyncio.create_subprocess_exec",
            AsyncMock(side_effect=FileNotFoundError("codex")),
        ):
            runtime = CodexRuntime()
            try:
                await runtime.spawn(config)
                pytest.fail("Expected FileNotFoundError")
            except FileNotFoundError as e:
                msg = str(e)
                assert "codex" in msg.lower()
                assert "npm install" in msg


# ---------------------------------------------------------------------------
# Terminate
# ---------------------------------------------------------------------------


class TestCodexTerminate:
    async def test_terminate_already_exited(self) -> None:
        """Terminate on already-exited process is a no-op."""
        proc = _make_mock_process(returncode=0)
        result = SpawnResult(pid=1, session_id="s1", process=proc)

        runtime = CodexRuntime()
        await runtime.terminate(result)

        proc.terminate.assert_not_called()
        proc.kill.assert_not_called()

    async def test_terminate_sends_sigterm(self) -> None:
        """Terminate sends SIGTERM and waits for exit."""
        proc = _make_mock_process()
        proc.returncode = None  # Still running
        proc.wait = AsyncMock(return_value=0)
        result = SpawnResult(pid=2, session_id="s2", process=proc)

        runtime = CodexRuntime()
        await runtime.terminate(result)

        proc.terminate.assert_called_once()

    async def test_terminate_escalates_to_sigkill_on_timeout(self) -> None:
        """SIGKILL sent when process does not exit after SIGTERM grace period."""
        proc = _make_mock_process()
        proc.returncode = None

        # First wait_for times out, second (after kill) succeeds.
        call_count = 0

        async def side_effect_wait(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise asyncio.TimeoutError()
            return 0

        proc.wait = AsyncMock(side_effect=side_effect_wait)

        result = SpawnResult(pid=3, session_id="s3", process=proc)

        # Patch _TERMINATE_GRACE_SECONDS to a tiny value for fast test
        with patch(
            "flock.integrations.external.adapters.base._TERMINATE_GRACE_SECONDS",
            0.01,
        ):
            runtime = CodexRuntime()
            await runtime.terminate(result)

        proc.terminate.assert_called_once()
        proc.kill.assert_called_once()


# ---------------------------------------------------------------------------
# Unit tests for _parse_codex_jsonl
# ---------------------------------------------------------------------------


class TestParseCodexJsonl:
    def test_empty_string(self) -> None:
        assert _parse_codex_jsonl("") is None

    def test_whitespace_only(self) -> None:
        assert _parse_codex_jsonl("   \n\n  ") is None

    def test_thread_started_only(self) -> None:
        result = _parse_codex_jsonl('{"type": "thread.started", "thread_id": "t1"}')
        assert result is not None
        assert result["session_id"] == "t1"
        assert "result_text" not in result

    def test_turn_completed_only(self) -> None:
        result = _parse_codex_jsonl('{"type": "turn.completed", "result": "done"}')
        assert result is not None
        assert result["result_text"] == "done"
        assert "session_id" not in result

    def test_both_events(self) -> None:
        jsonl = (
            '{"type": "thread.started", "thread_id": "t2"}\n'
            '{"type": "turn.completed", "result": "finished"}\n'
        )
        result = _parse_codex_jsonl(jsonl)
        assert result is not None
        assert result["session_id"] == "t2"
        assert result["result_text"] == "finished"

    def test_no_parseable_events(self) -> None:
        result = _parse_codex_jsonl("plain text\nno json here")
        assert result is None

    def test_event_field_as_type(self) -> None:
        """Supports 'event' field as alternative to 'type'."""
        result = _parse_codex_jsonl('{"event": "turn.completed", "result": "ok"}')
        assert result is not None
        assert result["result_text"] == "ok"

    def test_message_as_result_field(self) -> None:
        """Supports 'message' field as alternative to 'result'."""
        result = _parse_codex_jsonl('{"type": "turn.completed", "message": "hello"}')
        assert result is not None
        assert result["result_text"] == "hello"

    def test_id_as_session_field(self) -> None:
        """Supports 'id' field as fallback for session_id."""
        result = _parse_codex_jsonl('{"type": "thread.started", "id": "fallback_id"}')
        assert result is not None
        assert result["session_id"] == "fallback_id"

    def test_content_block_array(self) -> None:
        """Result as array of content blocks is joined."""
        jsonl = '{"type": "turn.completed", "result": [{"text": "A"}, {"text": "B"}]}'
        result = _parse_codex_jsonl(jsonl)
        assert result is not None
        assert "A" in result["result_text"]
        assert "B" in result["result_text"]

    def test_non_dict_line_skipped(self) -> None:
        """Lines that parse to non-dict JSON are skipped."""
        jsonl = '42\n"just a string"\n{"type": "turn.completed", "result": "ok"}'
        result = _parse_codex_jsonl(jsonl)
        assert result is not None
        assert result["result_text"] == "ok"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestCodexConfig:
    def test_default_config(self) -> None:
        config = CodexConfig()
        assert config.additional_env == {}

    def test_custom_additional_env(self) -> None:
        config = CodexConfig(additional_env={"OPENAI_API_KEY": "sk-test"})
        assert config.additional_env["OPENAI_API_KEY"] == "sk-test"

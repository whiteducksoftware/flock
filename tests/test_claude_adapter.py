"""Tests for ClaudeCodeRuntime — the Claude Code CLI adapter.

All tests mock ``asyncio.create_subprocess_exec`` so no actual ``claude``
process is spawned.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from flock.integrations.external.adapters.claude_code import (
    ClaudeCodeConfig,
    ClaudeCodeRuntime,
)
from flock.integrations.external.models import SpawnConfig, SpawnResult
from flock.integrations.external.runtime import ExternalAgentRuntime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_spawn_config(
    prompt: str = "Hello, Claude!",
    session_id: str | None = None,
    session_mode: str = "new",
    timeout: float = 60.0,
    env_vars: dict[str, str] | None = None,
    working_dir: Path | None = None,
) -> SpawnConfig:
    return SpawnConfig(
        prompt=prompt,
        working_dir=working_dir or Path("/tmp/test-workspace"),
        env_vars=env_vars or {},
        session_id=session_id,
        session_mode=session_mode,
        timeout=timeout,
    )


def _make_fake_process(
    pid: int = 42,
    returncode: int = 0,
    stdout: bytes = b"",
    stderr: bytes = b"",
) -> MagicMock:
    """Create a mock asyncio.subprocess.Process."""
    proc = MagicMock()
    proc.pid = pid
    proc.returncode = None  # Not exited yet at spawn time.

    # stdin mock
    stdin = MagicMock()
    stdin.write = MagicMock()
    stdin.drain = AsyncMock()
    stdin.close = MagicMock()
    stdin.wait_closed = AsyncMock()
    proc.stdin = stdin

    # stdout/stderr as async stream readers
    stdout_reader = AsyncMock()
    stdout_reader.read = AsyncMock(return_value=stdout)
    proc.stdout = stdout_reader

    stderr_reader = AsyncMock()
    stderr_reader.read = AsyncMock(return_value=stderr)
    proc.stderr = stderr_reader

    # wait() sets returncode and returns it
    async def fake_wait():
        proc.returncode = returncode
        return returncode

    proc.wait = AsyncMock(side_effect=fake_wait)

    # terminate / kill
    proc.terminate = MagicMock()
    proc.kill = MagicMock()

    return proc


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    def test_satisfies_external_agent_runtime_protocol(self) -> None:
        """ClaudeCodeRuntime implements ExternalAgentRuntime."""
        runtime = ClaudeCodeRuntime()
        assert isinstance(runtime, ExternalAgentRuntime)


# ---------------------------------------------------------------------------
# ClaudeCodeConfig
# ---------------------------------------------------------------------------


class TestClaudeCodeConfig:
    def test_defaults(self) -> None:
        cfg = ClaudeCodeConfig()
        assert cfg.model is None
        assert cfg.max_turns is None
        assert cfg.max_budget_usd is None
        assert cfg.allowed_tools == []
        assert cfg.additional_env == {}

    def test_custom_values(self) -> None:
        cfg = ClaudeCodeConfig(
            model="claude-sonnet-4-20250514",
            max_turns=10,
            max_budget_usd=5.0,
            allowed_tools=["Bash", "Read"],
            additional_env={"MY_VAR": "val"},
        )
        assert cfg.model == "claude-sonnet-4-20250514"
        assert cfg.max_turns == 10
        assert cfg.max_budget_usd == 5.0
        assert cfg.allowed_tools == ["Bash", "Read"]
        assert cfg.additional_env == {"MY_VAR": "val"}


# ---------------------------------------------------------------------------
# Spawn tests
# ---------------------------------------------------------------------------


class TestSpawn:
    @pytest.mark.asyncio
    async def test_happy_path_new_mode(self) -> None:
        """Spawn with session_mode='new' produces correct CLI args (no --resume)."""
        fake_proc = _make_fake_process(pid=123)
        runtime = ClaudeCodeRuntime()
        config = _make_spawn_config()

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=fake_proc)) as mock_exec:
            result = await runtime.spawn(config)

            # Verify subprocess was created with correct args
            call_args = mock_exec.call_args
            positional = call_args[0]
            assert positional[0] == "claude"
            assert "--bare" not in positional  # bare=False by default (subscription auth)
            assert "-p" in positional
            assert "-" in positional
            assert "--output-format" in positional
            assert "json" in positional
            assert "--dangerously-skip-permissions" in positional
            assert "--resume" not in positional

            # Verify cwd
            assert call_args[1]["cwd"] == str(Path("/tmp/test-workspace"))

            # Verify prompt was written to stdin
            fake_proc.stdin.write.assert_called_once_with(b"Hello, Claude!")
            fake_proc.stdin.drain.assert_awaited_once()
            fake_proc.stdin.close.assert_called_once()
            fake_proc.stdin.wait_closed.assert_awaited_once()

        # Verify SpawnResult — session_id is None until monitor() extracts one.
        assert result.pid == 123
        assert result.session_id is None
        assert result.process is fake_proc

    @pytest.mark.asyncio
    async def test_resume_mode_with_session_id(self) -> None:
        """Spawn with session_mode='resume' and session_id includes --resume flag."""
        fake_proc = _make_fake_process(pid=456)
        runtime = ClaudeCodeRuntime()
        config = _make_spawn_config(
            session_id="sess-abc123",
            session_mode="resume",
        )

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=fake_proc)) as mock_exec:
            result = await runtime.spawn(config)

            positional = mock_exec.call_args[0]
            assert "--resume" in positional
            resume_idx = list(positional).index("--resume")
            assert positional[resume_idx + 1] == "sess-abc123"

        assert result.session_id == "sess-abc123"

    @pytest.mark.asyncio
    async def test_new_mode_with_session_id_no_resume_flag(self) -> None:
        """session_mode='new' with a session_id does NOT add --resume."""
        fake_proc = _make_fake_process()
        runtime = ClaudeCodeRuntime()
        config = _make_spawn_config(
            session_id="sess-xyz",
            session_mode="new",
        )

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=fake_proc)) as mock_exec:
            await runtime.spawn(config)
            positional = mock_exec.call_args[0]
            assert "--resume" not in positional

    @pytest.mark.asyncio
    async def test_custom_config_adds_model_and_max_turns(self) -> None:
        """ClaudeCodeConfig model and max_turns are passed as CLI args."""
        fake_proc = _make_fake_process()
        cc_config = ClaudeCodeConfig(model="claude-sonnet-4-20250514", max_turns=5)
        runtime = ClaudeCodeRuntime(config=cc_config)
        config = _make_spawn_config()

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=fake_proc)) as mock_exec:
            await runtime.spawn(config)
            positional = mock_exec.call_args[0]
            assert "--model" in positional
            model_idx = list(positional).index("--model")
            assert positional[model_idx + 1] == "claude-sonnet-4-20250514"
            assert "--max-turns" in positional
            mt_idx = list(positional).index("--max-turns")
            assert positional[mt_idx + 1] == "5"

    @pytest.mark.asyncio
    async def test_env_vars_merged(self) -> None:
        """SpawnConfig env_vars and ClaudeCodeConfig additional_env are merged."""
        fake_proc = _make_fake_process()
        cc_config = ClaudeCodeConfig(additional_env={"ADAPTER_VAR": "from_adapter"})
        runtime = ClaudeCodeRuntime(config=cc_config)
        config = _make_spawn_config(env_vars={"FLOCK_API_TOKEN": "tok123"})

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=fake_proc)) as mock_exec:
            await runtime.spawn(config)
            env = mock_exec.call_args[1]["env"]
            assert env["FLOCK_API_TOKEN"] == "tok123"
            assert env["ADAPTER_VAR"] == "from_adapter"
            # OS env should be in there too
            assert "PATH" in env

    @pytest.mark.asyncio
    async def test_claude_not_installed_raises_clear_error(self) -> None:
        """FileNotFoundError from subprocess creation gives a helpful message."""
        runtime = ClaudeCodeRuntime()
        config = _make_spawn_config()

        with patch(
            "asyncio.create_subprocess_exec",
            AsyncMock(side_effect=FileNotFoundError("No such file")),
        ):
            with pytest.raises(FileNotFoundError, match="Claude Code CLI.*not found"):
                await runtime.spawn(config)


# ---------------------------------------------------------------------------
# Monitor tests
# ---------------------------------------------------------------------------


class TestMonitor:
    @pytest.mark.asyncio
    async def test_happy_path_json_output(self) -> None:
        """Monitor parses JSON output with result and session_id."""
        json_output = json.dumps({
            "result": "Here is my analysis of the bug.",
            "session_id": "sess-new-123",
        })
        fake_proc = _make_fake_process(
            pid=10,
            returncode=0,
            stdout=json_output.encode(),
        )
        # Set returncode to None initially (not yet exited)
        fake_proc.returncode = None

        runtime = ClaudeCodeRuntime()
        spawn_result = SpawnResult(pid=10, session_id=None, process=fake_proc)

        outcome = await runtime.monitor(spawn_result)

        assert outcome.success is True
        assert outcome.returncode == 0
        assert outcome.stdout == "Here is my analysis of the bug."
        assert outcome.session_id == "sess-new-123"

    @pytest.mark.asyncio
    async def test_json_output_with_content_field(self) -> None:
        """Monitor handles 'content' field as alternative to 'result'."""
        json_output = json.dumps({
            "content": "Response via content field.",
            "metadata": {"session_id": "sess-meta-456"},
        })
        fake_proc = _make_fake_process(
            returncode=0,
            stdout=json_output.encode(),
        )
        fake_proc.returncode = None

        runtime = ClaudeCodeRuntime()
        spawn_result = SpawnResult(pid=10, session_id=None, process=fake_proc)

        outcome = await runtime.monitor(spawn_result)
        assert outcome.success is True
        assert outcome.stdout == "Response via content field."
        assert outcome.session_id == "sess-meta-456"

    @pytest.mark.asyncio
    async def test_json_output_with_content_blocks(self) -> None:
        """Monitor handles content as a list of text blocks."""
        json_output = json.dumps({
            "result": [
                {"type": "text", "text": "First block."},
                {"type": "text", "text": "Second block."},
            ],
            "session_id": "sess-blocks",
        })
        fake_proc = _make_fake_process(
            returncode=0,
            stdout=json_output.encode(),
        )
        fake_proc.returncode = None

        runtime = ClaudeCodeRuntime()
        spawn_result = SpawnResult(pid=10, session_id=None, process=fake_proc)

        outcome = await runtime.monitor(spawn_result)
        assert outcome.success is True
        assert "First block." in outcome.stdout
        assert "Second block." in outcome.stdout
        assert outcome.session_id == "sess-blocks"

    @pytest.mark.asyncio
    async def test_non_zero_exit_code(self) -> None:
        """Non-zero return code produces success=False with stderr captured."""
        fake_proc = _make_fake_process(
            returncode=1,
            stdout=b"",
            stderr=b"Error: something went wrong",
        )
        fake_proc.returncode = None

        runtime = ClaudeCodeRuntime()
        spawn_result = SpawnResult(pid=10, session_id=None, process=fake_proc)

        outcome = await runtime.monitor(spawn_result)
        assert outcome.success is False
        assert outcome.returncode == 1
        assert outcome.stderr == "Error: something went wrong"

    @pytest.mark.asyncio
    async def test_malformed_json_falls_back_to_raw_stdout(self) -> None:
        """If JSON parsing fails, raw stdout is used as the result."""
        raw_output = b"This is not JSON, just plain text output."
        fake_proc = _make_fake_process(
            returncode=0,
            stdout=raw_output,
        )
        fake_proc.returncode = None

        runtime = ClaudeCodeRuntime()
        spawn_result = SpawnResult(pid=10, session_id="sess-orig", process=fake_proc)

        outcome = await runtime.monitor(spawn_result)
        assert outcome.success is True
        assert outcome.stdout == "This is not JSON, just plain text output."
        # Session ID should remain from the SpawnResult.
        assert outcome.session_id == "sess-orig"

    @pytest.mark.asyncio
    async def test_empty_stdout(self) -> None:
        """Empty stdout is handled gracefully."""
        fake_proc = _make_fake_process(returncode=0, stdout=b"")
        fake_proc.returncode = None

        runtime = ClaudeCodeRuntime()
        spawn_result = SpawnResult(pid=10, session_id="sess-empty", process=fake_proc)

        outcome = await runtime.monitor(spawn_result)
        assert outcome.success is True
        assert outcome.stdout == ""
        assert outcome.session_id == "sess-empty"

    @pytest.mark.asyncio
    async def test_json_array_output(self) -> None:
        """Monitor handles JSON array of content blocks."""
        json_output = json.dumps([
            {"text": "Block A"},
            {"content": "Block B"},
        ])
        fake_proc = _make_fake_process(
            returncode=0,
            stdout=json_output.encode(),
        )
        fake_proc.returncode = None

        runtime = ClaudeCodeRuntime()
        spawn_result = SpawnResult(pid=10, session_id=None, process=fake_proc)

        outcome = await runtime.monitor(spawn_result)
        assert outcome.success is True
        assert "Block A" in outcome.stdout
        assert "Block B" in outcome.stdout


# ---------------------------------------------------------------------------
# Terminate tests
# ---------------------------------------------------------------------------


class TestTerminate:
    @pytest.mark.asyncio
    async def test_terminate_sends_sigterm_then_waits(self) -> None:
        """Terminate sends SIGTERM and waits for exit."""
        fake_proc = _make_fake_process(returncode=0)
        fake_proc.returncode = None  # Still running

        runtime = ClaudeCodeRuntime()
        spawn_result = SpawnResult(pid=10, session_id="s", process=fake_proc)

        await runtime.terminate(spawn_result)

        fake_proc.terminate.assert_called_once()
        fake_proc.wait.assert_awaited()

    @pytest.mark.asyncio
    async def test_terminate_sigkill_on_timeout(self) -> None:
        """If SIGTERM doesn't work within grace period, SIGKILL is sent."""
        fake_proc = _make_fake_process()
        fake_proc.returncode = None

        # Make wait() time out on first call (SIGTERM grace), succeed on second (after SIGKILL).
        call_count = 0

        async def flaky_wait():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # Simulate timeout — asyncio.wait_for will raise TimeoutError
                await asyncio.sleep(999)
            fake_proc.returncode = -9
            return -9

        fake_proc.wait = AsyncMock(side_effect=flaky_wait)

        runtime = ClaudeCodeRuntime()
        spawn_result = SpawnResult(pid=10, session_id="s", process=fake_proc)

        # Patch the grace period to something tiny for test speed.
        with patch(
            "flock.integrations.external.adapters.base._TERMINATE_GRACE_SECONDS",
            0.1,
        ):
            await runtime.terminate(spawn_result)

        fake_proc.terminate.assert_called_once()
        fake_proc.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_terminate_already_exited(self) -> None:
        """Terminate on an already-exited process is a no-op."""
        fake_proc = _make_fake_process(returncode=0)
        # Process already exited — returncode is set.
        fake_proc.returncode = 0

        runtime = ClaudeCodeRuntime()
        spawn_result = SpawnResult(pid=10, session_id="s", process=fake_proc)

        await runtime.terminate(spawn_result)

        fake_proc.terminate.assert_not_called()
        fake_proc.kill.assert_not_called()

    @pytest.mark.asyncio
    async def test_terminate_process_already_gone(self) -> None:
        """ProcessLookupError from terminate() is handled gracefully."""
        fake_proc = _make_fake_process()
        fake_proc.returncode = None
        fake_proc.terminate = MagicMock(side_effect=ProcessLookupError)

        runtime = ClaudeCodeRuntime()
        spawn_result = SpawnResult(pid=10, session_id="s", process=fake_proc)

        # Should not raise.
        await runtime.terminate(spawn_result)


# ---------------------------------------------------------------------------
# Timeout scenario (spawn + monitor with timeout)
# ---------------------------------------------------------------------------


class TestTimeoutScenario:
    @pytest.mark.asyncio
    async def test_monitor_can_be_timed_out_by_caller(self) -> None:
        """Demonstrates that the caller can wrap monitor() in wait_for for timeout."""
        fake_proc = _make_fake_process()
        fake_proc.returncode = None

        # Make stdout.read() hang forever to simulate a long-running process.
        async def hang_forever():
            await asyncio.sleep(999)
            return b""

        fake_proc.stdout.read = AsyncMock(side_effect=hang_forever)

        runtime = ClaudeCodeRuntime()
        spawn_result = SpawnResult(pid=10, session_id="s", process=fake_proc)

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(runtime.monitor(spawn_result), timeout=0.1)


# ---------------------------------------------------------------------------
# Cancellation / cleanup scenario
# ---------------------------------------------------------------------------


class TestCancellationCleanup:
    @pytest.mark.asyncio
    async def test_cancelled_monitor_does_not_leave_zombie(self) -> None:
        """CancelledError during monitor does not prevent process cleanup."""
        fake_proc = _make_fake_process()
        fake_proc.returncode = None

        # Make stdout.read() hang to simulate a long-running process.
        async def hang_forever():
            await asyncio.sleep(999)
            return b""

        fake_proc.stdout.read = AsyncMock(side_effect=hang_forever)

        runtime = ClaudeCodeRuntime()
        spawn_result = SpawnResult(pid=10, session_id="s", process=fake_proc)

        # Start monitor in a task and cancel it.
        task = asyncio.create_task(runtime.monitor(spawn_result))
        await asyncio.sleep(0.05)
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        # Caller should terminate after cancellation to avoid zombie.
        await runtime.terminate(spawn_result)
        fake_proc.terminate.assert_called_once()


# ---------------------------------------------------------------------------
# Full spawn → monitor lifecycle
# ---------------------------------------------------------------------------


class TestFullLifecycle:
    @pytest.mark.asyncio
    async def test_spawn_then_monitor_success(self) -> None:
        """Full lifecycle: spawn then monitor with successful JSON output."""
        json_output = json.dumps({
            "result": "Task completed successfully.",
            "session_id": "sess-lifecycle-1",
        })
        fake_proc = _make_fake_process(
            pid=77,
            returncode=0,
            stdout=json_output.encode(),
        )

        runtime = ClaudeCodeRuntime()
        config = _make_spawn_config(prompt="Analyze the codebase.")

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=fake_proc)):
            result = await runtime.spawn(config)

        assert result.pid == 77
        assert result.session_id is None

        # Now monitor — reset returncode to None as it would be in real life.
        fake_proc.returncode = None

        outcome = await runtime.monitor(result)

        assert outcome.success is True
        assert outcome.stdout == "Task completed successfully."
        assert outcome.session_id == "sess-lifecycle-1"

    @pytest.mark.asyncio
    async def test_spawn_then_monitor_failure(self) -> None:
        """Full lifecycle: spawn then monitor with non-zero exit."""
        fake_proc = _make_fake_process(
            pid=88,
            returncode=1,
            stderr=b"Error: rate limit exceeded",
        )

        runtime = ClaudeCodeRuntime()
        config = _make_spawn_config()

        with patch("asyncio.create_subprocess_exec", AsyncMock(return_value=fake_proc)):
            result = await runtime.spawn(config)

        fake_proc.returncode = None

        outcome = await runtime.monitor(result)
        assert outcome.success is False
        assert outcome.returncode == 1
        assert "rate limit exceeded" in outcome.stderr

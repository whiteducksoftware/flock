# Async MCP Tool Invocation Regression

## Summary
Parallel agents that should have invoked GitHub MCP tools were silently falling back to plain DTO generation whenever streaming output was suppressed. The foreground agent (with Rich or dashboard streaming enabled) still issued MCP calls, but every background run skipped tool execution entirely. This note captures the precise failure mode and the remediation applied so the dev team can review and propagate the fix.

## Symptoms Observed
- Reproduced with `examples/app-sketches/github-project-starter/main.py`: the `issue_creator` agent publishes five tasks in parallel, yet only one GitHub issue appears. The dashboard shows five DTO payloads with no `tool_use` metadata for four of the runs.
- Log output reveals `Execution error in issue_creator__github_tools__issue_write` for background workers, followed by the agent returning a synthesized DTO instead of calling GitHub.
- No warnings surface in the CLI because the failure occurs inside DSPy’s synchronous tool wrapper.

## Root Cause
- Background runs take the non-streaming execution path (`DSPyStreamingExecutor.execute_standard`).
- Prior to the fix, the executor always invoked `program(**payload)` (synchronous call).
- MCP integration wraps each tool as an **async** DSPy tool (see `src/flock/mcp/tool.py`), and DSPy’s `Tool.__call__` refuses to run coroutines unless `settings.allow_tool_async_sync_conversion` is toggled. As a result, every tool call raised `ValueError: You are calling __call__ on an async tool…`, which DSPy surfaced as “Execution error in …” and moved on without retrying.

## Remediation
1. **Async-first standard execution** (`src/flock/engines/dspy/streaming_executor.py:433`):
   - Detect whether the resolved DSPy program exposes an `acall` coroutine (DSPy’s async entry point) and await it when available.
   - Fall back to the synchronous call only when no coroutine exists, preserving compatibility with deterministic engines.
   - Import `asyncio` to perform the coroutine check explicitly (`asyncio.iscoroutinefunction`).
2. **Regressions tests** (`tests/test_dspy_engine.py:677`–`723`):
   - Existing semantic-fields test now asserts that we await `program.acall` when it exists.
   - Added `test_execute_standard_without_acall_falls_back_to_sync` to guarantee legacy sync-only programs still execute via `program(**payload)`.

## Validation Performed
- `pytest tests/test_dspy_engine.py`
- Manual reasoning: once standard execution awaits `acall`, DSPy routes tool invocations through `Tool.acall`, which directly awaits the async MCP wrapper, so every parallel agent can now call GitHub and other async MCP servers even when CLI streaming is disabled.

## Follow-Up / Recommendations
- Re-run the GitHub project starter example after pulling this patch to confirm five GitHub issues get created.
- Consider adding an integration test that exercises `flock.agent(...).max_concurrency(n)` with MCP tooling to catch similar regressions faster.

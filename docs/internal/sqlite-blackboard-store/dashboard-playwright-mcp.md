# Manual Dashboard Verification (playwright-mcp)

This checklist replaces the original automated Playwright suite. It uses the
`playwright-mcp` tool to exercise the historical dashboard manually.

## Prerequisites

- SQLite backend configuration available (see project README).
- `uv` CLI installed.
- `playwright-mcp` MCP extension enabled in the Codex CLI environment.

## Launch the Dashboard Edge-Case Scenario

```bash
uv run python examples/03-the-dashboard/02-dashboard-edge-cases.py
```

Wait for the following log lines:

- `[Dashboard] Production build completed`
- `Uvicorn running on http://127.0.0.1:8344`
- `[Dashboard] Browser launched successfully`

## Manual Verification Steps (playwright-mcp)

1. `mcp__playwright__browser_navigate(url="http://127.0.0.1:8344")`
   - Confirm Agent View renders all agents with idle status.
2. Close the Publish panel (`mcp__playwright__browser_click` with `Close publish panel`) and switch to **Blackboard View**.
3. Toggle the **Filters** panel and verify:
   - Correlation search, time range presets, multi-select filters, and saved preset controls appear.
4. Enter a sample correlation ID (e.g., `"abc123"`) to ensure filter pills update.
5. Re-open the Filters panel and ensure layout remains stable (no overlap between time-range buttons and fields).
6. Interact with the **Historical Blackboard** module (if enabled):
   - Trigger “Load Older” and capture behavior.
7. Capture a screenshot with `mcp__playwright__browser_take_screenshot(fullPage=True, ...)`.

## Expected Outcomes

- No React errors or ErrorBoundary screens.
- Filter controls render without overlapping.
- Manual interactions update filter pills and historical listings.
- WebSocket reconnect warnings are acceptable when the example shuts down.

Record findings in the Phase 3 validation notes before closing tasks.

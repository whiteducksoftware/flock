# `Flock` — Orchestrator

High-level orchestrator for managing and executing agents.

## Key Methods

- `add_agent(agent: FlockAgent)` — Register an agent with this Flock
- `add_server(server: FlockMCPServer)` — Register an MCP server
- `run(agent, input, context=None, box_result=True, ...)` — Run synchronously
- `run_async(agent, input, context=None, box_result=True, ...)` — Run async
- `run_batch(...)` / `run_batch_async(...)` — Batch execution
- `evaluate(...)` / `evaluate_async(...)` — Dataset evaluation
- `serve(...)` — Start REST API and optional UI
- `start_cli(...)` — Interactive CLI

## Behavior

- Uses composition helpers for execution, server management, evaluation, and web.
- Accepts `dict` inputs or Pydantic `BaseModel` instances (normalized to dict).
- Returns a `Box` by default (dot-accessible dict) or raw dict with `box_result=False`.

See `src/flock/core/flock.py` for details.

# Production Tool Set Switch Plan

## Context
- `FlockAgent.evaluate` currently always forwards `self.tools` to the evaluator; there is no concept of alternate tool bundles.
- Orchestrated runs (`Flock.run_async` → `workflow.activities.run_agent`) do not pass per-run options beyond the initial inputs stored in `FlockContext`.
- Web execution (`htmx_run_flock` → `run_current_flock_service`) and REST (`POST /run/flock`) both end up calling `Flock.run_async` with hard-coded parameters; HTML form/templates have no affordance for toggling tool usage.
- Serialization (`FlockAgent.to_dict/from_dict` and `FlockSerializer`) only know about a single tool list, so persisted YAML/JSON would currently lose any secondary tool configuration.

## Proposed Changes
1. **Agent Model & Serialization**
   - Introduce `production_tools: list[Callable] | None` on `FlockAgent` (excluded from serialization by default).
   - Update `FlockAgent.to_dict/from_dict` plus `FlockSerializer` to persist and restore both tool collections.
   - Add a helper such as `_resolve_tool_set(tool_set: Literal['dev','production'])` that returns the right list (dev list remains backward compatible default).

2. **Execution Flow**
   - Extend `FlockAgent.run/run_async/evaluate` signatures with `use_production_tools: bool = False` (keyword-only for clarity).
   - Store the chosen tool set on the stack (no shared mutation) and have `evaluate` call the helper to pick the correct tool bundle when invoking the evaluator.
   - Allow orchestrated runs to surface the choice via a new context variable (e.g. `FLOCK_TOOL_SET`) so that `workflow.activities.run_agent` can pass the flag when iterating agents.

3. **Flock Orchestrator**
   - Add the same boolean flag to `Flock.run/run_async` (and by extension `run_batch_async` if batch runs should support it), defaulting to dev tools.
   - When initializing the context (`initialize_context`) persist the selection, and ensure both local (`run_local_workflow`) and Temporal execution paths propagate it down to each agent invocation.

4. **API & Services**
   - Extend `FlockAPIRequest` with `use_production_tools: bool = False`, update the REST handler to forward the flag into `_execute_flock_run_task`.
   - Update `run_current_flock_service` and any other server-side helper that triggers `Flock.run_async` so the flag is threaded through.
   - Review/adjust other entry points (CLI helpers, schedulers, shared-run flows) for calls to `Flock.run_async` or `FlockAgent.run_async` to either expose the flag or explicitly opt into dev tools.

5. **Web UI**
   - Modify `partials/_execution_form.html` to add a checkbox labelled for production tools.
   - Add a confirmation modal/JS prompt before submitting when the checkbox is checked, ensuring HTMX submission includes the new form value.
   - Adjust `htmx_run_flock` to parse the form flag and pass it to `run_current_flock_service`; update the rendered form state as needed.

6. **Tool Registration Utilities**
   - Update helper factories (`FlockFactory.create_default_agent`, editor service for agent CRUD) to accept and wire `production_tools` if provided so UI/editor flows can manage both sets without manual patching.

## Validation Plan
- Unit-style exercise: new test or dummied script ensuring an agent with distinct dev/prod tool lists executes the correct callable based on the flag.
- Web layer smoke test: via HTMX form submission, confirm the checkbox toggles which tool is invoked (can be logged/printed during dev).
- REST test: `uv run flock --web` and POST to `/ui/api/run/flock` with `use_production_tools=true`, verify response indicates production tool path.
- Regression sweep: run `uv run pytest` (or a focused subset) to ensure serialization changes don’t break existing expectations.

## Open Considerations
- Confirm whether shared-run or batch workflows must surface the flag (requirement only mentions direct runs; plan assumes batch remains dev-only unless requested otherwise).
- Decide how to handle agents lacking a production tool list when the flag is enabled (proposed behaviour: fall back to dev tools, plus warning log).
- Ensure concurrency safety if multiple runs toggle tool sets concurrently—using per-call parameters instead of mutating agent state should avoid cross-talk.

## Implementation Summary

- **Agent Model Extensions**
  - Added a `production_tools` field and runtime helper `_get_runtime_tools`, enabling evaluators to receive either the default or production list without mutating agent state (`src/flock/core/flock_agent.py#L100`, `src/flock/core/flock_agent.py#L334`).
  - Serialization/deserialization updated to persist both tool collections, plus registration of production tools during flock export (`src/flock/core/flock_agent.py#L724`, `src/flock/core/flock_agent.py#L930`, `src/flock/core/serialization/flock_serializer.py#L262`).
  - `FlockFactory.create_default_agent` accepts an optional production list for UI/editor flows (`src/flock/core/flock_factory.py#L398`).

- **Execution Propagation**
  - `Flock.run/run_async` now accept `use_production_tools`; the flag is stored in context via `initialize_context` for downstream consumers (`src/flock/core/flock.py#L465`, `src/flock/core/context/context_manager.py#L14`).
  - Local and Temporal workflows read the shared context value before invoking each agent, ensuring chained agents share the same selection (`src/flock/workflow/activities.py#L68`, `src/flock/workflow/agent_execution_activity.py#L81`).

- **API & UI Integration**
  - REST model/endpoint extended with a `use_production_tools` boolean that is forwarded into flock execution (`src/flock/core/api/models.py#L17`, `src/flock/core/api/endpoints.py#L81`).
  - Web execution form gains a confirmation-backed checkbox; HTMX handler and service propagate the flag to `Flock.run_async` (`src/flock/webapp/templates/partials/_execution_form.html#L37`, `src/flock/webapp/app/api/execution.py#L145`, `src/flock/webapp/app/services/flock_service.py#L249`).

- **Testing & Example**
  - Added `examples/02-core-concepts/10-production-tools-toggle.py`, a compact integration script that drives the new flag through `Flock.run` and prints tool usage, validated via `uv run` with model `openai/gpt-4.1`.

- **Outcome**
  - Agents default to development tools, but a run-wide toggle can switch all agents in the context to their production tool set, falling back gracefully when unspecified. The web UI and REST API surface the new control, while serialization keeps both tool bundles intact for config handoff.

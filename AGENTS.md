Flock Agents — Onboarding Guide for Agents

Overview

- Purpose: Declarative LLM orchestration at scale. Flock lets you define agents by their inputs/outputs, wire them with routers and modules, run locally or via Temporal, expose them via a web UI/API, and serialize whole systems.
- Core pillars: Declarative agent signatures, pluggable components (Evaluator, Router, Module), a registry for dynamic lookup, robust execution (local/Temporal), MCP server integration, strong logging/telemetry, and a clean CLI/web UX.

Quickstart (uv-managed)

- Sync deps: `uv sync --dev --all-groups --all-extras`
- Run the CLI: `uv run flock`
- Start Web UI/API: `uv run flock --web` (add `--theme random` or a theme name)
- Start Chat UI: `uv run flock --chat` or combined with web: `uv run flock --web --chat`
- Run an example: `uv run python examples/01-getting-started/01-hello-flock.py`
- Tests: `uv run pytest`
- Useful tasks (poethepoet):
  - Build+install editable: `uv run poe build`
  - Full install incl. examples showcase: `uv run poe install`
  - Update examples submodule: `uv run poe update-showcase`

Key Environment Variables

- Models & APIs
  - `DEFAULT_MODEL`: default LLM, e.g. `openai/gpt-4o`
  - Provider keys set as required by LiteLLM (e.g., `OPENAI_API_KEY`), plus tool-specific keys (e.g., `TAVILY_API_KEY`, `GITHUB_PERSONAL_ACCESS_TOKEN`)
- Temporal
  - `TEMPORAL_SERVER_URL` (default `localhost:7233`)
- Telemetry/Logging
  - `LOG_LEVEL`, `OTEL_*` (OTLP/Jaeger/file/sqlite exporters in `src/flock/core/logging/telemetry.py`)
- Web UI
  - `FLOCK_WEB_THEME` (theme name or `random`), `FLOCK_CHAT_ENABLED` (set by the CLI flags), `FLOCK_START_MODE=chat` for chat-only

Repository Map (src/flock)

- `core/` — orchestration/runtime
  - `flock.py`: The Flock orchestrator (add agents/servers, run/serve/batch, serialize)
  - `flock_agent.py`: Agent definition + lifecycle (initialize → evaluate → terminate)
  - `flock_router.py`: Router base + `HandOffRequest` for chaining
  - `flock_evaluator.py`: Evaluator base and config
  - `flock_module.py`: Module base and lifecycle hooks
  - `execution/`: local vs Temporal executors and batch processing
  - `workflow/`: Temporal workflow and activities
  - `context/`: `FlockContext`, context vars, input resolution
  - `serialization/`: Serializable base, FlockSerializer, utils
  - `flock_registry.py`: Registry + decorators (@flock_component/@flock_tool/@flock_type) + auto-discovery
  - `flock_factory.py`: Helpers to build agents and MCP servers quickly
  - `api/`: Web API (FastAPI), custom endpoints, run store
  - `logging/`: Loguru/Temporal bridge, OpenTelemetry config, formatters
  - `mcp/`: MCP server base, configs, clients, server manager
- `evaluators/`: Built-in evaluators (Declarative, Memory, Zep, TestCase)
- `routers/`: Default, Conditional, LLM, Feedback/Retry, Agent
- `modules/`: Output/metrics/memory/assertion/callback/enterprise memory/mem0
- `tools/`: Web/code/file/text/system/GitHub/Azure/Zendesk helpers
- `webapp/`: Unified FastAPI app hosting API + UI
- `themes/`: Rich output themes for CLI/UI

Core Concepts

- Flock
  - Orchestrator that collects `FlockAgent` and optional `FlockMCPServerBase` instances.
  - Primary entrypoints:
    - `run()` / `run_async()`: execute a workflow starting with a given agent
    - `run_batch()` / `run_batch_async()`: batch execution over lists/DataFrames/CSV
    - `serve(...)`: start FastAPI server (optionally UI/chat) with custom endpoints
    - Serialization: `to_dict()/from_dict()`, `to_yaml_file()/from_yaml_file()`, JSON/MsgPack/Cloudpickle
  - Temporal: If `enable_temporal=True`, dispatches to Temporal workflow (`FlockWorkflow`) using `temporal_config` and optional in-process worker for dev (`temporal_start_in_process_worker`).

- FlockAgent
  - Declarative contract via `input` and `output` strings or callables/types:
    - Signature format: `name: type | description`, comma-separated. Types can be Python/typing/Pydantic (registered via `@flock_type`).
  - Components:
    - `evaluator` (required to produce output)
    - `handoff_router` (decides next agent)
    - `modules` (dict of `FlockModule` with lifecycle hooks)
    - `tools` (list of callables—the agent becomes a ReAct agent when tools exist)
    - `servers` (MCP servers, either by name or instance)
  - Lifecycle: `initialize` → `evaluate` → `terminate` with `on_error` hook; modules can modify inputs/results or handle errors.
  - Temporal per-activity settings via `temporal_activity_config`.
  - Serialization supports: components, tools (callable refs), MCP servers (by name), and callables for description/input/output.
  - DI: if a DI container from `wd.di` is attached under `context['di.container']`, evaluator execution may pass through middleware.

- Evaluators (src/flock/evaluators)
  - Base: `FlockEvaluator` with `evaluate(agent, inputs, tools, mcp_tools=None)`.
  - DeclarativeEvaluator: wraps DSPy; builds a `dspy.Signature` from the agent contract; supports streaming output; supports tools and MCP tools; options like `temperature`, `max_tokens`, `include_thought_process`, `include_reasoning`.
  - Memory/Zep/TestCase evaluators provided as examples.

- Routers (src/flock/routers)
  - `DefaultRouter`: deterministic `hand_off` to a named next agent or `HandOffRequest`.
  - `ConditionalRouter`: rich condition checks over context values (string/length/number/list/type/bool/existence), with retry logic, feedback keys, and success/failure routing.
  - `LLMRouter`: uses LiteLLM to select the next agent by analyzing current result and available agent definitions; expects/parses JSON response; supports a custom prompt and confidence threshold.
  - `FeedbackRetryRouter`: loops back on assertion feedback up to `max_retries`, optionally routes to `fallback_agent`.

- Modules (src/flock/modules)
  - Base: `FlockModule` with hooks: `on_initialize`, `on_pre_evaluate`, `on_post_evaluate`, `on_terminate`, `on_error`, and MCP hooks (`on_connect`, `on_pre_mcp_call`, `on_post_mcp_call`, and server lifecycle hooks).
  - `OutputModule`: pretty printing/tables in Rich; `theme` selection from `OutputTheme`.
  - `MetricsModule`: latency thresholds and basic metrics.
  - `AssertionCheckerModule`: run rules (callables/strings/LLM judge/Pydantic validators) and optionally store feedback in context (`flock.assertion_feedback`) to enable self-correction loops.
  - Memory modules (local, mem0, enterprise memory) for RAG-like patterns.

- MCP Integration
  - `FlockMCPServerBase`: abstract server with lifecycle and module hooks; manages an underlying client manager and exposes tools/resources/prompts.
  - `FlockServerManager`: async context manager that starts/stops servers around a Flock run.
  - Factory helpers in `FlockFactory.create_mcp_server(...)` to instantiate SSE/stdio/websocket/streamable HTTP backed servers with feature/callback/caching configs and optional mount points.
  - Agents can declare `servers=[server_or_name]`; tools discovered via MCP get injected as callable tools at runtime.

Execution Model

- Local Execution
  - `core/execution/local_executor.run_local_workflow(context)`: uses `workflow/activities.run_agent` loop.
  - `activities.run_agent`: resolves agent inputs from context (`core/util/input_resolver.py`), executes the agent, records history, consults router for handoff, and iterates.

- Temporal Execution
  - `core/execution/temporal_executor.run_temporal_workflow(...)` creates a Temporal client, optionally spins up a worker for dev, and starts `workflow/flock_workflow.FlockWorkflow`.
  - `FlockWorkflow`: executes two activities per step: `execute_single_agent` (run) and `determine_next_agent` (handoff); records to `FlockContext.history`; respects per-agent `TemporalActivityConfig` and workflow-level `TemporalWorkflowConfig` (task queue, retries/timeouts).

FlockContext & Input Resolution

- State: `state` dict, `history` (list of `AgentRunRecord`), `agent_definitions` (serialized agent specs), `run_id`, `workflow_id`, `workflow_timestamp`.
- Initialization: `context_manager.initialize_context` sets `FLOCK_CURRENT_AGENT`, copies initial input into `flock.<key>` variables, sets `FLOCK_LOCAL_DEBUG`, `FLOCK_RUN_ID`, `FLOCK_MODEL`.
- Input rules (`core/util/input_resolver.py`):
  - Key forms: `context` (whole context), `context.var`, `def.agent_name` (agent definition), `agent_name` (most recent record), `agent_name.var`, or plain `var` (search state/history). All with commas and type/desc stripped.
- History recording writes back last agent/result variables (`FLOCK_LAST_AGENT`, `FLOCK_LAST_RESULT`) and caches per-agent outputs under `agent.key`.

Registry & Serialization

- Registry (`core/flock_registry.py`)
  - Registers agents/servers/callables/types/components.
  - Decorators:
    - `@flock_component(config_class=...)` on classes (Evaluator/Router/Module)
    - `@flock_tool` on functions to make them available as tools
    - `@flock_type` on classes (Pydantic/Dataclass) for signature/type usage
  - Lookup utilities: `get_callable`, `get_type`, `get_component`, `get_component_class_for_config`, `get_callable_path_string`.
  - Auto-discovery: `FlockRegistry.discover_and_register_components()` scans `flock.tools`, `flock.evaluators`, `flock.modules`, `flock.routers` packages to pre-register items.

- Serialization
  - `Serializable` base implements JSON/YAML/MsgPack/Pickle helpers.
  - `FlockSerializer` controls how a whole Flock is persisted: agents, MCP servers, tools (stored as callable refs), components, custom types, and dependencies. Supports relative/absolute paths for component sources.
  - `FlockAgent.to_dict/from_dict` persists evaluator/router/modules by config and callables by name; tools saved as names resolved via registry; servers kept as names/instances via registry.
  - Loading from files via `core/util/loader.load_flock_from_file` (YAML/JSON/MsgPack/Pickle).

Web API & UI

- Start server: `flock.serve(host='127.0.0.1', port=8344, ui=True, chat=False, ui_theme=None, custom_endpoints=[...])`
- Web app: unified FastAPI app with OpenAPI docs and a simple UI (themes in `src/flock/themes`). Use `FLOCK_WEB_THEME` or `ui_theme` argument (`random` supported).
- Custom endpoints: `core/api/custom_endpoint.FlockEndpoint(path, methods, callback, ...)`. Endpoints get `flock` injected and optional Pydantic models for body/query; properly tagged and surfaced in docs.
- CLI flags: `uv run flock --web`, `--chat`, `--theme <name|random>`.

CLI Console (flock)

- Entry point `flock:main` provides a management console:
  - Create a flock, load/save YAML, manage registry and settings, run the Theme Builder, or start web server.
  - Useful for quickly assembling agents via `FlockFactory` and exporting YAML with proper tool serialization.

Batch Processing & Evaluation

- `Flock.run_batch(...)` accepts a list of dicts, a Pandas DataFrame, or a CSV path. Optional `input_mapping` for DataFrame/CSV, `static_inputs`, local parallelism (`parallel=True`, `max_workers`), or Temporal runs. Can return errors or write CSV.
- Evaluation helpers (`core/evaluation/utils.py`) integrate with Opik and common metrics patterns (optional extras required).

Tools Overview (selected)

- `web_tools`: Tavily/Bing/DuckDuckGo search, fetch page and convert to markdown
- `code_tools`: Python expression/code evaluation (constrained environment), package helpers (requires caution)
- `file_tools`: safe JSON parsing/search, read/write/append
- `text_tools`, `system_tools`, `azure_tools`, `github_tools`, `zendesk_tools`, `markdown_tools`
- All tool functions are decorated with tracing (`traced_and_logged`) and should be registered or importable for serialization.

Logging & Telemetry

- Logger (`core/logging/logging.py`): unified wrapper that uses Temporal workflow logger in workflow context, Loguru otherwise. Configurable levels. Category coloring for scan-friendly logs.
- Telemetry (`core/logging/telemetry.py`): OpenTelemetry setup with exporters (Jaeger/OTLP/file/sqlite). Baggage attributes added (e.g., `run_id`).

Examples (quick map)

- Getting Started: agents, inputs/outputs, tools, architecture — `examples/01-getting-started`
- Core Concepts: pydantic types, declarative vs imperative, chaining, tools, modules, context — `examples/02-core-concepts`
- Intermediate: web API + custom endpoints + chat, MCP servers (stdio/docker), scheduled agents, Opik, evaluation/benchmark — `examples/03-intermediate-guides`
- Advanced: Temporal execution, hydrator, streaming, etc. — `examples/04-advanced-features/08-temporal.py`

Extending Flock (patterns)

- New Module
  - Create a `FlockModuleConfig` subtype (or use `with_fields`) and a `FlockModule` subclass.
  - Decorate with `@flock_component(config_class=YourConfig)`.
  - Attach to an agent: `agent.add_component(YourConfig(...), component_name='your_module')`.

- New Evaluator
  - Subclass `FlockEvaluator`, implement `evaluate`. Optional DSPy integration via `DSPyIntegrationMixin`.
  - Provide a `FlockEvaluatorConfig` subtype. Decorate with `@flock_component(config_class=...)`.

- New Router
  - Subclass `FlockRouter`, return a `HandOffRequest` in `route(...)`.
  - Provide a `FlockRouterConfig` subtype. Decorate with `@flock_component(config_class=...)`.

- New Tools
  - Define a function and decorate with `@flock_tool` (or ensure import/registration).
  - Reference by name in `tools=[...]` when building agents, or rely on registry discovery.

- New Types
  - Decorate Pydantic models or dataclasses with `@flock_type` so they can be referenced in agent signatures and survive serialization.

Operational Tips & Gotchas

- Ensure Evaluator is set: a `FlockAgent` without an evaluator will error on `evaluate`.
- Tool serialization: Tools must be registered or importable by full path for YAML. Unregistered callables will warn and may be serialized as strings.
- LLMRouter parsing: expects a JSON block; there is a fallback keyword match, but providing a clear prompt yields better stability.
- Box dependency: Results are wrapped in `Box` if `python-box` is installed; otherwise raw `dict` is returned.
- Temporal workers: For production you typically run separate workers; the Flock `temporal_start_in_process_worker` dev helper is convenient but not for prod.
- MCP servers: Do not mutate the server manager’s server list while it is running (use the provided runtime add/remove helpers).
- DI (optional): If using `wd.di`, attach the `ServiceProvider` to `context['di.container']` so agents/evaluators can resolve dependencies/middleware.
- Context helpers: `resolve_inputs` strips type/description—keep signatures clean and consistent; prefer prefixing variables with agent names to avoid collisions.
- Web dependencies: Web/UI features require FastAPI/uvicorn/etc. (installed by default here). If running as library-only, import errors are handled gracefully.

Minimal Working Snippets

- One agent, local run
  - `flock = Flock(name="hello_flock", model="openai/gpt-4o")`
  - `agent = FlockFactory.create_default_agent(name="present", input="topic", output="title, bullets")`
  - `flock.add_agent(agent)`
  - `flock.run(start_agent=agent, input={"topic": "Robot kittens"})`

- Chain with default router
  - `a1.add_component(DefaultRouterConfig(hand_off="a2"))`
  - `flock.add_agent(a1); flock.add_agent(a2)`
  - `flock.run(start_agent="a1", input={...})`

- Serve API + UI with custom endpoint
  - Define a `FlockEndpoint` with request/response models and callback using `flock.run_async(...)`
  - `flock.serve(custom_endpoints=[endpoint], chat=True, ui_theme="random")`

Temporal Quickstart

- Create a `Flock(enable_temporal=True, temporal_config=TemporalWorkflowConfig(...))`
- Optionally set `temporal_start_in_process_worker=True` for dev. Ensure a Temporal server is reachable (`TEMPORAL_SERVER_URL`).
- Use `examples/04-advanced-features/08-temporal.py` for reference.

Examples & Workspaces

- The `examples/` directory is a submodule with its own `pyproject.toml` and `uv.lock`.
  - Inside examples: `uv sync` then `uv run python 01-getting-started/01-hello-flock.py`
  - Or install showcase deps from root via `uv run poe install-showcase`

Troubleshooting

- Missing tool/type/component at load-time:
  - Ensure module is importable and registered. Use full dotted paths where necessary. Consider calling `FlockRegistry.discover_and_register_components()` early.
- Serialization path issues:
  - Prefer `path_type="relative"` when exporting sharable YAML; ensure dependent modules are present on the target system.
- Webapp import error:
  - Install web dependencies (already in project), or run `uv sync --all-extras`.
- Temporal failures:
  - Verify Temporal server/worker connectivity, task queue names, and retry configs. Check `context.run_id` and logs/OTEL traces.

Version/Packaging Notes

- Package name: `flock-core` (`pyproject.toml`). Script entry: `flock`.
- Extras: `basic-tools`, `azure-tools`, `llm-tools`, `code-tools`, `memory`, `evaluation`, `all-tools`, `all`.
- Indices: custom PyTorch index configured (not required unless adding torch).

Where to Look for More

- README.md for positioning and high-level usage
- `examples/` for hands-on scenarios
- `src/flock/core/*` for orchestration details
- `src/flock/evaluators/*`, `src/flock/modules/*`, `src/flock/routers/*` for built-ins and extension patterns

— End of AGENTS.md —


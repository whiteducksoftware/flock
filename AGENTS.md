# AGENTS.md

Guide for AI coding agents (and humans) working on **Flock**, a blackboard-first framework for orchestrating AI agents. Read this first; it links to the detailed guides.

- **What Flock is:** agents declare which typed artifacts (Pydantic models) they consume and publish on a shared blackboard. Workflows emerge from subscriptions; nobody wires a graph. Visibility controls, a React dashboard, OpenTelemetry tracing, decision models and application hosting (Microsoft Foundry) are built in. The [README](README.md) has the overview.
- **Versions:** backend in `pyproject.toml` (`flock-core`), dashboard in `src/flock/frontend/package.json`. Read them there; do not trust numbers in prose.
- **Package manager:** [uv](https://docs.astral.sh/uv/), not pip. Task runner: [poe](https://poethepoet.natn.io/).

---

## Setup

Prerequisites: Python 3.12+, uv, and Node.js 20.19+ or 22.12+ for the dashboard (Vite 7).

```bash
git clone https://github.com/whiteducksoftware/flock.git && cd flock
uv run poe install          # ensure uv, uv sync --dev --all-groups --all-extras, build, editable install
cp .envtemplate .env        # API keys and model defaults (never commit .env, never print secrets)
uv run python -c "from flock import Flock; print('ready')"
```

Useful environment variables (see `.envtemplate` and [configuration reference](docs/reference/configuration.md)):

| Variable | Purpose |
|---|---|
| `DEFAULT_MODEL` | LLM for agents, e.g. `openai/gpt-4.1` (LiteLLM model strings) |
| `OPENAI_API_KEY`, `AZURE_API_KEY`, `AZURE_API_BASE`, `AZURE_API_VERSION` | Provider credentials |
| `DEFAULT_DECISION_MODEL` | Decision model for `.decides()`, e.g. `azure/decision-1` |
| `FLOCK_AUTO_TRACE`, `FLOCK_TRACE_FILE` | Tracing on (default on) and DuckDB trace file (default off) |
| `FLOCK_LIVE_DECISIONS=1` | Opt-in live tests against decision model providers |

## Commands

| Task | Command |
|---|---|
| All backend tests | `uv run poe test` (pytest, `asyncio_mode = "auto"`) |
| One test | `uv run pytest tests/test_file.py::test_name -v` |
| Coverage | `uv run poe test-cov` (`test-cov-fail` enforces 75 %, `test-critical` 100 % on critical paths) |
| Lint / format | `uv run poe lint`, `uv run poe lintfix`, `uv run poe format` (Ruff) |
| Frontend | `cd src/flock/frontend && npm test` (Vitest), `npm run type-check`, `npm run build`, `npm run dev` |
| Docs | `uv run poe docs-serve` (MkDocs) |
| Example | `uv run python examples/01-getting-started/01_declarative_pizza.py` |
| Live decision tests | `FLOCK_LIVE_DECISIONS=1 uv run pytest tests/decisions/test_live_providers.py` |
| Version bump | `uv run poe version-patch` (see [Versions and pull requests](#versions-and-pull-requests)) |

Pre-commit hooks run Ruff and other checks; a pre-push hook (`scripts/check_version_bump.py`) flags code changes without a version bump.

## Repository layout

| Path | Contents |
|---|---|
| `src/flock/core/` | `Flock` orchestrator, `AgentBuilder`, artifacts, subscriptions, visibility, stores (`store.py`: in-memory, SQLite), context providers, conditions (`Until`), fan-out |
| `src/flock/orchestrator/` | Scheduling, lifecycle, batching, correlation (joins), context building, server manager |
| `src/flock/agent/` | Agent execution: output processing, builder helpers |
| `src/flock/components/` | Agent, orchestrator (timer, webhooks, circuit breaker, dedup) and server components |
| `src/flock/engines/` | `DSPyEngine` (default), example engines, Azure auth helpers |
| `src/flock/decisions/` | Decision models: question types, providers, engine, routing, request budgets |
| `src/flock/application/` | `FlockApplication`: one isolated workflow per request, for hosts |
| `src/flock/integrations/` | Microsoft Foundry hosting (`foundry`), OpenClaw |
| `src/flock/storage/` | Dapr state-store blackboard (`flock-core[dapr]`) |
| `src/flock/semantic/` | Embeddings for semantic subscriptions and `SemanticContextProvider` (`flock-core[semantic]`) |
| `src/flock/api/` | REST API services, dashboard event collector, graph builder |
| `src/flock/mcp/`, `src/flock/logging/`, `src/flock/utils/` | MCP client, logging and tracing, runtime types (`Context`, `EvalResult`) |
| `src/flock/frontend/` | React/TypeScript dashboard (Vite) |
| `tests/`, `examples/`, `docs/` | Tests, runnable examples (numbered folders), MkDocs site |

Never put new files in the repository root. Tests go to `tests/` (`test_<module>.py`; frontend tests next to the component as `*.test.tsx`), examples to the matching `examples/NN-topic/` folder, docs to `docs/guides/` (and the nav in `mkdocs.yml`).

---

## Core API in one page

```python
from flock import Flock, flock_type
from pydantic import BaseModel


@flock_type
class Idea(BaseModel):
    topic: str


@flock_type
class Pitch(BaseModel):
    title: str
    hook: str


flock = Flock("openai/gpt-4.1")
writer = flock.agent("writer").description("Writes pitches").consumes(Idea).publishes(Pitch)

await flock.publish(Idea(topic="cats in space"))
await flock.run_until_idle()
pitches = await flock.store.get_by_type(Pitch)  # list[Pitch]
```

- **Subscriptions:**
  - `.consumes(A, B)` is an AND gate. `.consumes(A).consumes(B)` is OR.
  - `.consumes(A, A, A)` waits for three artifacts of type A.
  - Filters: `where=` predicates, `tags=`, `from_agents=`, `semantic_match=` (needs `[semantic]`).
  - `batch=BatchSpec(size=, timeout=)` collects a batch; `join=JoinSpec(by=, within=)` correlates artifacts.
- **Publishing:**
  - `.publishes(X, fan_out=10 | (min, max), where=, validate=, visibility=)`.
  - Several types at once: `.publishes(A, B, fan_out=3)`.
  - `fan_out` ranges apply to the raw engine output, before `where`/`validate` ([fan-out guide](docs/guides/fan-out.md)).
- **Visibility** (from `flock`): `PublicVisibility`, `PrivateVisibility(agents=...)`, `TenantVisibility(tenant_id=...)`, `LabelledVisibility(required_labels=...)`, `AfterVisibility(ttl=..., then=...)`. Agents get labels and tenants with `.labels(...)` and `.tenant(...)`.
- **Context providers** (`flock.core.context_provider`):
  - Built in: `DefaultContextProvider`, `FilteredContextProvider(FilterConfig(...))`, `CorrelatedContextProvider`, `RecentContextProvider`, `TimeWindowContextProvider`, `EmptyContextProvider`. `SemanticContextProvider` lives in `flock.semantic`.
  - Set them globally with `Flock(..., context_provider=)` or per agent with `.with_context(provider)`.
  - Custom providers extend `BaseContextProvider`, which enforces visibility.
- **Scheduling:**
  - `.schedule(every=timedelta | at=time | at=datetime | cron="0 9 * * 1-5", after=, max_repeats=)`.
  - Timer runs see `ctx.trigger_type == "timer"`, `ctx.timer_iteration` and `ctx.fire_time` on `flock.Context`.
- **Execution control:**
  - `run_until_idle()`, `run_until(Until.artifact_count(X).at_least(5) | Until.workflow_error(cid), timeout=)` (`flock.core.conditions`).
  - `invoke(agent, artifact, publish_outputs=...)`, `arun(agent, *inputs)`, `async with flock.traced_run("name")`.
- **Components:**
  - `AgentComponent` hooks: `on_initialize`, `on_pre_consume`, `on_pre_evaluate`, `on_post_evaluate`, `on_post_publish`, `on_error`, `on_terminate`. Add them with `.with_utilities(...)`.
  - Orchestrator components: [guide](docs/guides/orchestrator-components.md).
  - Server components: `on_startup_async`, `on_shutdown_async`, `register_routes`, added with `flock.add_server_component(...)`.
- **Engines:** `.with_engines(DSPyEngine(...))` or a custom `EngineComponent`. `DSPyEngine(lm_kwargs={"azure_ad_token_provider": get_default_azure_token_provider()})` uses Entra ID; the helper is in `flock.engines.auth.azure` and needs the `azure` extra.
- **Persistence:**
  - `Flock(..., store=SQLiteBlackboardStore(".flock/blackboard.db"))` from `flock.core.store`; the schema is created on first use.
  - Maintenance: `flock sqlite-maintenance DB --delete-before ISO --vacuum`.
  - Dapr state stores: [Dapr guide](docs/guides/dapr-state-store.md).
- **Webhooks:** `WebhookDeliveryComponent` (`flock.components.orchestrator`) delivers artifacts to the webhook URL and secret given with a REST publish request ([webhooks guide](docs/guides/webhooks.md)).
- **Dashboard and API:** `await flock.serve(dashboard=True)` serves the REST API (OpenAPI at `/docs`) and the dashboard on port 8344.

### Decision models

Typed questions answered by a decision model (calibrated probabilities, no generated text). Guide: [docs/guides/decisions.md](docs/guides/decisions.md).

```python
from flock import Choice, Decision, Flock, YesNo


class Route(Choice):
    """Which team should handle this support ticket?"""  # the question

    billing = "Charges, invoices, refunds"                # option: criteria
    tech = "Bugs, crashes, login problems"


class Urgent(YesNo):
    """Does the customer need an answer today?"""


flock = Flock("openai/gpt-4.1", decision_model="azure/decision-1", decision_rate_limit="100/min")
flock.agent("triage").consumes(Ticket).decides(Route, Urgent, threshold=0.8)  # one request, one Decision per question

flock.agent("billing").consumes(Route.billing).publishes(Reply)       # receives the Ticket; decision on ctx.decision
flock.agent("supervisor").consumes(Route.UNSURE).publishes(Reply)     # below the threshold or refused
flock.agent("pager").consumes(Route.tech, Urgent.yes).publishes(Page)  # AND about the same ticket (ctx.decisions)
flock.agent("audit").consumes(Decision.of(Route)).publishes(Entry)    # the decision itself (separate agent from handles)
```

- **Question types:**
  - `Choice`: 2+ options; more than 255 need `tournament=` or `options=`.
  - `YesNo`.
  - `Scale`: 2-10 levels; `Anger.angry.or_higher` compares the weighted score.
  - `Checklist`: one yes/no per item, one decision. Handles: `.passed`, `.failed`, `.item.no`.
  - `Choice.from_options(...)` and `Checklist.from_items(...)` build questions from catalogs.
- **Large catalogs:**
  - `tournament=Tournament(group_size=20, keep=3)` asks the choice in rounds.
  - `options=callable` restricts a question to a runtime subset.
  - Several handles in one `.consumes()` build screening networks.
- **Providers** (`flock.decisions.providers`): `azure/<deployment>`, `openai/<model>`, `jev/<model>`, `local/<name>` (`DECISION_API_BASE`).
  - Model precedence: `model=` on `.decides()`, then `Flock(decision_model=)`, then `DEFAULT_DECISION_MODEL`.
  - HTTP 429/503 are retried after the server's advice plus a jittered backoff.
- **Rules:**
  - A decision agent publishes only its decisions: no `.with_engines()` or `.publishes()` with `.decides()`.
  - Handles and `Decision.of(X)` cannot share an agent.
  - Images go to providers that support them (`flock.Image`, limits 20 MB and 50 MP).
- **Tests:** `FakeDecider({"billing": 0.9, "tech": 0.1})` from `flock.decisions` is deterministic and records `requests`. For several questions: `FakeDecider({"Route": {...}, "Urgent": {"yes": 0.8, "no": 0.2}})`. For a checklist, map item to probability of yes.

### Applications and Microsoft Foundry

`FlockApplication` (from `flock`) runs one request as one isolated workflow: a factory builds a fresh `Flock`, `input_type` and `output_types` define the contract, outputs stream per artifact, and every workflow ends with one `WorkflowResult`. `flock.integrations.foundry.FoundryResponsesAdapter` hosts it as a Microsoft Foundry hosted agent (`flock-core[foundry]`; Azure packages are imported lazily, never by `import flock`). Guides: [applications](docs/guides/applications.md), [Foundry](docs/guides/foundry.md); examples `examples/13-applications/`, `examples/14-foundry/`.

---

## Critical patterns

### `invoke()` vs `run_until_idle()`

```python
# Unit test: run one agent, publish nothing, no cascade
await flock.invoke(agent, artifact, publish_outputs=False)

# Integration test: publish outputs, then let downstream agents run
await flock.invoke(agent, artifact, publish_outputs=True)
await flock.run_until_idle()
```

`prevent_self_trigger` is on by default, so an agent does not re-run on its own outputs. This is not a double run; downstream agents run.

### Publish first, then run: parallelism

`publish()` only schedules work, and `run_until_idle()` executes it. Publish many artifacts, then call `run_until_idle()` once, so independent agents run concurrently. Separate unrelated workflows with `async with flock.traced_run("name")`.

### Test isolation

- Never leave class-level patches behind. Use fixtures that restore the original in `finally` (or `monkeypatch`).
- Run a new test file alone and inside the full suite. Contamination shows up only in the full run.
- Common sources: `PropertyMock` on classes, module-level patches, shared mutable state, leaked asyncio tasks, global type-registry names. Give `@flock_type` models in tests unique class names.

### Time

- **Measure intervals with `time.monotonic()`, never with the wall clock.** On WSL2 the wall clock can step back by a second or more every 30 s (VM time sync), and daylight saving moves it too. Batch timeouts use the monotonic clock for this reason.
- In tests, assert requested waits (patch `asyncio.sleep` in the module under test) instead of measuring elapsed time with tight bounds. Assert only lower bounds on real elapsed time.

### Logging

Use the Flock logger, never `logging.getLogger` directly:

```python
from flock.logging.logging import get_logger

logger = get_logger(__name__)
```

### Error handling and async

Follow [docs/patterns/error_handling.md](docs/patterns/error_handling.md) and [docs/patterns/async_patterns.md](docs/patterns/async_patterns.md). The architecture overview is [docs/architecture.md](docs/architecture.md).

---

## Debugging with traces

Tracing is the fastest way to see what happened: every operation is recorded with its inputs and outputs.

```bash
export FLOCK_AUTO_TRACE=true FLOCK_TRACE_FILE=true
uv run python examples/01-getting-started/01_declarative_pizza.py   # or a pytest run
```

```python
import duckdb

conn = duckdb.connect(".flock/traces.duckdb", read_only=True)
trace_id = conn.execute(
    "SELECT trace_id FROM spans GROUP BY trace_id ORDER BY MIN(start_time) DESC LIMIT 1"
).fetchone()[0]
for name, service, ms, status, error in conn.execute(
    "SELECT name, service, duration_ms, status_code, status_description "
    "FROM spans WHERE trace_id = ? ORDER BY start_time",
    [trace_id],
).fetchall():
    print("✅" if status == "OK" else "❌", name, service, f"{ms:.0f} ms", error or "")
```

- **Columns of `spans`:** `trace_id`, `span_id`, `parent_id`, `name`, `service`, `operation`, `kind`, `start_time`, `end_time`, `duration_ms`, `status_code`, `status_description`, `attributes` (JSON, including inputs and outputs), `events`, `links`, `resource`.
- **Housekeeping:** use read-only connections, and clear old traces with `Flock.clear_traces()`.
- **Guides:** [Tracing](docs/guides/tracing/index.md), [unified tracing](docs/guides/tracing/unified-tracing.md).

## Dashboard development and manual testing

- **Build flow:** `serve(dashboard=True)` builds the frontend (`npm run build` in `src/flock/frontend`) into `src/flock/api/static/`, which is gitignored, and serves it on port 8344. `src/flock/api/static_files/` holds a committed build that the server does not read.
- **Manual check:** run `uv run python examples/04-misc/02-dashboard-edge-cases.py` and open `http://localhost:8344` with a browser tool such as playwright-mcp.
  1. The title is "🦆🐓 Flock 🐤🐧", the WebSocket status is "Connected", and the views are "Agent View" and "Blackboard View".
  2. Publish an artifact from the publish panel. Agents should go from idle to running to idle, and counters and edges should update live.
  3. Auto Layout is in the right-click menu of the canvas (hierarchical, circular, grid, random).
  4. With many artifacts, take screenshots instead of accessibility snapshots, which get too large.
- **After UI changes:** run `npm test` and `npm run type-check`, and bump the frontend version.

---

## Versions and pull requests

- **Bump versions with every code change:**
  - backend (`pyproject.toml` and `uv.lock`) for anything in `src/flock/`;
  - frontend (`src/flock/frontend/package.json` and `package-lock.json`) for dashboard changes;
  - docs-only changes need no bump.
- **Version scheme:** plain `X.Y.Z`, no beta tags, and the last segment never has more than three digits. New features start a series (0.5.720, 0.5.730); follow-ups count up within it (0.5.721 … 0.5.729), and after 0.5.729 comes 0.5.730.
- **One issue per pull request.** PRs target `main`. A stacked PR targets the PR below it; GitHub retargets the next PR to `main` as the stack merges ([stacked PRs](https://docs.github.com/en/pull-requests/get-started/about-stacked-prs)).
- **Before a PR:**
  - `uv run poe test` and `uv run poe lint` pass, and the frontend tests pass if the UI changed;
  - versions are bumped;
  - the changelog (`docs/about/changelog.md`) is updated;
  - screenshots are included for UI changes.

---

## Documentation map

| Topic | Guide |
|---|---|
| Concepts | [Blackboard](docs/guides/blackboard.md), [agents](docs/guides/agents.md), [patterns](docs/guides/patterns.md), [use cases](docs/guides/use-cases.md) |
| Subscriptions | [Predicates](docs/guides/predicates.md), [joins](docs/guides/join-operations.md), [batching](docs/guides/batch-processing.md), [semantic](docs/guides/semantic-subscriptions.md), [workflow control](docs/guides/workflow-control.md) |
| Publishing | [Fan-out](docs/guides/fan-out.md), [visibility](docs/guides/visibility.md), [webhooks](docs/guides/webhooks.md) |
| Decisions | [Decision models](docs/guides/decisions.md) |
| Hosting | [Applications](docs/guides/applications.md), [Microsoft Foundry](docs/guides/foundry.md), [REST API](docs/guides/rest-api.md), [server components](docs/guides/server-components.md) |
| Extending | [Agent components](docs/guides/components.md), [orchestrator components](docs/guides/orchestrator-components.md), [DSPy engine](docs/guides/dspy-engine.md), [local models](docs/guides/local-models.md), [context providers](docs/guides/context-providers.md) |
| Operations | [Scheduling](docs/guides/scheduling.md), [persistence](docs/guides/persistent-blackboard.md), [Dapr](docs/guides/dapr-state-store.md), [dashboard](docs/guides/dashboard.md), [tracing](docs/guides/tracing/index.md), [testing](docs/guides/testing.md) |
| Contributing | [CONTRIBUTING.md](CONTRIBUTING.md), [configuration](docs/reference/configuration.md), [imports](docs/guides/imports.md) |

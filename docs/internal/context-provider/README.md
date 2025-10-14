# Context Provider Blueprint

**Status:** Design sketch • Feedback welcome
**Owner:** Codex agent
**Last updated:** 2025-02-14

---

## Why This Exists

Today `EngineComponent.fetch_conversation_context()` pulls every artifact that shares the current `correlation_id`. That default gives us safe, deterministic cascades, but it falls short whenever an agent needs:

- **Richer memory:** e.g., “Show me the last three wins this agent posted anywhere on the board.”
- **Selective recall:** e.g., “Hide drafts tagged `#internal` even if they share the correlation id.”
- **Cross-run intelligence:** e.g., mixing historical benchmarks with the live workflow.

The goal is to introduce a **Context Provider** abstraction that keeps the existing behavior as the default while letting power users plug in explicit policies for what gets surfaced to an engine.

---

## Design Goals

- **Composable:** Agents choose the provider they want; utilities can layer extra logic without rewriting engines.
- **Visibility-aware:** Providers route through the blackboard store so existing ACL rules stay in force.
- **Declarative by default, extensible when needed:** Simple filters for common cases, full custom code for bespoke policies.
- **No hidden coupling:** Providers operate on well-defined request objects; they cannot mutate orchestrator internals.

---

## Proposed API Surface

```python
# src/flock/context.py (new)
class ContextRequest(BaseModel):
    agent: Agent
    ctx: Context
    inputs: EvalInputs
    board: BlackboardStoreHandle  # ctx.board
    correlation_id: UUID | None
    config: dict[str, Any] = {}


class ContextSlice(BaseModel):
    """Structured payload handed to engines/components."""
    items: list[dict[str, Any]]
    metadata: dict[str, Any] = {}


class ContextProvider(Protocol):
    async def __call__(self, request: ContextRequest) -> ContextSlice:
        ...
```

### Registration

```python
class AgentBuilder:
    def with_context(
        self,
        provider: ContextProvider,
        *,
        fallback: ContextProvider | None = None,
    ) -> AgentBuilder: ...

    def with_context_filter(
        self,
        *,
        filters: FilterConfig | None = None,
        limit: int | None = None,
        include_state_keys: set[str] | None = None,
    ) -> AgentBuilder: ...
```

- `with_context(...)` sets the provider for all engines on that agent.
- `with_context_filter(...)` is a convenience that instantiates a `FilteredContextProvider` (see below).
- Engines can override per-engine context through `DSPyEngine(context_provider=...)` etc. If absent, the agent-level provider is used; if that is missing, we fall back to the current correlation-only provider.

### Engine Consumption

```python
class EngineComponent:
    context_provider: ContextProvider | None = None

    async def fetch_conversation_context(self, ctx: Context) -> list[dict[str, Any]]:
        provider = self.context_provider or ctx.agent_context_provider or DefaultCorrelationProvider()
        request = ContextRequest(
            agent=ctx.agent,
            ctx=ctx,
            inputs=ctx.inputs,
            board=ctx.board,
            correlation_id=ctx.correlation_id,
        )
        return (await provider(request)).items
```

Here `ctx.agent_context_provider` is injected by the orchestrator while setting up the execution.

---

## Built-In Providers

| Provider | What it does | Notes |
|----------|--------------|-------|
| `DefaultCorrelationProvider` | Existing behavior: all artifacts with matching correlation id. | Serves as the fallback and keeps legacy examples working. |
| `FilteredContextProvider` | Wraps a `FilterConfig` (type, tags, time window, producers) and optional limit. | Great for simple “last N matching artifacts” use cases. |
| `StateDelegatingProvider` | Returns whatever a component stashed at `ctx.state["context_snapshot"]`. | Lets utilities pre-compute context so engines just read it. |
| `CompositeProvider` | Runs N providers sequentially and merges the slices (with dedupe by artifact id). | Useful for “current workflow + historical benchmarks”. |
| `RedactingProvider` | Wraps another provider and prunes payload keys (or applies callable transforms). | Handy for GDPR/PII scenarios. |

Providers can be nested: e.g., `CompositeProvider(DefaultCorrelationProvider(), FilteredContextProvider(...))`.

---

## Example Workflow (Pseudo-Script)

This mirrors the existing examples pattern but showcases a custom provider that mixes live artifacts with historical wins while redacting sensitive fields.

```python
# examples/07-context-providers/pep_talk_context.py

from flock import Flock, flock_type
from flock.context import ContextProvider, ContextRequest, ContextSlice
from flock.filters import FilterConfig, TagFilter
from flock.engines.dspy_engine import DSPyEngine
from flock.runtime import EvalInputs, EvalResult


class RecentWinsProvider:
    """Provide recent wins plus the active run, redacting private notes."""

    def __init__(self, max_wins: int = 3) -> None:
        self.max_wins = max_wins

    async def __call__(self, request: ContextRequest) -> ContextSlice:
        items: list[dict[str, Any]] = []

        # 1) Include the default correlation view (current cascade)
        correlation = await DefaultCorrelationProvider()(request)
        items.extend(correlation.items)

        # 2) Add last N wins from the whole board
        wins_filter = FilterConfig(
            types={"PitchResult"},
            tags=TagFilter(include={"deal_won"}),
            limit=self.max_wins,
            order="-created_at",
        )
        wins, _total = await request.board.query_artifacts(wins_filter, embed_meta=True)
        for envelope in wins:
            payload = dict(envelope.payload)
            payload.pop("private_notes", None)  # Redact internal notes
            items.append(
                {
                    "type": envelope.type,
                    "payload": payload,
                    "produced_by": envelope.produced_by,
                }
            )

        return ContextSlice(items=items)


@flock_type
class Pitch(BaseModel):
    product: str
    audience: str
    highlight: str


@flock_type
class PitchResult(BaseModel):
    tagline: str
    closer: str
    private_notes: str | None = None


async def main():
    flock = Flock()

    (
        flock.agent("pep_talk_lead")
        .description("Adds a hype meter to every pitch.")
        .consumes(Pitch)
        .publishes(PitchResult)
        .with_context(RecentWinsProvider(max_wins=5))  # 👈 inject custom context
        .with_engines(DSPyEngine())
    )

    await flock.publish(Pitch(...))
    await flock.run_until_idle()
```

In this script the DSPy engine receives context that looks like:

```json
[
  {"type": "Pitch", "payload": {...}},             // from current cascade
  {"type": "PitchResult", "payload": {...}},       // previous wins (redacted)
  ...
]
```

Because we routed through the store, visibility constraints and tenant separation still apply.

---

## Implementation Notes

- **Backward compatibility:** If no provider is set, we call `DefaultCorrelationProvider`. Existing examples keep working.
- **Tracing:** Each provider invocation should be wrapped in its own span (`ContextProvider.__call__`). We can add automatic tracing by making `ContextProvider` implementations inherit from `AgentComponent` or by decorating the orchestrator callsite.
- **Caching:** Providers can optionally cache results in `ctx.state` if they plan multiple reads during one execution. The orchestrator should pass the same `ContextSlice` to every engine on the agent to avoid duplicate work.
- **Testing:** New unit tests can spin up an in-memory store, publish artifacts, assign a provider, and assert the context list contents. Integration tests should verify that visibility constraints are respected.

---

## Open Questions

1. **Per-subscription context?** Some teams might want different providers depending on the input type. Should we allow `.consumes(..., context_provider=...)`?
2. **Materialized views:** Do we need a convenience API for “summaries only” where the provider converts artifacts into LLM-friendly strings?
3. **Dashboard integration:** Should the dashboard surface which provider furnished the context slice for observability?

Feedback and extensions welcome—this is a blueprint to unblock richer, safer context management without sacrificing the blackboard-first philosophy.

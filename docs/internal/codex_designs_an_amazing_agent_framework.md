# Codex Designs An Amazing Agent Framework (DX‑first)

Goal: a framework someone picks up, writes 10 lines, and it “just works.” No bus, events, or DAGs in their face. No prompts to write. Everything declarative, typed, and reactive under the hood.

## The First 10 Lines (what users see)

```python
from amazing import agent, App
from pydantic import BaseModel
from typing import Literal

class Idea(BaseModel):
    topic: str
    genre: Literal["comedy","drama","horror","action","adventure"]

class Movie(BaseModel):
    fun_title: str
    runtime: int
    synopsis: str

movie = agent("movie").contracts(input=Idea, output=Movie).model("openai/gpt-4o-mini")
critic = agent("critic").contracts(input=Movie, output=str).model("auto")

# The only wiring most users need:
critic.reacts_to(movie)

app = App([movie, critic])
result = app.run(Idea(topic="AI agents", genre="comedy"))
print(result)  # {'movie': Movie(...), 'critic': '...'}
```

That’s it. No events, buses, or DAG authoring. `reacts_to` wires outputs to inputs, with automatic type‑aware mapping.

## Design Tenets (user‑facing)

- Contracts, not prompts: users declare Pydantic models and pick a model name. The framework converts contracts to structured generation automatically.
- One‑line wiring: `b.reacts_to(a)`, `c.reacts_to(b)`, or chaining sugar: `flow = a.then(b).then(c)`.
- Smart mapping: outputs → inputs are matched by type/name; tiny transforms can be added with `.map(lambda m: {...})` when needed.
- Everything has sane defaults: local single‑process runtime, mock engine in tests, useful logs, and streaming to console with `.stream()`.

## A Bit More Sugar

- Conditional reactions: `b.reacts_to(a, when=lambda out: out.score > 0.8)`
- Fan‑out: `b.reacts_to(a); c.reacts_to(a)`
- Converge: `d.reacts_to(b, c)` (auto merges fields by type; conflicts resolved by simple policy or a tiny mapper)
- Tools: `agent(...).with_tools(calc, search)` (typed tools; no prompt glue)
- Memory: `agent(...).with_memory(vector="pgvector", graph=True)` (still one line)
- Reasoning: `agent(...).reasoning(on=True)` toggles CoT internally without exposing engine jargon

## Under the Hood (kept invisible by default)

- Reactive runtime: implemented with a tiny pub/sub core. In dev it’s pure in‑proc; in prod, a durable log (NATS/Redis/Kafka) can be enabled by config. Users don’t have to care.
- Engine adapters: JSON‑Schema (function‑calling), PydanticAI/Instructor (light), BAML (assertions/TypeBuilder). Pick `model("auto")` and we choose a sensible default; expert users can pin engines.
- Type‑aware routing: contracts compile to schemas; outputs validate into inputs. We auto‑generate the minimum “system primer” for structured output — users never edit prompts.
- Reliability: at‑least‑once, idempotency, retries, DLQ in prod mode; instant local mode in dev.

## Why This Beats DAGs and “Crew” Style UIs

- Fewer concepts: Agent + `.reacts_to(…)`. No graphs to draw, no YAML spaghetti.
- Safer by default: types everywhere; invalid outputs never pass silently.
- Extensible later: if you need multi‑tenant queues, backpressure, DLQ — switch on “prod mode” in one config line.

## Power Without Pain (for advanced users)

- Data transforms:
  - `critic.reacts_to(movie).map(lambda m: {"script": m.synopsis})`
  - `post.reacts_to(movie, critic).map(lambda mv, cr: {"title": mv.fun_title, "blurb": cr})`
- Inline guards: `agent(...).asserts(lambda out: len(out.synopsis) > 0, "empty synopsis")`
- Streaming: `app.run(input, stream=True)` yields deltas; `.tap(print)` for live console output.
- Observability: `.trace()` prints a one‑screen flow summary with latencies, tokens, and costs.

## Minimal Concepts (internals summarized)

- Agent: name, contracts(input, output), optional tools/memory/options, and an engine.
- Wiring: `.reacts_to(other)` and `.then(other)` are the only verbs most users need. They compile to subscriptions internally.
- App: collects agents, runs locally by default; `mode="prod"` uses durable infra.

## Defaults That “Just Work”

- Model provider: `model("auto")` chooses a local/open provider in dev; pinned providers in prod.
- Engine: JSON‑Schema engine for structured output unless a more specific engine is requested.
- Tests: mock engine by default (deterministic), no network.
- Errors: validation errors are clear, typed, and point to the offending field.

## Example: Three Agents, One Line Each

```python
extract = agent("extract").contracts(input=str, output={"facts": list[str]}).model("auto")
draft   = agent("draft").contracts(input={"facts": list[str]}, output=str)
review  = agent("review").contracts(input=str, output=str)

draft.reacts_to(extract)
review.reacts_to(draft)

App([extract, draft, review]).run("raw text…")
```

## Implementation Plan (still pragmatic)

1) DX Core
   - API sugar: `agent()`, `.contracts()`, `.reacts_to()`, `.then()`, `.with_tools()`, `.with_memory()`
   - Local in‑proc scheduler; JSON‑Schema engine; mock engine; basic tracing/metrics
2) Engines
   - Instructor/PydanticAI engine (lightweight); optional BAML engine for assertions/TypeBuilder
3) Prod Mode
   - Pluggable bus (NATS/Redis/Kafka), idempotency store, retries/DLQ; zero‑config “on” switch
4) Tooling/Memory
   - Typed tools registry; vector/graph memory adapters (off by default)
5) Observability
   - `.trace()`, OpenTelemetry, simple web dashboard; replay/DLQ via CLI

## Promise

- You define types and write `a.reacts_to(b)` — we do the rest.
- No prompts, no DAGs, no bus talk. Just agents that work together.

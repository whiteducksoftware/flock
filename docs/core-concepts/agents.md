---
hide: # Optional: Hide table of contents on simple pages
  - toc
---

# Flock Agents 🐦

A **FlockAgent** is the fundamental unit of work. Each agent is declarative — you specify what goes in and what should come out. Components provide the “how”.

---

## 1. Anatomy of an Agent (Unified)

```python
from flock.core import FlockFactory

agent = FlockFactory.create_default_agent(
    name="movie_pitcher",
    description="Create a fun movie idea",
    input="topic: str | Central subject",
    output="title: str, runtime: int, synopsis: str",
)
```

### Key Fields

| Field | Type | Intent |
| ----- | ---- | ------ |
| `name` | `str` | Unique identifier; becomes the registry key. |
| `model` | `str | None` | Override the default model for this agent. |
| `description` | `str \| Callable \| BaseModel` | High-level instruction (string or callable). |
| `input` | `str | BaseModel` | Contract for accepted data. |
| `output` | `str | BaseModel` | Contract for produced data. |
| `tools` | `list[Callable]` | Extra callables the evaluator may invoke. |
| `components` | `list[AgentComponent]` | Unified list: evaluation, routing, utility. |
| `evaluator` | `EvaluationComponent | None` | Convenience property: primary evaluator. |
| `router` | `RoutingComponent | None` | Convenience property: primary router. |

All these fields are **Pydantic-validated** and fully serialisable via `Serializable`.

---

## 2. Contracts: Input & Output

Signatures are written in a compact mini-DSL:

* `field` – just a name (type & description inferred by the LLM).
* `field: type` – adds a type hint.
* `field: type | description` – adds a natural-language description.
* Multiple fields are comma-separated.
* Lists/dicts follow normal Python typing: `list[dict[str, str]]`.

Alternatively, pass **Pydantic models** (recommended for complex schemas):

```python
from pydantic import BaseModel

class SearchIn(BaseModel):
    query: str
    top_k: int = 5

class SearchOut(BaseModel):
    documents: list[str]

search_agent = FlockFactory.create_default_agent(
    name="searcher",
    input=SearchIn,
    output=SearchOut,
)
```

---

## 3. Lifecycle

```mermaid
flowchart LR
    A[initialize] --> B[evaluate]
    B --> C[terminate]
    B -. error .-> D[on_error]
```

1. **initialize** – prepare resources (DB connection, load embeddings, etc.).
2. **evaluate** – main logic executed by the evaluator.
3. **terminate** – clean-up, persist metrics.
4. **on_error** – triggered if any previous stage raises.

Components (utility) can hook into each stage to extend behavior.

---

## 4. Adding Components

```python
from flock.components.utility.output_utility_component import OutputUtilityComponent, OutputUtilityConfig
from flock.components.routing.default_routing_component import DefaultRoutingComponent, DefaultRoutingConfig

agent.add_component(OutputUtilityComponent(name="output", config=OutputUtilityConfig(render_table=True)))
agent.add_component(DefaultRoutingComponent(name="router", config=DefaultRoutingConfig()))
```

---

## 5. Best Practices

* Keep `description` concise; use the signature for fine-grained control.
* Prefer Pydantic models for complex schemas – you get validation for free.
* Separate concerns: evaluator handles logic, utility components handle cross‑cutting tasks.
* Register reusable tools with `@flock_tool` so any agent can adopt them.

---

**Next:**  Learn *why* this declarative approach works in [Declarative Programming](declarative.md).

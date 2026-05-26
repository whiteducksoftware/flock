---
hide: # Optional: Hide table of contents on simple pages
  - toc
---

# Workflows & Orchestration 🚦

A **workflow** in Flock is *simply* a sequence of agent evaluations managed by a `Flock` orchestrator.  You can think of the orchestrator as an event loop with built-in telemetry and error handling that knows which agent to call next.

---

## 1. Creating a Workflow

```python
from flock.core import Flock, FlockFactory
from flock.routers.agent import AgentRouter

flock = Flock(name="demo")

search_agent = FlockFactory.create_default_agent(
    name="searcher",
    input="query: str",
    output="documents: list[str]",
)

summariser = FlockFactory.create_default_agent(
    name="summariser",
    input="docs: list[str]",
    output="summary: str",
)

flock.add_agent(search_agent)
flock.add_agent(summariser)

# Explicit chain
search_agent.handoff_router = AgentRouter(
    name="router",
    config={"with_output": False}
)
```

You can start the workflow by **name** or by passing the agent instance:

```python
result = flock.run(start_agent="searcher", input={"query": "LLM frameworks"})
print(result.summary)
```

---

## 2. Routing Strategies

| Router | Behaviour | Use-case |
| ------ | --------- | -------- |
| *None* | Linear – stops after first agent. | Simple tasks. |
| `AgentRouter` | Uses an LLM to pick the next agent based on `current_result`. | Dynamic multi-step assistants. |
| Custom Router | Subclass `FlockRouter` and implement `route(...)`. | Heuristic or rule-based flows. |

Routers return a `HandOffRequest` (`agent_name`, optional `input_override`, optional `confidence`).  Returning `None` ends the run.

---

## 3. Context Propagation

Every run owns a `FlockContext` containing:

* `state` – mutable key-value store (`context.set_variable(...)`).
* `history` – ordered list of `(agent_name, result)` tuples.
* `run_id` – UUID injected into OpenTelemetry baggage.
* Agent definitions – serialized versions for Temporal workers.

Agents and modules can read/write to the context at will, enabling memory and coordination.

---

## 4. Batch & Async Helpers

```python
# Run multiple inputs concurrently
results = await flock.run_batch_async(
    start_agent="searcher",
    input_list=[{"query": q} for q in queries],
)
```

Evaluation mode:

```python
metrics = await flock.evaluate_async(
    agent_name="summariser",
    dataset=my_dataset,
    evaluator=BleuEvaluator(),
)
```

---

## 5. Temporal Execution

Passing `enable_temporal=True` upgrades the run into a **durable workflow**.  Under the hood Flock:

1. Serialises the entire flock (including agent definitions) via `FlockSerializer`.
2. Starts a `FlockWorkflow` on the configured Temporal cluster.
3. Each agent execution becomes a **Temporal Activity** – retriable, cancellable, and observable via Temporal Web.

This means you get *exactly* the same code path for local debugging and production-grade reliability.

---

## 6. Error Handling

* All exceptions inside an agent are routed to `on_error` hooks.
* The orchestrator captures unhandled errors, records them in the context history, and surfaces them to the caller.
* When using Temporal, failed activities can be automatically retried based on `TemporalActivityConfig`.

---

## 7. Tips for Designing Workflows

* Keep agents **single-purpose**; compose higher-level behaviour via routers.
* Use context variables prefixed with `flock.` to avoid collisions (`flock.user_id`).
* Benchmark with `flock.evaluate_async` before shipping.
* Prefer batch helpers for throughput-critical workloads.

---

🎉 That's all for workflows!  Move on to component deep-dives in the [Components section](../components/index.md).

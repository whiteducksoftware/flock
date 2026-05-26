---
hide: # Optional: Hide table of contents on simple pages
  - toc
---

# Modules 🧩

Modules let you **augment** agents with additional behaviour without touching their core logic.  They follow the classic *aspect-oriented* approach: hook into lifecycle stages and run code *around* the evaluator.

---

## 1. Anatomy

```python
class MyModule(FlockModule):
    async def initialize(self, agent, inputs, context):
        ...  # called before evaluate

    async def after_evaluate(self, agent, result, context):
        ...  # inspect/transform result

    async def terminate(self, agent, context):
        ...  # cleanup

    async def on_error(self, agent, error, context):
        ...  # exception handling
```

The base class also exposes a `.config` dataclass so users can set parameters declaratively.

---

## 2. Built-in Modules

| Module | Purpose |
| ------ | ------- |
| `OutputModule` | Pretty-prints results to the console via *Rich*. |
| `MetricsModule` | Records latency & token metrics, raises alerts. |
| `MemoryModule` *(WIP)* | Persistent, vectorised memory per agent. |
| `TracingModule` | Adds extra OpenTelemetry spans/tags. |

You attach modules either during construction:

```python
agent = FlockFactory.create_default_agent(...)
agent.add_module(OutputModule("output", OutputModuleConfig(render_table=True)))
```

Or pass them into `FlockAgent(modules={...})` directly.

---

## 3. Ordering

Modules run in the order they were added.  Use this to your advantage (e.g. log metrics *after* output is printed).

---

## 4. Writing Your Own

1. Subclass `FlockModule`.
2. Implement any subset of the lifecycle hooks.
3. Optionally create a `FlockModuleConfig` Pydantic model.
4. Register via `@flock_component` so it serialises nicely.

---

## 5. Best Practices

* Keep modules **stateless** or store state in the provided `context`.
* Perform long-running or blocking work in the async hooks.
* Use configurability (`*Config`) to avoid hard-coding behaviour.

---

Next up: [Tools](tools.md).

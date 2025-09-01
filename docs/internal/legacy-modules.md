---
hide: # Optional: Hide table of contents on simple pages
  - toc
---

# Utility Components (Legacy Modules)

Flock now uses a unified component system. What used to be called "modules" are covered by Utility components that hook into the agent lifecycle and provide cross‑cutting behavior (output formatting, metrics, memory, etc.).

---

## 1. Anatomy (Modern)

```python
from flock.core.component.agent_component_base import AgentComponent

class MyUtility(AgentComponent):
    async def on_pre_evaluate(self, agent, inputs, context):
        return inputs  # optional input transform

    async def on_post_evaluate(self, agent, inputs, context, result):
        return result  # optional result transform

    async def terminate(self, agent, inputs, result, context):
        ...  # cleanup
```

Utility components can expose a Pydantic `config` model for declarative parameters.

---

## 2. Built-in Utility Components

| Module | Purpose |
| ------ | ------- |
| `OutputUtilityComponent` | Pretty-prints results to the console via *Rich*. |
| `MetricsUtilityComponent` | Records latency & token metrics, raises alerts. |

Attach utility components either during construction or later:

```python
agent = FlockFactory.create_default_agent(...)
agent.add_component(OutputUtilityComponent(name="output", config=OutputUtilityConfig(render_table=True)))
```

Or pass them into `FlockAgent(components=[...])` directly.

---

## 3. Ordering

Components run in the order they were added. Use this to your advantage (e.g., log metrics after output is printed).

---

## 4. Writing Your Own

1. Subclass `AgentComponent`.
2. Implement any subset of lifecycle hooks.
3. Optionally create a Pydantic `AgentComponentConfig`.
4. Register via `@flock_component` for discovery and serialization.

---

## 5. Best Practices

* Keep utilities **stateless** or store state in the provided `context`.
* Perform long-running or blocking work in the async hooks.
* Use configurability (`*Config`) to avoid hard-coding behaviour.

---

Next up: [Tools](../components/tools.md).

---
hide: # Optional: Hide table of contents on simple pages
  - toc
---

# Components Overview 🧩

Flock uses a unified component system: every agent has a single list `agent.components` that may include any of the following:

| Component Type | Purpose | Base Class |
| -------------- | ------- | ---------- |
| **Evaluation** | Implements an agent’s core logic (LLM/DSPy or custom code). | `EvaluationComponent` |
| **Routing** | Chooses the next agent in a workflow (static, conditional, LLM-based). | `RoutingComponent` |
| **Utility** | Cross-cutting concerns: output formatting, metrics, memory, etc. | `AgentComponent` |

Tools are simple callables (or MCP tools) that evaluators may invoke; register them via `@flock_tool`.

Learn more:

* [Evaluation Components](evaluators.md)
* [Utility Components](utility.md)
* [Tools](tools.md)

---

## Version Compatibility

All core component base classes follow **Semantic Versioning**.  Adding new optional hook methods counts as a *minor* version bump, so custom components will keep working.

---

## Lifecycle Hooks

All components inherit from `AgentComponent` and can implement lifecycle hooks:

- `on_initialize(agent, inputs, context)`
- `on_pre_evaluate(agent, inputs, context)`
- `on_post_evaluate(agent, inputs, context, result)`
- `terminate(agent, inputs, result, context)`
- `on_error(agent, inputs, context, error)`

Evaluation components also implement `evaluate_core(...)`.

---

Continue reading the dedicated pages for implementation details.

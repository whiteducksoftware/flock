---
hide: # Optional: Hide table of contents on simple pages
  - toc
---

# Components Overview 🧩

Components are the **plug-in** architecture that powers extensibility in Flock.  They allow you to add behaviour without rewriting agent code.

| Component Type | Purpose | Base Class |
| -------------- | ------- | ---------- |
| **Evaluator** | Implements an agent's core logic.  Often calls an LLM but could be pure Python. | `FlockEvaluator` |
| **Module** | Hooks into the agent lifecycle for cross-cutting concerns (metrics, output formatting, memory, etc.). | `FlockModule` |
| **Tool** | A single callable that an evaluator may invoke to access external functionality (web search, DB query, script execution…). | Registered via `@flock_tool` |

Each component type is described in its own page:

* [Evaluators](evaluators.md)
* [Modules](modules.md)
* [Tools](tools.md)

---

## Version Compatibility

All core component base classes follow **Semantic Versioning**.  Adding new optional hook methods counts as a *minor* version bump, so custom components will keep working.

---

## Lifecycle Hook Matrix

| Stage | Evaluator | Module |
| ----- | --------- | ------ |
| `initialize` | ❌ (Evaluator created beforehand) | ✅ |
| `evaluate` | ✅ | ✅ (wrap/observe) |
| `terminate` | ❌ | ✅ |
| `on_error` | ❌ | ✅ |

Tools do not participate in hooks; they are invoked directly by the evaluator.

---

Continue reading the dedicated pages for implementation details.

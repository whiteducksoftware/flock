---
hide:
  - toc
---

# Basic Concepts

If you're brand-new to Flock, start here.  This page gives you a *glossary-level* overview; detailed deep-dives live in the **Core Concepts** section.

| Term | One-liner |
| ---- | --------- |
| **Flock** | The orchestrator that owns agents & context and starts runs. |
| **FlockAgent** | Declarative spec of a single task (input → output). |
| **Evaluator** | Executes agent logic (LLM call, rule engine, etc.). |
| **Module** | Lifecycle plug-in that adds behaviour (metrics, memory…). |
| **Router** | Chooses the next agent, enabling branching workflows. |
| **Tool** | Independent function an evaluator can call. |
| **Context** | Key-value store + history shared across agents. |

---

## Next Steps

* Follow the [Quick Start](quickstart.md) to build your first agent.
* Dive into the full explanations in **Core Concepts**:
  * [Agents](../core-concepts/agents.md)
  * [Declarative programming](../core-concepts/declarative.md)
  * [Workflows](../core-concepts/workflows.md) 
# Welcome to Flock

> **Stop engineering prompts. Start declaring contracts.**

Flock is a production-focused framework for orchestrating AI agents through **declarative type contracts** and **blackboard architecture**—proven patterns from distributed systems and classical AI, now applied to modern LLMs.

---

## Why Flock?

### 🎯 Type-Safe Coordination
Stop hoping for valid JSON. Declare your agent contracts with Pydantic models and let Flock enforce them at runtime.

### 🔄 Blackboard Architecture
No rigid graphs. Agents subscribe to artifact types and coordinate through a shared workspace—add new agents without rewiring.

### 👁️ Built-in Observability
OpenTelemetry + DuckDB tracing captures every operation with full I/O. Debug in minutes, not hours.

### 🛡️ Production-Ready
Circuit breakers, visibility controls, resource limits, and comprehensive testing—700+ tests ensure reliability.

---

## Quick Example

```python
from flock import Flock
from pydantic import BaseModel

# Define your data contracts
class BugReport(BaseModel):
    description: str
    severity: str

class Diagnosis(BaseModel):
    root_cause: str
    fix_suggestion: str

# Create orchestrator
flock = Flock("openai/gpt-4.1")

# Declare agent with type contracts
flock.agent("diagnostician") \
    .description("Analyze bug reports and suggest fixes") \
    .consumes(BugReport) \
    .publishes(Diagnosis)

# Publish and let agents coordinate
await flock.publish(BugReport(
    description="App crashes when clicking save",
    severity="critical"
))
await flock.run_until_idle()

# Get results with type safety
diagnoses = await flock.get_all(Diagnosis)
```

---

## Key Features

### Declarative Type Contracts
- **No prompt engineering** - Define contracts with Pydantic
- **Runtime validation** - Survives model upgrades gracefully
- **Type safety** - Catch errors at development time

### Blackboard Coordination
- **Decoupled agents** - No explicit wiring between agents
- **Dynamic topology** - Add agents at runtime (O(1) vs O(n))
- **Opportunistic parallelism** - Automatic fanout via subscriptions

### Production Observability
- **Full I/O capture** - Every input/output stored in DuckDB
- **Causal lineage** - Track artifacts across agent cascades
- **Root cause analysis** - Debug failures in minutes

### Enterprise Features
- **Visibility controls** - Public, Private, Tenant, Label-based
- **Circuit breakers** - Cost protection by default
- **Resource limits** - Prevent runaway executions
- **Multi-tenancy** - Zero-trust agent scheduling

---

## Get Started

<div class="grid cards" markdown>

-   :material-clock-fast:{ .lg .middle } __Quick Start__

    ---

    Install Flock and run your first agent in 5 minutes

    [:octicons-arrow-right-24: Get started](getting-started/installation.md)

-   :material-book-open-variant:{ .lg .middle } __User Guide__

    ---

    Learn about agents, blackboard, visibility, and tracing

    [:octicons-arrow-right-24: Read the guide](guides/agents.md)

-   :material-code-braces:{ .lg .middle } __API Reference__

    ---

    Complete API documentation for Flock

    [:octicons-arrow-right-24: API docs](reference/api.md)

-   :material-chart-line:{ .lg .middle } __Examples__

    ---

    See Flock in action with real-world examples

    [:octicons-arrow-right-24: Browse examples](https://github.com/whiteducksoftware/flock/tree/main/examples)

</div>

---

## Architecture Highlights

**Blackboard Pattern** (Hearsay-II from 1970s, modernized for LLMs)
```
┌─────────────────────────────────────────────┐
│         Blackboard (Typed Artifacts)        │
│  ┌──────┐ → ┌──────┐ → ┌──────┐ → ┌──────┐│
│  │ Idea │   │Movie │   │Script│   │Review││
│  └──────┘   └──────┘   └──────┘   └──────┘│
└─────────────────────────────────────────────┘
      ↑           ↑           ↑           ↑
  Agent A     Agent B     Agent C     Agent D
  (produce)   (consume    (consume    (consume
              & produce)  & produce)  & produce)
```

**Key Differentiators:**
- O(n) subscriptions vs O(n²) graph edges (scales to 100+ agents)
- 99% parallel efficiency with automatic fanout
- Built-in security model (visibility-based access control)
- Complete execution traces (OpenTelemetry + DuckDB)

---

## Community & Support

- **GitHub:** [whiteducksoftware/flock](https://github.com/whiteducksoftware/flock)
- **PyPI:** [flock-core](https://pypi.org/project/flock-core/)
- **Issues:** [Report bugs](https://github.com/whiteducksoftware/flock/issues)
- **Discussions:** [Ask questions](https://github.com/whiteducksoftware/flock/discussions)

---

## License

Flock is open-source software licensed under the MIT License.

Built with ❤️ by [white duck GmbH](https://whiteduck.de)

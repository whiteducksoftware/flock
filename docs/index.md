# Flock: Declarative Blackboard Multi-Agent Orchestration

> **Stop engineering prompts. Start declaring contracts.**

Flock is a production-focused framework for orchestrating AI agents through **declarative type contracts** and **blackboard architecture**—proven patterns from distributed systems, decades of experience with microservice architectures, and classical AI—now applied to modern LLMs.

---

## Quick Start

```bash
pip install flock-core
export OPENAI_API_KEY="sk-..."
export DEFAULT_MODEL="openai/gpt-4.1"
```

```python
import os
import asyncio
from pydantic import BaseModel, Field
from flock import Flock, flock_type

# Define typed artifacts
@flock_type
class CodeSubmission(BaseModel):
    code: str
    language: str

@flock_type
class BugAnalysis(BaseModel):
    bugs_found: list[str]
    severity: str = Field(pattern="^(Critical|High|Medium|Low|None)$")
    confidence: float = Field(ge=0.0, le=1.0)

# Create the blackboard
flock = Flock(os.getenv("DEFAULT_MODEL", "openai/gpt-4.1"))

# Agents subscribe to types (NO graph wiring!)
bug_detector = flock.agent("bug_detector").consumes(CodeSubmission).publishes(BugAnalysis)

# Run with real-time dashboard
async def main():
    await flock.serve(dashboard=True)

asyncio.run(main())
```

---

## Why Flock?

Flock makes different architectural choices than traditional multi-agent frameworks:

- **✅ Declarative Type Contracts** - No 500-line prompts, schemas define behavior
- **✅ Blackboard Architecture** - Loose coupling through type subscriptions
- **✅ Automatic Parallelization** - Concurrent execution by default
- **✅ Built-in Security** - Zero-trust visibility controls
- **✅ Production Observability** - Real-time dashboard + OpenTelemetry tracing

---

## Key Features

### Type-Safe Agent Communication

```python
@flock_type
class PatientDiagnosis(BaseModel):
    condition: str = Field(min_length=10)
    confidence: float = Field(ge=0.0, le=1.0)
    recommended_treatment: list[str] = Field(min_length=1)
    follow_up_required: bool
```

### Zero-Trust Security

```python
# HIPAA compliance built-in
agent.publishes(MedicalRecord, visibility=PrivateVisibility(agents={"physician"}))

# Multi-tenancy
agent.publishes(CustomerData, visibility=TenantVisibility(tenant_id="customer_123"))
```

### Real-Time Dashboard

Start the dashboard with one line:

```python
await flock.serve(dashboard=True)
```

---

## Next Steps

<div class="grid cards" markdown>

-   :rocket: **Getting Started**

    ---

    Learn how to install Flock and create your first agent

    [Installation →](getting-started/installation.md){ .md-button }

-   :material-school: **Tutorials**

    ---

    Step-by-step tutorials from basics to advanced patterns

    [Tutorials →](tutorials/index.md){ .md-button }

-   :books: **User Guides**

    ---

    In-depth documentation on agents, blackboard, and patterns

    [Guides →](guides/index.md){ .md-button }

-   :material-api: **API Reference**

    ---

    Complete API documentation for all modules

    [Reference →](reference/index.md){ .md-button }

</div>

---

## Community & Support

- **GitHub:** [whiteducksoftware/flock](https://github.com/whiteducksoftware/flock)
- **PyPI:** [flock-core](https://pypi.org/project/flock-core/)
- **Issues:** [Report bugs & request features](https://github.com/whiteducksoftware/flock/issues)
- **Discussions:** [Community discussions](https://github.com/whiteducksoftware/flock/discussions)

---

<div align="center">

**Built with ❤️ by white duck GmbH**

**Version:** 0.5.0 | **License:** MIT | **Python:** 3.10+

</div>

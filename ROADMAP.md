# 🗺️ Flock Roadmap to 1.0

**Building Enterprise Infrastructure for AI Agents**

This roadmap outlines Flock's path from v0.5.0 (production-ready core) to v1.0 (enterprise-complete) by Q4 2025.

We're confident to deliver all enterprise features in a single release: **Flock 1.0 in Q4 2025**.

---

## ✅ What's Already Production-Ready (v0.5.0)

### Core Framework
- [x] Blackboard orchestrator with typed artifacts
- [x] Declarative agent subscriptions (no graph wiring)
- [x] Parallel + sequential execution (automatic)
- [x] Zero-trust security (5 visibility types)
- [x] Circuit breakers and feedback loop prevention
- [x] 743 tests with 77.65% coverage (86-100% on critical paths)
- [x] Type-safe retrieval API (`get_by_type()`)

### Observability
- [x] OpenTelemetry distributed tracing
- [x] DuckDB trace storage (AI-queryable)
- [x] Real-time dashboard with WebSocket streaming
- [x] 7-mode trace viewer (Timeline, RED metrics, Dependencies, SQL)
- [x] Service filtering and CSV export
- [x] Full I/O capture with JSON viewer

### Developer Experience
- [x] MCP integration (Model Context Protocol)
- [x] Best-of-N execution
- [x] Batch processing and join operations
- [x] Conditional consumption (`where=lambda`)
- [x] Rich console output and FastAPI service
- [x] Keyboard shortcuts (WCAG 2.1 AA compliant)

---

## 🧱 0.5.0 Beta Initiatives (In Flight)

These are the features we are actively building for the 0.5.0 beta. Follow the linked GitHub issues to track progress:

### Core data & governance
- [#271](https://github.com/whiteducksoftware/flock/issues/271) — Durable blackboard persistence backends.
- [#274](https://github.com/whiteducksoftware/flock/issues/274) — Serialization/export of blackboard state and registered agents.
- [#273](https://github.com/whiteducksoftware/flock/issues/273) — Structured feedback channel for agent outputs.
- [#281](https://github.com/whiteducksoftware/flock/issues/281) — Human-in-the-loop approval flow.

### Execution patterns & scheduling
- [#282](https://github.com/whiteducksoftware/flock/issues/282) — Fan-out / fan-in workflow helpers.
- [#283](https://github.com/whiteducksoftware/flock/issues/283) — Time-based scheduling primitives.

### REST access & integrations
- [#286](https://github.com/whiteducksoftware/flock/issues/286) — Custom REST endpoint DSL.
- [#287](https://github.com/whiteducksoftware/flock/issues/287) — Synchronous publish endpoint (single and batch).
- [#288](https://github.com/whiteducksoftware/flock/issues/288) — Correlation-aware status endpoint.
- [#289](https://github.com/whiteducksoftware/flock/issues/289) — Webhook notifications for published artifacts.
- [#290](https://github.com/whiteducksoftware/flock/issues/290) — Schema discovery endpoints.
- [#291](https://github.com/whiteducksoftware/flock/issues/291) — REST idempotency keys and error model.
- [#292](https://github.com/whiteducksoftware/flock/issues/292) — Artifact listing and filtering API.
- [#293](https://github.com/whiteducksoftware/flock/issues/293) — OpenAPI specification generation.

### Documentation & onboarding
- [#270](https://github.com/whiteducksoftware/flock/issues/270) — MkDocs-powered documentation site.
- [#269](https://github.com/whiteducksoftware/flock/issues/269) — Revamped example catalog.

---

## 🚀 Flock 1.0 (Target Q4 2025)

Once the 0.5.0 beta ships, we will focus on the remaining enterprise capabilities before the 1.0 release.

### Reliability & operations
- [#277](https://github.com/whiteducksoftware/flock/issues/277) — Advanced retry strategy, dead-letter queues, per-agent circuit breakers.
- [#278](https://github.com/whiteducksoftware/flock/issues/278) — Kafka-backed event backbone with replay and time-travel debugging.
- [#279](https://github.com/whiteducksoftware/flock/issues/279) — Kubernetes deployment tooling (Helm charts, auto-scaling).
- [#294](https://github.com/whiteducksoftware/flock/issues/294) — Workflow lifecycle controls (pause, resume, cancel).

### Platform validation & quality
- [#275](https://github.com/whiteducksoftware/flock/issues/275) — Benchmarking suite against industry workloads.
- [#276](https://github.com/whiteducksoftware/flock/issues/276) — Automated evaluation harness for datasets/metrics.
- [#284](https://github.com/whiteducksoftware/flock/issues/284) — Test coverage expansion to 85%+ with 1,000 tests.
- [#285](https://github.com/whiteducksoftware/flock/issues/285) — Production validation pilots with launch partners.

### Security & access
- [#280](https://github.com/whiteducksoftware/flock/issues/280) — Authentication & authorization (OAuth/OIDC, API keys).

Stay tuned to the issue tracker for milestone updates. We'll publish detailed release notes as each cluster of features lands.

---

## Example: Multi-Modal Clinical Decision Support

```python
import os
from flock import Flock, flock_type
from flock.core.visibility import PrivateVisibility, TenantVisibility, LabelledVisibility
from flock.identity import AgentIdentity
from pydantic import BaseModel

@flock_type
class PatientScan(BaseModel):
    patient_id: str
    scan_type: str
    image_data: bytes

@flock_type
class XRayAnalysis(BaseModel):
    findings: list[str]
    confidence: float

@flock_type
class LabResults(BaseModel):
    markers: dict[str, float]

@flock_type
class Diagnosis(BaseModel):
    condition: str
    reasoning: str
    confidence: float

# Create HIPAA-compliant blackboard
flock = Flock(os.getenv("DEFAULT_MODEL", "openai/gpt-4.1"))

# Radiologist with privacy controls
radiologist = (
    flock.agent("radiologist")
    .consumes(PatientScan)
    .publishes(
        XRayAnalysis,
        visibility=PrivateVisibility(agents={"diagnostician"})  # HIPAA!
    )
)

# Lab tech with multi-tenancy
lab_tech = (
    flock.agent("lab_tech")
    .consumes(PatientScan)
    .publishes(
        LabResults,
        visibility=TenantVisibility(tenant_id="patient_123")  # Isolation!
    )
)

# Diagnostician with explicit access
diagnostician = (
    flock.agent("diagnostician")
    .identity(AgentIdentity(name="diagnostician", labels={"role:physician"}))
    .consumes(XRayAnalysis, LabResults)  # Waits for BOTH
    .publishes(
        Diagnosis,
        visibility=LabelledVisibility(required_labels={"role:physician"})
    )
)

# Run with tracing
async with flock.traced_run("patient_123_diagnosis"):
    await flock.publish(PatientScan(patient_id="123", ...))
    await flock.run_until_idle()

    # Get diagnosis (type-safe retrieval)
    diagnoses = await flock.store.get_by_type(Diagnosis)
```

---
title: Product Roadmap
description: Flock's path from v0.5.0 to v1.0 - enterprise features, production readiness, and future vision
tags:
  - roadmap
  - future
  - community
search:
  boost: 1.2
---

# 🗺️ Flock Roadmap to 1.0

**Building Enterprise Infrastructure for AI Agents**

This roadmap outlines Flock's path from v0.5.0 (production-ready core) to v1.0 (enterprise-complete) by Q4 2025. We're confident we can deliver the remaining enterprise features by **Q4 2025**.

---

## ✅ What's Already Production-Ready (v0.5.0)

### Core Framework
- Blackboard orchestrator with typed artifacts
- Declarative agent subscriptions (no graph wiring)
- Automatic parallel + sequential execution
- Zero-trust visibility model (5 visibility types)
- Circuit breakers and self-trigger prevention
- 743 tests with 77.65% coverage (86-100% on critical paths)
- Type-safe retrieval API (`get_by_type()`)

### Observability
- OpenTelemetry distributed tracing
- DuckDB trace storage (AI-queryable)
- Real-time dashboard with WebSocket streaming
- 7-mode trace viewer (Timeline, RED metrics, Dependencies, SQL)
- Service filtering and CSV export
- Full I/O capture with JSON viewer

### Developer Experience
- MCP integration (Model Context Protocol)
- Best-of-N execution
- Batch processing and join operations
- Conditional consumption (`where=lambda`)
- Rich console output and FastAPI service
- Keyboard shortcuts (WCAG 2.1 AA compliant)

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

---

## 📌 Staying in the Loop

- ⭐ Star the [GitHub repository](https://github.com/whiteducksoftware/flock)
- 🗓️ Join community calls and roadmap discussions (announced in Discord/Slack)
- 💬 Open issues or discussions to influence priorities
- 📨 Contact [support@whiteduck.de](mailto:support@whiteduck.de) for enterprise questions

We’ll publish release notes as each milestone lands and keep this document in sync with the public issue tracker.

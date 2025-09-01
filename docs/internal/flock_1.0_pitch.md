
# Flock 1.0 — Project Plan

**Tagline:** **CONTRACT. REACT. DEPLOY.**
**Subline:** Typed events. Durable agents.

---

## 1) Project pitch

Current AI agent frameworks are built on the wrong primitives. They expect you to:

* Write in natural language instead of defining interfaces
* Draw graphs to express simple handoffs
* Re‑invent distributed systems badly
* Choose between developer speed and production reliability

**We do not build APIs with prose. We use contracts, schemas, and types.**
**Flock 1.0** applies the same discipline to AI systems.

### Agents as microservices

**Contract‑first:** Inputs and outputs are strict schemas. The runtime enforces them at the boundary. Model outputs must conform by decoding, not by fragile parsing.

**Reactive by design:** Agents compose by subscription. `B` subscribes to `A`. When `A` emits a typed event, `B` reacts. No DAG authoring. Graphs exist only as an observability view.

**Reliability on a switch:** Local mode for speed. Flip a flag to get durable execution with retries, backoff, timeouts, and crash‑proof progress (Temporal). Same code. Better semantics.

**Package and ship:** Agents are packaged as portable images with their contracts, policies, and capabilities. Pull from a registry. Compose with a simple file. Run anywhere.

---

## 2) Core philosophy

1. **Agents are microservices that can proactively call other microservices.**
   In mature microservice landscapes no one authors DAGs to wire services. Services talk via events and RPC. “Infinite loops” are addressed by idempotency, backpressure, circuit breakers, and policy. Apply the same here.

2. **Contracts at the boundary. Events in the middle.**
   All agent inputs and outputs use strict schemas. All interactions flow through typed events with envelopes that carry identity, causation, budgets, and policy context.

3. **Reliability is a foundation, not an add‑on.**
   Delivery semantics are explicit. At‑most‑once for local dev. At‑least‑once with idempotency for reliable ops. Durable orchestration for long‑running work.

4. **Open standards over bespoke glue.**
   JSON Schema for contracts, CloudEvents for envelopes, AsyncAPI/OpenAPI for interfaces, OCI for packaging, OpenTelemetry for traces, MCP for tools, OPA for policy.

5. **DX that respects senior engineers.**
   Author with types and subscriptions. Inspect as graphs only when debugging. Strong defaults, clear failure modes, predictable costs.

---

## 3) High‑level architecture

### 3.1 System overview

```
+--------------------------------------------------------------+
|                          Dev Experience                      |
|  - SDK (Python first)  - CLI  - Web UI  - Templates/Scaffolds|
+--------------------------+-----------------------------------+
                           |
                           v
+--------------------------------------------------------------+
|                        Control Plane                          |
|  - Flock Registry (OCI)   - Flock Compose loader              |
|  - Policy Engine (OPA)    - Identity/Signing (Cosign/SLSA)    |
|  - Config & Secrets       - Version/Compatibility Manager     |
+--------------------------+-----------------------------------+
                           |
                           v
+--------------------------------------------------------------+
|                          Data Plane                           |
|  Runtime Core:                                               |
|   - Event Router (typed, CloudEvents envelope)               |
|   - Subscription Registry (type-checked)                     |
|   - Reliability Adapters:                                    |
|       Local | Reliable (at-least-once) | Durable (Temporal)  |
|   - Capability Mounts (MCP servers, tools)                   |
|   - Backpressure, Rate limits, Circuit breakers              |
|   - Observability (OpenTelemetry)                            |
+--------------------------+-----------------------------------+
                           |
                           v
+--------------------------------------------------------------+
|                 Packaging and Supply Chain                    |
|  Flock Image (OCI artifact):                                 |
|   - Code + Model adapters + Component stack                  |
|   - Contracts (JSON Schema) + Interfaces (AsyncAPI/OpenAPI)  |
|   - Policies (OPA) + SBOM (CycloneDX) + Attestations         |
|   - Capability manifest (MCP mounts, tools)                  |
+--------------------------------------------------------------+
                           |
                           v
+--------------------------------------------------------------+
|                         Infrastructure                        |
|  - Kubernetes + Knative/KEDA for autoscale                   |
|  - Temporal Server for durable mode                          |
|  - Any OCI registry (GHCR/ECR/GCR/ACR)                       |
+--------------------------------------------------------------+
```

### 3.2 Key abstractions

* **Agent Contract**
  JSON Schema definitions for `Input` and `Output`. Versioned with semver. Optional adapters to bridge versions. Contracts are the source of truth for validation, docs, codegen, and type checking of subscriptions.

* **Envelope**
  CloudEvents‑style metadata: `id`, `source`, `type`, `time`, `schema_id`, `schema_version`, `causation_id`, `attempt`, `budget`, `policy_tags`. Payload is a validated `Output` type. Envelopes enable tracing, retries, loop detection, idempotency, and governance.

* **Subscription**
  A reactive link between producer and consumer with predicate filters on payload type, version, tags, and policies. Delivery semantics and retry policy are declared per subscription. Subscriptions are the only composition primitive.

* **Component stack**
  Everything an agent does is a component: pre‑filters, judges, memory, tools, optimizers, policy guards. Components are pure functions over typed inputs and outputs. This maps cleanly to current Flock.

* **Capabilities**
  Per‑agent tool and MCP mounts with explicit scopes. Capabilities are declared in the Flock Image manifest and enforced by the policy engine. Least privilege by default.

* **Reliability tiers**

  * Local: in‑process event router with at‑most‑once delivery
  * Reliable: at‑least‑once delivery with idempotency and backoff
  * Durable: Temporal workflows/activities for crash‑proof and long‑running work

* **Observability**
  OpenTelemetry spans for every hop with `event_id` and `causation_id`, model choice, tokens, latency, cost, policy decisions, and validation results. The UI renders the **derived run graph** from real events rather than a designed DAG.

### 3.3 Packaging model

* **Flock Image (OCI)**
  A portable artifact that includes:

  * Contracts and interface specs
  * Component stack configuration
  * Capability manifest (MCP, tools)
  * Policy bundle (OPA)
  * SBOM and signed attestations
  * Optional datasets or embeddings as separate layers

* **Flock Compose (YAML)**
  A declarative file that wires subscriptions, sets delivery semantics, policies, budgets, and SLOs. Checked into source control. Deployed by CLI or UI.

* **Flock Registry**
  Any OCI registry can host Flock Images. A lightweight index maps names to digests and exposes trust metadata. Admission checks verify signatures, SLSA level, and policy compliance at pull or deploy time.

### 3.4 Data plane details

* **Event Router** routes envelopes to subscribers based on payload type, version, and predicates.
* **Backpressure** clamps fan‑out and queue depth. Policies decide drop, delay, or reroute.
* **Loop control** uses causation chains and hop limits.
* **Budget awareness** tracks cost and latency. Subscriptions can downshift models or short‑circuit when budgets are exhausted.
* **DLQ** captures irreparable events with full context for replay or triage.

### 3.5 Governance and security

* **Policy Engine (OPA)** enforces capability scopes, data egress, PII rules, and budget limits.
* **Supply chain** uses CycloneDX SBOMs, Cosign signatures, and in‑toto attestations for each Flock Image.
* **Isolation** per‑agent secrets, sandboxed tool calls, and rate limits.

### 3.6 Interoperability posture

* **Standards first:** JSON Schema, CloudEvents, AsyncAPI/OpenAPI, OCI, OTel, MCP, OPA.
* **Adapters** for external ecosystems: mount LangGraph nodes or AutoGen actors as foreign agents behind contracts; export compatible PydanticAI components.
* **Transport flexibility:** in‑process router for dev, pluggable brokers for scale when needed.

---

## 4) Component plan

### 4.1 Control‑plane components

* **CLI and SDK (Python first)**
  Scaffolds new agents from contracts. Validates Compose. Pulls and runs Flock Images. Generates client stubs from interfaces.
  **CLI vibe:** `flock init`, `flock build`, `flock pull`, `flock up`, `flock run --durable temporal`, `flock logs`.

* **Flock Registry Service**
  Wraps an OCI registry with indexing, search, signatures, SBOM fetch, and policy checks.

* **Policy Service**
  Hosts OPA bundles. Integrates with identity to evaluate capability requests at runtime.

* **Compatibility and Version Manager**
  Tracks contract versions and available adapters. Validates subscription compatibility at deploy time.

### 4.2 Data‑plane components

* **Runtime Core**
  In‑process event router, subscription registry, queue manager, backpressure controller, retry engine, idempotency cache.

* **Reliability Adapters**

  * Reliable mode: storage for pending deliveries and idempotency keys
  * Durable mode: Temporal workflow/activity wrappers, state capture, replay mapping between envelopes and workflow history

* **Capability Manager**
  MCP client and tool loaders with per‑agent scopes and rate limits. Emits audit logs.

* **Evaluator and Judge components**
  Structured output validators, repairers, and ensemble judges for quality gates.

* **Memory components**
  Short‑term, episodic, semantic, and procedural memories with typed access. Optional external stores.

* **Observability adapters**
  OpenTelemetry exporters. Event taps for the derived run graph in the UI.

### 4.3 Packaging components

* **Image Builder**
  Packs an agent codebase, contracts, components, policies, and manifests into an OCI artifact. Writes SBOM and signatures.

* **Compose Orchestrator**
  Applies Flock Compose to spin up agents, attach subscriptions, and configure reliability tiers and policies.

---

## 5) How this maps to Flock today

* **Component model** → reuse directly. Agents remain stacks of components.
* **Evaluators and DSPy** → become Judges and Optimizers that can run inline or offline.
* **Temporal integration** → drives the Durable tier with minimal surface change.
* **REST/UI/CLI** → evolve to include Flock Image build, pull, verify, and Compose deploy.
* **MCP support** → becomes the standard capability mount per agent.
* **Tracing and metrics** → align to OpenTelemetry and enrich with envelope metadata.

**Migration:** keep Flock agents source‑compatible. Add packaging and subscription wiring. Introduce contracts as first‑class and CloudEvents envelopes on the wire.

---

## 6) Phased plan and discussion prompts

### Phase 0 — Decision doc

* Lock pillars: Contracts, Subscriptions, Reliability tiers, Packaging
* Approve standards set and naming for artifacts (Flock Image, Flock Compose)

### Phase 1 — Minimal reactive runtime

* In‑process event router, typed envelopes, subscription registry
* Local mode only; OTel traces; derived graph view in UI

### Phase 2 — Contract discipline

* JSON Schema generation and validation
* Structured outputs at model boundary
* Type‑checked subscription wiring with adapters

### Phase 3 — Flock Compose and CLI

* Compose spec for subscriptions, policies, and SLOs
* CLI commands: `flock init|build|pull|up|run|logs`

### Phase 4 — Packaging and Registry

* Flock Image builder with SBOM and signing
* Registry index and admission checks

### Phase 5 — Reliability tiers

* Reliable mode with at‑least‑once and idempotency
* Durable mode with Temporal, long‑running workflows, memo, replay

### Phase 6 — Governance

* OPA policy bundles; capability scopes for MCP/tools
* Budget enforcement and egress rules

### Phase 7 — Optimizers and Evals

* Judges, repairers, DSPy optimizer mode, A/B shadows

### Phase 8 — Autoscale and infra polish

* Knative/KEDA adapters; per‑subscription backpressure policies
* Cost dashboards and SLO compliance views

**Discussion prompts:**

* Which standards are mandatory at 1.0 vs optional plug‑ins
* Minimal viable fields in the Flock Image manifest
* Default delivery semantics for subscriptions in local vs reliable modes
* What gets signed and when
* Where to draw the line between framework and platform

---

## 7) Non‑goals for 1.0

* No visual graph authoring. Graphs are derived from events for debugging only
* No bespoke brokers; pluggable adapters later if needed
* No hard dependency on a specific cloud; keep OCI and OTel portable

---

## 8) Risks and mitigations

* **Schema drift across teams**
  Mitigation: versioned contracts, adapter registry, subscription compatibility checks at deploy time

* **Event storms and feedback loops**
  Mitigation: hop limits, backpressure, rate limits, DLQ with replay

* **Supply chain trust**
  Mitigation: SBOM, signatures, attestations, and admission checks by default

* **DX overload**
  Mitigation: one path that always works. Start local with `flock up`. Flip `--durable` when needed

---

## 9) Versioning & naming

* **Flock 1.0** names the standard: contracts + subscriptions + reliability tiers + packaging
* Artifacts: **Flock Image** (OCI), **Flock Compose** (YAML), **Flock Registry** (index atop any OCI registry)
* CLI: `flock` (reserve `flockctl` if you want an admin split later)

---

## 10) Acceptance bar for 1.0

* Author agents with contracts and component stacks
* Wire them with subscriptions only
* Package as Flock Images
* Deploy a Flock Compose file locally
* Toggle reliable and durable modes without code changes
* Observe the derived run graph with per‑hop traces
* Enforce an OPA policy and a capability scope
* Pass a set of golden tests and property‑based invariants on outputs

---



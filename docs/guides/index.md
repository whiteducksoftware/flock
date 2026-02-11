# User Guides

Comprehensive guides for building production-ready multi-agent systems with Flock.

---

## 📚 Core Guides

<div class="grid cards" markdown>

-   **🤖 Agents**

    ---

    Create specialized agents with type subscriptions, custom evaluation, and lifecycle hooks.

    [:octicons-arrow-right-24: Agent Guide](agents.md)

-   **📋 Blackboard**

    ---

    Master the shared artifact workspace that enables emergent agent collaboration.

    [:octicons-arrow-right-24: Blackboard Guide](blackboard.md)

-   **📦 Top-Level Imports**

    ---

    Convenient imports for DSPyEngine, adapters, components, and more from the root namespace.

    [:octicons-arrow-right-24: Imports Guide](imports.md)

-   **🔒 Visibility Controls**

    ---

    Control data access with public, private, tenant-based, and label-based visibility.

    [:octicons-arrow-right-24: Visibility Guide](visibility.md)

-   **📊 Dashboard**

    ---

    Monitor agent execution in real-time with the built-in React dashboard.

    [:octicons-arrow-right-24: Dashboard Guide](dashboard.md)

-   **🌐 REST API**

    ---

    Production-ready HTTP endpoints with OpenAPI documentation for integration.

    [:octicons-arrow-right-24: REST API Guide](rest-api.md)

-   **🔧 Server Components**

    ---

    Extend Flock's HTTP API with custom middleware, authentication, and routes.

    [:octicons-arrow-right-24: Server Components Guide](server-components.md)

-   **🤫 Silent Mode**

    ---

    Suppress terminal output when running Flock as a service or in production.

    [:octicons-arrow-right-24: Silent Mode Guide](silent-mode.md)

</div>

---

## 🔗 Integrations

<div class="grid cards" markdown>

-   **🦞 OpenClaw Integration**

    ---

    Use OpenClaw agents as Flock pipeline participants — tools, skills, multi-step reasoning, different models.

    [:octicons-arrow-right-24: OpenClaw Guide](openclaw.md)

</div>

---

## 🖥️ Local Models & Engines

<div class="grid cards" markdown>

-   **🔧 DSPy Engine Deep Dive**

    ---

    Understanding how DSPy signatures work and how the DSPyEngine generates contract-valid artifacts.

    [:octicons-arrow-right-24: DSPy Engine Guide](dspy-engine.md)

-   **🏠 Local Models (Transformers)**

    ---

    Run Flock agents entirely locally using Hugging Face models — no API keys required.

    [:octicons-arrow-right-24: Local Models Guide](local-models.md)

</div>

---

## 🔍 Distributed Tracing

Comprehensive observability with OpenTelemetry and DuckDB.

<div class="grid cards" markdown>

-   **⚡ Quick Start**

    ---

    Enable tracing in 30 seconds and start capturing execution data.

    [:octicons-arrow-right-24: Tracing Quick Start](tracing/tracing-quickstart.md)

-   **🔄 Auto-Tracing**

    ---

    Automatic trace capture for all operations without code changes.

    [:octicons-arrow-right-24: Auto-Tracing Guide](tracing/auto-tracing.md)

-   **📊 Unified Tracing**

    ---

    Wrap workflows in single parent traces for better observability.

    [:octicons-arrow-right-24: Unified Tracing](tracing/unified-tracing.md)

-   **🎯 Effective Usage**

    ---

    Master debugging, optimization, and monitoring techniques.

    [:octicons-arrow-right-24: Using Tracing Effectively](tracing/how_to_use_tracing_effectively.md)

-   **🚀 Production**

    ---

    Best practices for production deployments and monitoring.

    [:octicons-arrow-right-24: Production Tracing](tracing/tracing-production.md)

-   **📖 Reference**

    ---

    Complete trace module and DuckDB schema reference.

    [:octicons-arrow-right-24: Trace Module](tracing/trace-module.md)

</div>

---

## Guide Categories

### Agent Development
- **[Creating Agents](agents.md)** - Basic agent setup and configuration
- **[Declaring Consumption](agents.md#declaring-consumption)** - Type subscriptions and patterns
- **[Advanced Subscriptions](agents.md#advanced-subscriptions)** - Conditional consumption and filtering
- **[Agent Builder API](agents.md#agent-builder-api)** - Complete reference

### Blackboard Patterns
- **[Publishing to Blackboard](blackboard.md)** - Add artifacts and data flows
- **[Batching Pattern](blackboard.md)** - Parallel execution optimization
- **[Multi-Agent Coordination](blackboard.md)** - Pipeline architectures
- **[Artifact Lifecycle](blackboard.md)** - Data flow and management

### Visibility & Security
- **[Visibility Overview](visibility.md)** - Understanding visibility controls
- **[Public Artifacts](visibility.md#1-publicvisibility-default)** - Shared across all agents
- **[Tenant Isolation](visibility.md#3-tenantvisibility-multi-tenancy)** - Multi-tenant systems
- **[Label-Based Access](visibility.md#4-labelledvisibility-rbac)** - Fine-grained control
- **[Time-Based Access](visibility.md#5-aftervisibility-time-delayed)** - Temporal constraints

### Observability
- **[REST API](rest-api.md)** - HTTP endpoints for integration and monitoring
- **[Server Components](server-components.md)** - Custom middleware and authentication
- **[Trace Capture](tracing/auto-tracing.md)** - Automatic trace collection
- **[Trace Analysis](tracing/how_to_use_tracing_effectively.md)** - Debugging workflows
- **[Dashboard Viewer](tracing/trace-module.md)** - Visual trace exploration
- **[Production Monitoring](tracing/tracing-production.md)** - Metrics and alerts

---

## Common Tasks

Looking for specific tasks? Here are quick links:

- **Create a new agent** → [Agent Guide](agents.md)
- **Enable parallel execution** → [Batching Pattern](blackboard.md)
- **Debug agent execution** → [Tracing Effectively](tracing/how_to_use_tracing_effectively.md)
- **Add real-time monitoring** → [Dashboard Guide](dashboard.md)
- **Add authentication to API** → [Server Components - Authentication](server-components.md#authenticationcomponent)
- **Configure CORS** → [Server Components - CORS](server-components.md#corscomponent)
- **Integrate with external systems** → [REST API Guide](rest-api.md)
- **Track workflow completion** → [Correlation Status](rest-api.md#correlation-status-workflow-tracking)
- **Implement multi-tenancy** → [Tenant Visibility](visibility.md#3-tenantvisibility-multi-tenancy)
- **Query artifacts** → [Blackboard Guide](blackboard.md)

---

## Best Practices

### Design Patterns
- ✅ Use small, focused agents with single responsibilities
- ✅ Leverage type contracts for implicit coordination
- ✅ Design artifacts as immutable domain events
- ✅ Enable batching for independent parallel work

### Performance
- ✅ Use `run_until_idle()` after batching publishes
- ✅ Enable auto-tracing only in dev/staging
- ✅ Set appropriate trace TTL for storage management
- ✅ Filter trace services to reduce overhead

### Production
- ✅ Implement proper visibility controls
- ✅ Monitor with production tracing
- ✅ Set up alerting on error rates
- ✅ Use correlation IDs for request tracking

---

## Reference Documentation

- **[API Reference](../reference/api.md)** - Complete API documentation
- **[Configuration Reference](../reference/configuration.md)** - All configuration options
- **[Core Concepts](../getting-started/concepts.md)** - Foundational understanding

---

## Need Help?

Can't find what you're looking for?

- 🔍 **Search** - Use the search bar (press `/` to focus)
- 💬 **Ask** - [GitHub Discussions](https://github.com/whiteducksoftware/flock/discussions)
- 🐛 **Report** - [GitHub Issues](https://github.com/whiteducksoftware/flock/issues)

---

**Start with the basics** → [Getting Started](../getting-started/index.md){ .md-button .md-button--primary }

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

-   **🔒 Visibility Controls**

    ---

    Control data access with public, private, tenant-based, and label-based visibility.

    [:octicons-arrow-right-24: Visibility Guide](visibility.md)

-   **📊 Dashboard**

    ---

    Monitor agent execution in real-time with the built-in React dashboard.

    [:octicons-arrow-right-24: Dashboard Guide](dashboard.md)

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
- **[Creating Agents](agents.md#creating-agents)** - Basic agent setup
- **[Type Subscriptions](agents.md#type-subscriptions)** - Consume and publish patterns
- **[Lifecycle Hooks](agents.md#lifecycle-hooks)** - on_initialize, on_terminate
- **[Custom Evaluation](agents.md#custom-evaluation)** - Beyond LLM engines

### Blackboard Patterns
- **[Publishing Artifacts](blackboard.md#publishing-artifacts)** - Add data to blackboard
- **[Batching](blackboard.md#batching-pattern)** - Parallel execution optimization
- **[Artifact Flows](blackboard.md#artifact-flow-patterns)** - Multi-agent pipelines
- **[Querying](blackboard.md#querying-artifacts)** - Search and filter artifacts

### Visibility & Security
- **[Public Visibility](visibility.md#public-visibility)** - Shared artifacts
- **[Private Visibility](visibility.md#private-visibility)** - Agent-specific data
- **[Tenant Isolation](visibility.md#3-tenantvisibility-multi-tenancy)** - Multi-tenant systems
- **[Label-Based Access](visibility.md#4-labelledvisibility-rbac)** - Fine-grained control
- **[Time-Based Access](visibility.md#5-aftervisibility-time-delayed)** - Temporal constraints

### Observability
- **[Trace Capture](tracing/auto-tracing.md)** - Automatic trace collection
- **[Trace Analysis](tracing/how_to_use_tracing_effectively.md)** - Debugging workflows
- **[Dashboard Viewer](tracing/trace-module.md)** - Visual trace exploration
- **[Production Monitoring](tracing/tracing-production.md)** - Metrics and alerts

---

## Common Tasks

Looking for specific tasks? Here are quick links:

- **Create a new agent** → [Agent Guide](agents.md#creating-agents)
- **Enable parallel execution** → [Batching Pattern](blackboard.md#batching-pattern)
- **Debug agent execution** → [Tracing Effectively](tracing/how_to_use_tracing_effectively.md)
- **Add real-time monitoring** → [Dashboard Guide](dashboard.md)
- **Implement multi-tenancy** → [Tenant Visibility](visibility.md#3-tenantvisibility-multi-tenancy)
- **Query artifacts** → [Blackboard Queries](blackboard.md#querying-artifacts)

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

**Start with the basics** → [Getting Started](../getting-started/){ .md-button .md-button--primary }

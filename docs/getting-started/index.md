# Getting Started with Flock

Welcome to Flock! This section will help you get up and running quickly with the blackboard multi-agent framework.

---

## 🚀 Quick Links

<div class="grid cards" markdown>

-   **📦 Installation**

    ---

    Install Flock and configure your environment in just a few minutes.

    [:octicons-arrow-right-24: Install Flock](installation.md)

-   **⚡ Quick Start**

    ---

    Build your first agent in 5 minutes. Zero prompts, zero graph wiring, just type contracts.

    [:octicons-arrow-right-24: Quick Start Guide](quick-start.md)

-   **💡 Core Concepts**

    ---

    Understand the four core concepts: Flock, Agents, Artifacts, and Blackboard.

    [:octicons-arrow-right-24: Learn Concepts](concepts.md)

</div>

---

## Learning Path

New to Flock? Follow this recommended learning path:

1. **[Installation](installation.md)** (5 minutes)
   Set up Flock and configure your API keys

2. **[Quick Start](quick-start.md)** (5 minutes)
   Build your first pizza-ordering agent

3. **[Core Concepts](concepts.md)** (15 minutes)
   Understand how Flock's blackboard architecture works

4. **[User Guides](../guides/index.md)** (ongoing)
   Dive deep into agents, blackboard patterns, and advanced features

---

## What Makes Flock Different?

**Traditional Frameworks** → You write prompts and define workflow graphs

**Flock** → You define typed artifacts and let workflows emerge from subscriptions

```python
# No prompts. No graphs. Just contracts.
agent = (
    flock.agent("pizza_master")
    .consumes(PizzaIdea)      # Subscribe to inputs
    .publishes(Pizza)         # Declare outputs
)
```

Agents automatically execute when their input types appear on the blackboard. No hardcoded edges. No orchestration code. Just clean, composable type contracts.

---

## Next Steps

<div class="grid cards" markdown>

-   **Build Multi-Agent Systems**

    ---

    Learn how to coordinate multiple agents through the blackboard.

    [:octicons-arrow-right-24: Agent Guide](../guides/agents.md)

-   **Master the Blackboard**

    ---

    Understand artifact flows, batching, and parallel execution.

    [:octicons-arrow-right-24: Blackboard Guide](../guides/blackboard.md)

-   **Add Real-Time Dashboard**

    ---

    Visualize agent execution with the built-in React dashboard.

    [:octicons-arrow-right-24: Dashboard Guide](../guides/dashboard.md)

-   **Enable Production Tracing**

    ---

    Monitor and debug with OpenTelemetry and DuckDB.

    [:octicons-arrow-right-24: Tracing Guide](../guides/tracing/tracing-quickstart.md)

</div>

---

## Need Help?

- 📖 **Documentation:** You're already here!
- 💬 **Discussions:** [GitHub Discussions](https://github.com/whiteducksoftware/flock/discussions)
- 🐛 **Issues:** [GitHub Issues](https://github.com/whiteducksoftware/flock/issues)
- 📦 **PyPI:** [flock-core](https://pypi.org/project/flock-core/)

---

**Ready to start?** → [Install Flock](installation.md){ .md-button .md-button--primary }

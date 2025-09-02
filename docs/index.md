---
hide: # Optional: Hide table of contents on simple pages
  - toc
---


# 🚀 Flock — Declarative, Testable AI Agents

<!-- Optional: Add banner back later if desired -->


<p align="center">
<!-- Badges can be added back if relevant/maintained -->
<img alt="Flock Banner" src="assets/images/flock.png">
<img alt="Dynamic TOML Badge" src="https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%2Fwhiteducksoftware%2Fflock%2Frefs%2Fheads%2Fmaster%2Fpyproject.toml&query=%24.project.version&style=for-the-badge&logo=pypi&label=pip%20version">
<a href="https://www.linkedin.com/company/whiteduck" target="_blank"><img alt="LinkedIn" src="https://img.shields.io/badge/linkedin-%230077B5.svg?style=for-the-badge&logo=linkedin&logoColor=white&label=whiteduck"></a>
<a href="https://bsky.app/profile/whiteduck-gmbh.bsky.social" target="_blank"><img alt="Bluesky" src="https://img.shields.io/badge/bluesky-Follow-blue?style=for-the-badge&logo=bluesky&logoColor=%23fff&color=%23333&labelColor=%230285FF&label=whiteduck-gmbh"></a>
</p>

---

Tired of wrestling with paragraphs of prompt text just to get your AI agent to do *one specific thing*? 😫 Enter **Flock**, the agent framework that lets you ditch the prompt-palaver and focus on **what** you want your agents to achieve!

Flock takes a **declarative approach**. You define contracts — the agent’s input and output — and let the framework figure out the “how”. Powered by modern LLMs, a clean component system, and strong orchestration, Flock makes agents reliable and testable.

Built with real-world deployment in mind, Flock integrates with **Temporal** for fault-tolerant execution, offers a web API/UI, and provides a thread-safe registry and serialization out of the box.

## ✨ Why Join the Flock?

| Traditional Agent Frameworks 😟 | Flock Framework 🐤🐧🐓🦆 |
| :-------------------------------- | :------------------------------------------ |
| 🤯 **Prompt Nightmare**             | ✅ **Declarative Simplicity**               |
| *Long, brittle, hard-to-tune prompts* | *Clear input/output specs (with types!)*  |
| 💥 **Fragile & Unpredictable**      | ⚡ **Robust & Production-Ready**           |
| *Single errors crash the system*  | *Fault-tolerant via Temporal integration* |
| 🧩 **Monolithic & Rigid**          | 🔧 **Modular & Flexible**                   |
| *Hard to extend or modify logic*  | *Unified Components (Evaluation, Routing, Utility)*  |
| ⛓️ **Basic Chaining**              | 🚀 **Advanced Orchestration**               |
| *Often just linear workflows*     | *Dynamic routing, parallel/batch runs*    |

## 💡 Core Ideas

Flock's power comes from a few key concepts:

1. **Declarative Contracts:** Define input/output as concise strings or Pydantic models.
2. **Unified Components:** Add behavior via Evaluation, Routing, and Utility components in a single list (`agent.components`).
3. **Intelligent Workflows:** Pick the next agent explicitly, via callable, or through routing components.
4. **Reliable Execution:** Debug locally or switch to **Temporal** for production-grade retries and durability.
5. **Type Safety:** Use type hints and Pydantic for predictable, testable agent behavior.

## 🐥 Quick Taste

Building your first agent is refreshingly simple:

```python
import os
from flock.core import Flock, DefaultAgent 


# --------------------------------
# Define the model
# --------------------------------
# Flock uses litellm to talk to LLMs
# Please consult the litellm documentation for valid IDs:
# https://docs.litellm.ai/docs/providers
MODEL = "openai/gpt-4o"


# --------------------------------
# Create the flock and context
# --------------------------------
# The flock is the place where all the agents are at home
flock = Flock(name="hello_flock", description="This is your first flock!", model=MODEL)

# --------------------------------
# Create an agent
# --------------------------------
# The Flock doesn't believe in prompts (see the docs for more info)
# Declare input/output contracts; the framework manages the "how"
presentation_agent = DefaultAgent(
    name="my_presentation_agent",
    description="Create a fun presentation outline",
    input="topic: str",
    output="fun_title: str, fun_slide_headers: list[str]"
)
flock.add_agent(presentation_agent)


# --------------------------------
# Run the flock
# --------------------------------
# Tell the flock who the starting agent is and what input to give it
flock.run(agent=presentation_agent, input={"topic": "Robot kittens"})

```


That’s it. Flock turns the contract into the necessary LLM calls and returns a clean, dot-accessible result.

🗺️ Ready to Explore?

- Dive deeper into the Flock ecosystem:

• Getting Started: Install and run your first agent
• Core Concepts: Agents, Contracts, Context, Workflows
• Components: Evaluation, Routing, Utility
• Guides: Hydrator, Custom components, MCP tools
• Interacting: Programmatic, REST API, Web UI, CLI
• Deployment: Temporal configuration

🤝 Join the Flock Community!

- Flock is actively developed and welcomes contributions.

- Check out the code on GitHub

- Report issues or suggest features.

- Help us improve the documentation!

Let’s build reliable AI agent systems together! 🚀

---
hide: # Optional: Hide table of contents on simple pages
  - toc
---


# 🚀 Welcome to Flock! Take Flight with Declarative AI Agents 🚀

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

Flock takes a **declarative approach**. Think of it like ordering a pizza 🍕: you specify the toppings (your agent's `input` and `output`), not the 30 steps the chef needs to follow. Flock, powered by modern LLMs and a clever architecture, figures out the "how" for you.

Built with real-world deployment in mind, Flock integrates seamlessly with tools like **Temporal** for building robust, fault-tolerant, and scalable agent systems right out of the box.

## ✨ Why Join the Flock?

| Traditional Agent Frameworks 😟 | Flock Framework 🐤🐧🐓🦆 |
| :-------------------------------- | :------------------------------------------ |
| 🤯 **Prompt Nightmare**             | ✅ **Declarative Simplicity**               |
| *Long, brittle, hard-to-tune prompts* | *Clear input/output specs (with types!)*  |
| 💥 **Fragile & Unpredictable**      | ⚡ **Robust & Production-Ready**           |
| *Single errors crash the system*  | *Fault-tolerant via Temporal integration* |
| 🧩 **Monolithic & Rigid**          | 🔧 **Modular & Flexible**                   |
| *Hard to extend or modify logic*  | *Pluggable Evaluators, Modules, Routers*  |
| ⛓️ **Basic Chaining**              | 🚀 **Advanced Orchestration**               |
| *Often just linear workflows*     | *Dynamic routing, parallel/batch runs*    |

## 💡 Core Ideas

Flock's power comes from a few key concepts:

1.  **Declarative Agents:** Define agents by *what* they do (inputs/outputs), not *how*. Flock uses **Evaluators** to handle the underlying logic (be it LLM calls, rules, or custom code).
2.  **Modular Components:** Extend agent capabilities with pluggable **Modules** (for memory, metrics, output formatting, etc.) that hook into the agent's lifecycle without touching its core definition.
3.  **Intelligent Workflows:** Chain agents explicitly or use **Routers** (like LLM-based or Agent-based) for dynamic decision-making on the next step.
4.  **Reliable Execution:** Run locally for debugging or switch seamlessly to **Temporal** for production-grade fault tolerance, retries, and state management.
5.  **Type Safety:** Leverage Python type hints and Pydantic for clear contracts, validation, and easier integration.

## 🐥 Hello Flock! - A Quick Taste

Building your first agent is refreshingly simple:

```python
import os
from flock.core import Flock, FlockFactory 


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
# The Flock just declares what agents get in and what agents produce
# my_presentation_agent takes in a topic and outputs a
# funny_title, fun_slide_headers and fun_slide_summaries
presentation_agent = FlockFactory.create_default_agent(
    name="my_presentation_agent",
    input="topic",
    output="fun_title, fun_slide_headers, fun_slide_summaries"
)
flock.add_agent(presentation_agent)


# --------------------------------
# Run the flock
# --------------------------------
# Tell the flock who the starting agent is and what input to give it
flock.run(
    start_agent=presentation_agent, 
    input={"topic": "A presentation about robot kittens"}
)

```


That's it! Flock handled turning your simple declaration into the necessary LLM interaction and gave you back a clean, typed Python object.

🗺️ Ready to Explore?

- Dive deeper into the Flock ecosystem:

- Getting Started: Your first flight – installation and basic usage.

- Core Concepts: Understand the foundations – Agents, Declarative logic, Workflows.

- Key Components: Learn about the building blocks – Evaluators, Modules, Tools.

- Guides: Practical walkthroughs for common tasks like chaining agents.

- Deployment: Take your Flock to production with Temporal.

🤝 Join the Flock Community!

- Flock is actively developed and welcomes contributions.

- Check out the code on GitHub

- Report issues or suggest features.

- Help us improve the documentation!

Let's build amazing, reliable AI agent systems together! 🚀

---
hide:
  - toc
---

# Getting Started: Your First Flight with Flock! 🚀

Welcome aboard! You're about to take your first steps into the world of **Flock**, where building powerful AI agents is less about wrestling with endless prompts and more about declaring **what** you want to achieve.

Ready to ditch the prompt-palaver and build robust, scalable agent systems with surprising ease? You're in the right place! This section is your launchpad, guiding you from zero to running your first Flock agent.

## What You'll Find Here

This section covers the essentials to get you up and running:

*   **[Quick Start](quickstart.md):** Jump right in and build your very first Flock agent in minutes. See how simple the declarative approach can be.
*   **[Installation](installation.md):** Get Flock set up on your machine, along with any necessary dependencies.
*   **[Basic Concepts](concepts.md):** Understand the fundamental ideas behind Flock – Agents, the Declarative approach, and the core components you'll interact with. *(Coming Soon)*
*   **[Configuration](configuration.md):** Learn how to configure Flock for your specific needs, including setting up LLM providers.

## Prerequisites

Before you dive in, make sure you have:

*   🐍 Python 3.10 or higher installed.
*   📦 `pip` or `uv` (highly recommended!) for installing packages.

Download `uv`: **[https://docs.astral.sh/uv/getting-started/installation/](https://docs.astral.sh/uv/getting-started/installation/)**

*   🔑 An API key for your preferred Large Language Model (LLM) provider (like OpenAI, Anthropic, Gemini, etc.). Flock uses `litellm` to connect, so many are supported!

Checkout which models are supported and how to use them! **[https://docs.litellm.ai/docs/providers](https://docs.litellm.ai/docs/providers)**

For example you want to use an Anthropic model with flock:

- Click on "Anthropic"

- Find the name of the environment variable which litellm will check: `ANTHROPIC_API_KEY`

- Find how litellm expects the model name to be defined: `model="anthropic/claude-3-5-sonnet-20240620"`


Based on these information all you need to do for flock using any anthropic model is adding the key with the correct name into your .env and build your flock with `flock = Flock(model="anthropic/...")`


## Where to Begin?

We recommend starting with the **[Quick Start](quickstart.md)** guide for a hands-on introduction. If you prefer to set up everything first, head over to the **[Installation](installation.md)** page.

Let's get your first agent airborne! 🐦‍⬛💨
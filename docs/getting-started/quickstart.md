---
hide:
  - toc
---

# Quick Start: Your First Agent in 5 Minutes! ⏱️

Ready for liftoff? This guide will get you running your first Flock agent faster than a hummingbird's wings! We'll create a simple agent that takes a topic and generates a fun presentation title and some slide headers.

## Prerequisites

Make sure you've completed the **[Installation](installation.md)** steps, especially setting up your LLM API keys in your environment (e.g., in a `.env` file).

## The "Hello Flock!" Code

Create a new Python file (e.g., `hello_flock.py`) and paste the following code:

```python
# hello_flock.py
from flock.core import Flock, FlockFactory

# --------------------------------
# 1. Choose Your LLM
# --------------------------------
# Flock uses litellm, so you can specify many different providers.
# Make sure the corresponding API key is set in your environment!
# Examples: "openai/gpt-4o", "anthropic/claude-3-sonnet-20240229", "gemini/gemini-1.5-pro"
MODEL = "openai/gpt-4o" # <-- Replace with your preferred model if needed

# --------------------------------
# 2. Create Your Flock
# --------------------------------
# The Flock is the main orchestrator.
flock = Flock(
    name="presentation_helper",
    description="My first Flock!",
    model=MODEL # Set the default model for agents in this Flock
)

# --------------------------------
# 3. Define Your Agent Declaratively
# --------------------------------
# No complex prompts needed! Just declare what goes in and what comes out.
# We'll use FlockFactory for a quick setup.
presentation_agent = FlockFactory.create_default_agent(
    name="my_presentation_agent",
    description="Creates a fun presentation outline about a given topic",
    input="topic: str", # The agent expects a string named 'topic'
    output="fun_title: str, fun_slide_headers: list[str]" # It will output a string 'fun_title' and a list of strings 'fun_slide_headers'
)

# --------------------------------
# 4. Add the Agent to the Flock
# --------------------------------
flock.add_agent(presentation_agent)

# --------------------------------
# 5. Run the Flock!
# --------------------------------
# Tell the Flock which agent to start with and provide the input.
print(f"Running agent '{presentation_agent.name}'...")
result = flock.run(
    start_agent=presentation_agent, # Or use the name: "my_presentation_agent"
    input={"topic": "Why Llamas Make Great Urban Pets"} # The input data
)

# --------------------------------
# 6. Admire the Results!
# --------------------------------
# The result is a clean Python object (a Box object, behaves like a dict/object)
print("\n--- Agent Output ---")
print(f"✨ Title: {result.fun_title}")
print(f"📊 Headers: {result.fun_slide_headers}")
print("--------------------")
```

## Running the Code

Save the file and run it from your terminal:

`python hello_flock.py`


You should see output similar to this (the exact content will vary based on the LLM's response):

```bash
Running agent 'my_presentation_agent'...

--- Agent Output ---
✨ Title: Concrete Jungles & Camelids: Why Your Next Roommate Should Be A Llama
📊 Headers: ['Llamas: Nature's Low-Maintenance Loft-Dwellers', "Traffic Jam? No Prob-llama!", 'The Ultimate Urban Eco-Warrior (They Mow with Their Mouths!)', 'Spit Happens: Debunking Llama Myths', 'From Andes to Apartments: Integrating Your Llama Lifestyle']
--------------------
```

## What Just Happened?

Let's break down the magic:

**Choose Your LLM**: You specified which LLM to use via MODEL. litellm handles the connection using the API key from your environment.

**Create Your Flock**: The Flock object acts as the container and orchestrator for your agents.

**Define Your Agent Declaratively**: This is the core of Flock! Instead of writing a long prompt, you used FlockFactory.create_default_agent and simply declared:

input="topic: str": The agent needs one input called topic, which should be a string.

output="fun_title: str, fun_slide_headers: list[str]": The agent should produce two outputs: fun_title (a string) and fun_slide_headers (a list of strings).
Flock's default evaluator takes care of constructing the necessary instructions for the LLM based on these declarations and the agent's description.

**Add the Agent**: You registered your presentation_agent with the flock.

**Run the Flock**: flock.run() kicked off the process, starting with your specified agent and input.

**Admire the Results**: Flock executed the agent (calling the LLM behind the scenes) and returned the output as a convenient Box object, allowing you to access the results using dot notation (like result.fun_title).

Congratulations! You've successfully run your first Flock agent without writing a single complex prompt.

## Next Steps

Explore adding Tools to give your agents superpowers (like web search or code execution).

Learn how to Chain Agents together for more complex workflows.

Dive deeper into the Core Concepts that make Flock tick.
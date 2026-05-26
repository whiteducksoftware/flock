---
hide:
  - toc
---

# ⌨️ Interactive Script CLI (`flock.start_cli()`)

While the main [Flock CLI Tool](cli-tool.md) is used for managing saved configurations, Flock also offers an **interactive command-line interface directly within your running Python script** using the `flock.start_cli()` method.

This mode is specifically designed for **development and debugging** purposes, allowing you to step through agent interactions and inspect the context of your *current, in-memory* `Flock` instance.

## Starting the Interactive CLI

You typically call `start_cli()` at a point in your script where you have a fully configured `Flock` object ready.

```python
from flock.core import Flock, FlockFactory
from flock.routers.default import DefaultRouter, DefaultRouterConfig # Assuming DefaultRouter is used

# --- Configure your Flock and Agents ---
flock = Flock(name="Debug Flock", model="openai/gpt-4o")

agent_a = FlockFactory.create_default_agent(
    name="AgentA",
    input="start_query: str",
    output="intermediate_result: str",
    wait_for_input=True # Useful in interactive mode
)

agent_b = FlockFactory.create_default_agent(
    name="AgentB",
    input="intermediate_result: str", # Takes output from AgentA
    output="final_answer: str",
    wait_for_input=True # Useful in interactive mode
)

# Setup handoff (simple chain)
agent_a.handoff_router = DefaultRouter(config=DefaultRouterConfig(hand_off=agent_b.name))

flock.add_agent(agent_a)
flock.add_agent(agent_b)

# --- Start the Interactive CLI ---
if __name__ == "__main__":
    print("Starting Flock Interactive CLI...")
    print("Type your initial query for AgentA, or 'quit' to exit.")
    # This call enters an interactive loop in the terminal
    flock.start_cli(start_agent=agent_a) # Specify the starting agent

    print("Interactive CLI finished.")
```

## Using the Interactive CLI

When you run the script above, instead of executing the full workflow automatically, `flock.start_cli()` will present an interactive prompt in your terminal:

1. **Initial Input:** It will typically prompt for the input required by the start_agent you specified.

2. **Agent Execution:** After you provide input, the starting agent (AgentA in the example) executes.

3. **Output Display:** The agent's output is displayed (often using the configured OutputModule, potentially with rich tables).

4. **Handoff & Next Input:** If the agent has a handoff_router, Flock determines the next agent (AgentB). If the next agent is configured with wait_for_input=True (or if interaction is needed), the CLI might pause or show the next agent's expected input. Often, data flows automatically via context matching the handoff mode.

5. **Loop:** The process repeats for the next agent.

6. **Commands:** You can typically type commands like `quit`, `exit`, or potentially others (depending on implementation details) to control the flow or inspect state.

(Placeholder: Screenshot of the terminal during an interactive flock.start_cli() session)

## Use Cases

- **Debugging Agent Chains:** Observe the output of each agent in a sequence.
- **Inspecting Context:** (If enhanced) See how the FlockContext changes after each step.
- **Testing Routers:** Verify that your LLMRouter or AgentRouter selects the expected next agent based on intermediate results.
- **Manual Control:** Intervene in the workflow or provide specific inputs at different stages.

**Important:** `flock.start_cli()` operates on the Flock object currently in your Python script's memory. It does not load or save .flock.yaml files like the main flock management tool. It's purely a development aid within a script.


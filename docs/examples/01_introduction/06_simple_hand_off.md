
# Simple hand-off between two agents

In this example, we create a simple two-agent chain:

1. **IdeaAgent:** Receives a query and outputs a fun software project idea.
2. **ProjectPlanAgent:** Takes the software project idea and outputs a catchy project name, project pitch, tech stack, and project implementation plan.

The **IdeaAgent** is the starting point of the workflow and hands off the software project idea to the **ProjectPlanAgent**, which then generates additional project details based on the idea.

A more in-depth example of agent hand-off is available in the `a_hand_off_pm.py` example.

To make hand-offs between agents as intuitive as possible, follow these rules:

1. **Connect Agents:**  
   Set the `hand_off` attribute of the first agent to the second agent.
   ```python
   idea_agent.hand_off = project_plan_agent
   ```

2. **Define Data Flow:**  
   Set the input of the second agent to the output of the first agent.
   ```python
   idea_agent -> a_fun_software_project_idea -> project_plan_agent
   ```

That's it! The agents are now connected and will pass data between them as expected.

---

## Code Example

### 1. Imports and Flock Setup

```python
import asyncio

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from flock.core.logging.formatters.base_formatter import FormatterOptions
from flock.core.logging.formatters.rich_formatters import RichTables
```

### 2. Defining Agents and Hand-off

```python
async def main():

    flock = Flock(
        local_debug=True,
        output_formatter=FormatterOptions(
            formatter=RichTables,
            wait_for_input=True,
            settings={}
        ),
        enable_logging=True
    )
    
    idea_agent = FlockAgent(
        name="idea_agent",
        input="query",
        output="a_fun_software_project_idea",
        use_cache=True,
    )

    project_plan_agent = FlockAgent(
        name="project_plan_agent",
        input="a_fun_software_project_idea",
        output="catchy_project_name, project_pitch, techstack, project_implementation_plan",
        use_cache=True,
    )
    
    idea_agent.hand_off = project_plan_agent

    flock.add_agent(idea_agent)
    flock.add_agent(project_plan_agent)

    await flock.run_async(
        input={"query": "fun software project idea"},
        start_agent=idea_agent,
    )

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Summary

This example demonstrates a simple hand-off between two Flock agents. The **IdeaAgent** generates a fun software project idea and passes it to the **ProjectPlanAgent**, which then expands on the idea by providing additional project details. This streamlined hand-off mechanism allows agents to be connected with minimal configuration.

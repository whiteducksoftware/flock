"""
Title: Simple hand-off between two agents

In this example, we create a simple two-agent chain:
    1. IdeaAgent: Receives a query and outputs a fun software project idea.
    2. ProjectPlanAgent: Takes the software project idea and outputs a catchy project name, project pitch, tech stack, and project implementation plan.

The IdeaAgent is the starting point of the workflow, and it hands off the software project idea to the ProjectPlanAgent.
The ProjectPlanAgent then generates additional project details based on the idea.

A more in-depth example of agent hand-off is available in the "a_hand_off_pm.py" example.

To make hand offs between agents as intuitive as possible an agent handoff works by these easy to remember rules:

1. Connect agents by setting the `hand_off` attribute of the first agent to the second agent.
idea_agent.hand_off = project_plan_agent

2. set the input of the second agent to the output of the first agent (or parts of it).
idea_agent -> a_fun_software_project_idea -> project_plan_agent

That's it! The agents are now connected and will pass data between them as expected.

For 99% of use cases, this is all you need to do to create a hand-off between agents.

In later examples, we will explore more advanced hand-off scenarios and fall back rules.
"""



from flock.core import Flock, FlockFactory



flock = Flock()

idea_agent = FlockFactory.create_default_agent(
    name="idea_agent",
    input="query",
    output="a_fun_software_project_idea",
    enable_rich_tables=True,
    wait_for_input=True,
)

project_plan_agent = FlockFactory.create_default_agent(
    name="project_plan_agent",
    input="a_fun_software_project_idea",
    output="catchy_project_name, project_pitch, techstack, project_implementation_plan",
    enable_rich_tables=True,
    wait_for_input=True,
)

idea_agent.hand_off = project_plan_agent

flock.run(
    input={"query": "fun software project idea about ducks"},
    start_agent=idea_agent,
    agents=[idea_agent,project_plan_agent]
)



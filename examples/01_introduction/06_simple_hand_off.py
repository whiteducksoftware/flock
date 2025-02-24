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



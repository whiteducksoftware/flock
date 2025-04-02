from flock.core import Flock, FlockFactory
from flock.routers.agent.agent_router import AgentRouter, AgentRouterConfig
from flock.routers.default.default_router import DefaultRouter, DefaultRouterConfig
from flock.routers.llm.llm_router import LLMRouter, LLMRouterConfig



flock = Flock(enable_logging=True)

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

# Default router = handoff to specific agent
idea_agent.handoff_router = DefaultRouter(config=DefaultRouterConfig(hand_off=project_plan_agent.name))

# LLM router = handoff to agent based on LLM's decision
#idea_agent.handoff_router = LLMRouter(config=LLMRouterConfig(with_output=True))
flock.add_agent(idea_agent)
flock.add_agent(project_plan_agent)
flock.start_cli()
flock.run(
    input={"query": "fun software project idea about ducks"},
    start_agent=idea_agent,
    agents=[idea_agent,project_plan_agent]
)



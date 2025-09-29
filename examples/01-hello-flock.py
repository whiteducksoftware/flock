from flock.cli.utils import print_header, print_subheader
from flock.core import DefaultAgent, Flock

# 1. Create the main orchestrator
my_flock = Flock(model="openai/gpt-5-mini")  # Uses DEFAULT_MODEL from environment if set

# 2. Declaratively define an agent
prd_agent = DefaultAgent(
    name="prd_generator",
    description="Generates a product requirements document from a project idea",
    input="project_idea",
    output="catchy_title, mission_statement, mvp_scope, target_users, functional_requirements, "
    "non_functional_requirements, milestones, epics, user_stories",
)

# 3. Add the agent to the Flock
my_flock.add_agent(prd_agent)

# 4. Run the agent!
input_data = {"project_idea": "An agent management dashboard"}
result = my_flock.run(agent="prd_generator", input=input_data)

# The result is a real object ready for downstream tasks
print_header(f"{result.catchy_title}")
print_subheader("Mission Statement")
print(f"{result.mission_statement}")
print_subheader("MVP Scope")
print(f"{result.mvp_scope}")
print_subheader("Target Users")
print(f"{result.target_users}")
print_subheader("Functional Requirements")
print(f"{result.functional_requirements}")
print_subheader("Non-Functional Requirements")
print(f"{result.non_functional_requirements}")
print_subheader("Milestones")
print(f"{result.milestones}")
print_subheader("Epics")
print(f"{result.epics}")
print_subheader("User Stories")
print(f"{result.user_stories}")

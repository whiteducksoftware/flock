"""
Tutorial Example: Multi-Agent Chain for Software Project Scaffolding

In this example, we build a chain of Flock agents that collaborate to scaffold a software project.
The workflow is as follows:

  1. **idea_agent:**  
     Takes a simple query and returns a fun software project idea.

  2. **project_plan_agent:**  
     Uses the software project idea to generate additional project details such as:
       - A catchy project name
       - A project pitch
       - A recommended tech stack
       - A project implementation plan

  3. **readme_agent:**  
     Consumes the outputs of the project_plan_agent to produce a readme file.

  4. **issue_agent:**  
     Uses the readme and additional project details to create GitHub issues and files.

Each agent is declared using a simple input/output signature, and the chain is established via the `hand_off` property.
Flock manages the registration and execution of agents. In this example, we run the workflow in local debug mode.

Let's see how it all comes together!
"""



import asyncio
from dataclasses import dataclass


from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from flock.core.logging.formatters.base_formatter import FormatterOptions
from flock.core.logging.formatters.rich_formatters import RichTables
from flock.core.tools import basic_tools
from flock.core.tools.dev_tools import github


@dataclass
class Features:
    title: str
    description: str
    acceptance_criteria: str


async def main():

    flock = Flock(local_debug=True, output_formatter=FormatterOptions(formatter=RichTables, wait_for_input=False, settings={}),enable_logging=True)
    
    idea_agent = FlockAgent(
        name="idea_agent",
        input="query",
        output="software_project_idea",
        tools=[basic_tools.web_search_tavily],
        use_cache=True,
    )

    project_plan_agent = FlockAgent(
        name="project_plan_agent",
        input="software_project_idea",
        output="catchy_project_name, project_pitch, techstack, project_implementation_plan",
        tools=[basic_tools.web_search_tavily],
        use_cache=True,
    )

    readme_agent = FlockAgent(
        name="readme_agent",
        input="catchy_project_name, project_pitch, techstack, project_implementation_plan",
        output="readme",
        tools=[github.upload_readme],
        use_cache=True,
    )   

    feature_agent = FlockAgent(
        name="feature_agent",
        input="readme, catchy_project_name, project_pitch, techstack, project_implementation_plan",
        output="features : list[Features]",
        tools=[github.create_user_stories_as_github_issue, github.create_files],
        use_cache=True,
    )   

    issue_agent = FlockAgent(
        name="issue_agent",
        input="current_feature, readme, techstack, project_implementation_plan, all_feature_titles",
        output="user_stories_on_github, files_on_github",
        tools=[github.create_user_stories_as_github_issue, github.create_files],
        use_cache=True,
    )   

    idea_agent.hand_off = project_plan_agent
    project_plan_agent.hand_off = readme_agent
    readme_agent.hand_off = feature_agent


    flock.add_agent(idea_agent)
    flock.add_agent(project_plan_agent)
    flock.add_agent(readme_agent)
    flock.add_agent(feature_agent)
    flock.add_agent(issue_agent)

    features : Features = await flock.run_async(
        start_agent=idea_agent,
    )



if __name__ == "__main__":
    asyncio.run(main())
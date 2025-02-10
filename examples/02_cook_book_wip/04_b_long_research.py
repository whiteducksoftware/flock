

import asyncio

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from flock.core.logging.formatters.base_formatter import FormatterOptions
from flock.core.logging.formatters.rich_formatters import RichTables
from flock.core.tools import basic_tools
from flock.core.tools.dev_tools import github


async def main():

    flock = Flock(local_debug=True, output_formatter=FormatterOptions(formatter=RichTables, wait_for_input=True, settings={}),enable_logging=True)
    
    idea_agent = FlockAgent(
        name="idea_agent",
        input="query",
        output="a_fun_software_project_idea",
        tools=[basic_tools.web_search_tavily],
    )

    project_plan_agent = FlockAgent(
        name="project_plan_agent",
        input="software_project_idea",
        output="catchy_project_name, project_pitch, techstack, project_implementation_plan",
        tools=[basic_tools.web_search_tavily],
    )

    readme_agent = FlockAgent(
        name="readme_agent",
        input="catchy_project_name, project_pitch, techstack, project_implementation_plan",
        output="readme",
        tools=[github.upload_readme],
    )   

    issue_agent = FlockAgent(
        name="issue_agent",
        input="readme, catchy_project_name, project_pitch, techstack, project_implementation_plan",
        output="user_stories_on_github, files_on_github",
        tools=[github.create_user_stories_as_github_issue, github.create_files],
    )   

    idea_agent.hand_off = project_plan_agent
    project_plan_agent.hand_off = readme_agent
    readme_agent.hand_off = issue_agent

    flock.add_agent(idea_agent)
    flock.add_agent(project_plan_agent)
    flock.add_agent(readme_agent)
    flock.add_agent(issue_agent)

    await flock.run_async(
        input="a random software project idea",
        start_agent=idea_agent,
    )



if __name__ == "__main__":
    asyncio.run(main())
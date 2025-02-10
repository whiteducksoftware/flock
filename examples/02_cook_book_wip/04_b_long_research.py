

import asyncio
from typing import Generator

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from flock.core.logging.formatters.base_formatter import FormatterOptions
from flock.core.logging.formatters.rich_formatters import RichTables
from flock.core.tools import basic_tools
from flock.core.tools.dev_tools import github


async def main():

    flock = Flock(local_debug=True, output_formatter=FormatterOptions(formatter=RichTables, wait_for_input=True, settings={}),enable_logging=True)
    
    outline_agent = FlockAgent(
        name="outluine_agent",
        description="Outline a thorough overview of a topic.",
        input="topic",
        output="title,sections: list[str],section_subheadings: dict[str, list[str]]|mapping from section headings to subheadings",
        tools=[basic_tools.web_search_tavily],
    )


    draft_agent = FlockAgent(
        name="draft_agent",
        input="topic,section_heading,section_subheadings: list[str]",
        output="content|markdown-formatted section",
        tools=[basic_tools.web_search_tavily],
    )

     
    flock.add_agent(outline_agent)
    flock.add_agent(draft_agent)

    result = await flock.run_async(
        input={"topic": "Latest research about training algorithms"},
        start_agent=outline_agent,
    )
    sections =[]
    for heading, subheadings in result.section_subheadings.items():
            section, subheadings = f"## {heading}", [f"### {subheading}" for subheading in subheadings]
            result_content = await flock.run_async(
                input={"topic": result.topic,
                       "section_heading": section,
                       "section_subheadings": subheadings
                       },
                start_agent=draft_agent,
            )
            sections.append(result_content.content)



if __name__ == "__main__":
    asyncio.run(main())
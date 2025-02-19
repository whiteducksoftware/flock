"""
Title: Building huge documents without a hand off

In this example, we'll outline a thorough overview of a topic and then draft the content for each section.

We do this without using an explicit handoff between the outline and draft agents, but by using flock itself to manage the flow.

This way you can build create workflows that need a transformation of data from one agent to another without the need for a handoff.

This example implements https://dspy.ai/#__tabbed_2_6 to also highlight the ability to build dspy pipelines with flock.
"""


import asyncio

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent

from flock.core.tools import basic_tools


async def main():

    flock = Flock(local_debug=True,enable_logging=True)
    
    outline_agent = FlockAgent(
        name="outline_agent",
        description="Outline a thorough overview of a topic.",
        input="topic",
        output="title,sections: list[str],section_subheadings: dict[str, list[str]]|mapping from section headings to subheadings",
        tools=[basic_tools.web_search_tavily, basic_tools.get_web_content_as_markdown],
    )


    draft_agent = FlockAgent(
        name="draft_agent",
        input="flock.topic,flock.section_heading,flock.section_subheadings: list[str]",
        output="content|markdown-formatted section",
        tools=[basic_tools.web_search_tavily, basic_tools.get_web_content_as_markdown],
    )

     
    flock.add_agent(outline_agent)
    flock.add_agent(draft_agent)

    # Instead defining handoff between agents, we just use flock to run the outline agent
    result = await flock.run_async(
        start_agent=outline_agent,
    )

    sections =[]
    # We then do our processing (in this case formatting the content) and run the draft agent for each section
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
            with open("output.md", "w") as f:
                f.write("\n\n".join(sections))





if __name__ == "__main__":
    asyncio.run(main())
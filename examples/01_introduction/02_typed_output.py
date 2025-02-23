"""
Title: Advanced Flock Agent with Caching, Type Hints, and Tool Integration

In this example, we'll show you how to build a more advanced Flock system that:
  - Uses a custom output formatter (RichTables) for a polished, swaggy display.
  - Defines output types using standard Python type hints (including lists and Literals) for structured results.
  - Integrates external tools (like a web content scraper) so that agents can perform more complex operations.
  - Leverages caching so that if an agent is called with the same input, the cached result is returned—this is particularly
    useful for expensive operations such as web scraping or during debugging.

The agent in this example takes a URL as input and outputs:
  - A title,
  - A list of headings,
  - A list of dictionaries mapping entities to metadata, and
  - A type (limited to one of 'news', 'blog', 'opinion piece', or 'tweet').

After executing the agent, you can work with the result as a real Python object that respects the defined types.

Let's dive in!
"""

import asyncio
from pprint import pprint

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from flock.core.logging.formatters.themes import OutputTheme
from flock.core.tools import basic_tools

async def main():
    # --------------------------------
    # Create the flock
    # --------------------------------
    flock = Flock(local_debug=True)


    # --------------------------------
    # Create an agent
    # --------------------------------
    # Some additions to example 01
    # - you can define the output types of the agent with standart python type hints
    # - you can define the tools the agent can use
    # - you can define if the agent should use the cache 
    #   results will get cached and if true and if the input is the same as before, the agent will return the cached result
    #   this is useful for expensive operations like web scraping and for debugging
    # Some people need some swag in their output
    # Flock supports rendering the output as a table and you can choose a theme
    agent = FlockAgent(
        name="my_agent",
        input="url",
        output="title, headings: list[str], entities_and_metadata: list[dict[str, str]], type:Literal['news', 'blog', 'opinion piece', 'tweet']",
        tools=[basic_tools.get_web_content_as_markdown],
        use_cache=True,
        output_config=FlockAgentOutputConfig(
            render_table=True,
            theme=OutputTheme.abernathy
        ),
        memory_enabled=True
    )
    flock.add_agent(agent)


    # --------------------------------
    # Run the agent
    # --------------------------------
    # ATTENTION: Big table incoming
    # It's worth it tho!
    result = await flock.run_async(
        start_agent=agent,
        input={"url": "https://lite.cnn.com/travel/alexander-the-great-macedon-persian-empire-darius/index.html"},
    )

    agent.save_memory_graph("memory_graph.json")
    agent.export_memory_graph("memory_graph.png")

    # --------------------------------
    # The result type
    # --------------------------------
    # Btw, the result is a real python object with the types you defined
    # so this works:
    pprint(result.title)



if __name__ == "__main__":
    asyncio.run(main())

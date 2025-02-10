import asyncio
from pprint import pprint

from devtools import debug

from flock.agents.declarative_agent import DeclarativeAgent
from flock.core.flock import Flock
from flock.core.logging.formatters.base_formatter import FormatterOptions
from flock.core.logging.formatters.themed_formatter import ThemedAgentResultFormatter
from flock.core.logging.formatters.themed_formatter import ThemedAgentResultFormatter
from flock.core.tools import basic_tools

async def main():
    # --------------------------------
    # Formatting and themes
    # --------------------------------
    # Some people need a little more color in their life
    # Flock support themes and formatting options for the output
    # ThemedAgentResultFormatter uses actual CLI themes the author of Flock had lying around
    format_options = FormatterOptions(ThemedAgentResultFormatter, wait_for_input=True, settings={"theme": "adventure"})
    flock = Flock(local_debug=True, output_formatter=format_options)

    agent = DeclarativeAgent(
        name="my_agent",
        input="url",
        output="title, headings: list[str], entities_and_metadata: list[dict[str, str]], type:Literal['news', 'blog', 'opinion piece', 'tweet']",
        tools=[basic_tools.get_web_content_as_markdown],
    )
    flock.add_agent(agent)

    await flock.run_async(
        start_agent=agent,
        input="https://lite.cnn.com/travel/alexander-the-great-macedon-persian-empire-darius/index.html",
    )

 



if __name__ == "__main__":
    asyncio.run(main())

import asyncio

from flock.agents import DeclarativeAgent
from flock.core.flock import Flock
from flock.core.logging.formatters.base_formatter import FormatterOptions
from flock.core.logging.formatters.pprint_formatter import PrettyPrintFormatter
from flock.core.logging.formatters.themed_formatter import ThemedAgentResultFormatter

MODEL = "openai/gpt-4o"

async def main():
    # --------------------------------
    # Formatting and themes
    # --------------------------------
    # Some people need a little more color in their life
    # Flock support themes and formatting options for the output
    # Pretty print is a simple formatter that displays the results as a dictionary
    # Pretty print is the default formatter
    format_options = FormatterOptions(PrettyPrintFormatter)
    flock = Flock(model=MODEL, local_debug=True, output_formatter=format_options)


    bloggy = DeclarativeAgent(name="bloggy", input="blog_idea", output="funny_blog_title, blog_headers")
    flock.add_agent(bloggy)
    await flock.run_async(start_agent=bloggy, input="a blog about cats")


if __name__ == "__main__":
    asyncio.run(main())

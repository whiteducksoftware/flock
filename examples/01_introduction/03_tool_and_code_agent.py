"""
Title: Celebrity Age Calculator with Themed Output and Tool Integration

In this example, you'll see an advanced Flock agent in action. This agent demonstrates several cool features:
  - **Themed Output:** We use ThemedAgentResultFormatter with a custom theme (e.g. "adventuretime")
    to spice up the CLI output.
  - **Tool Integration:** The agent is configured with multiple tools, so it can, for example,
    use web search and code evaluation to calculate some advanced maths.
  - **Caching:** Enabled caching ensures that if you run the agent with the same input,
    it will return a cached result—ideal for expensive operations or rapid testing.
  - **Simple Declaration:** Just like all Flock agents, this one declares what it needs ("a_person")
    and what it produces ("persons_age_in_days"), without the hassle of prompt engineering.

In this scenario, our agent ("my_celebrity_age_agent") takes a person's name as input and returns
that person's age in days. We then use it to calculate Johnny Depp's age in days. Very advanced maths!

Let's see how it's done!
"""

import asyncio

from devtools import debug


from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent, FlockAgentOutputConfig
from flock.core.logging.formatters.themed_formatter import ThemedAgentResultFormatter
from flock.core.logging.formatters.themes import OutputTheme
from flock.core.tools import basic_tools

MODEL = "openai/gpt-4o"

async def main():
    # --------------------------------
    # Create the flock
    # --------------------------------
    flock = Flock(local_debug=True)


    # --------------------------------
    # Tools
    # --------------------------------
    # Let's talk abou tools
    # DeclarativeAgent has a tools argument that takes in ANY callable
    # like the ones in flock.core.tools.basic_tools
    # or your own custom tools
    agent = FlockAgent(
        name="my_celebrity_age_agent",
        input="a_person",
        output="persons_age_in_days",
        tools=[basic_tools.web_search_duckduckgo, basic_tools.code_eval],
        output_config=FlockAgentOutputConfig(
            render_table=True,
            theme=OutputTheme.adventuretime
        ),
        use_cache=True,
    )
    flock.add_agent(agent)

    # --------------------------------
    # Run the agent
    # --------------------------------
    # Let's calculate Johnny Depp's age in days
    await flock.run_async(
        start_agent=agent,
        input={"a_person": "Johnny Depp"},
    )


if __name__ == "__main__":
    asyncio.run(main())

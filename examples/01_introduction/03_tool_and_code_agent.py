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


from flock.core import Flock, FlockFactory

from flock.core.logging.formatters.themes import OutputTheme
from flock.core.tools import basic_tools


# --------------------------------
# Create the flock
# --------------------------------
flock = Flock()


# --------------------------------
# Tools
# --------------------------------
# Let's talk about tools
# A FlockAgent has a tools argument that takes in ANY callable
# like the ones in flock.core.tools.basic_tools
# or your own custom tools
agent = FlockFactory.create_default_agent(
    name="my_celebrity_age_agent",
    input_def="a_person",
    output_def="persons_age_in_days",
    tools=[basic_tools.web_search_duckduckgo, basic_tools.code_eval],
    enable_rich_tables=True,
    output_theme=OutputTheme.adventuretime,
    use_cache=True,
)
flock.add_agent(agent)

# --------------------------------
# Run the agent
# --------------------------------
# Let's calculate Johnny Depp's age in days
flock.run(
    start_agent=agent,
    input={"a_person": "Johnny Depp"},
)



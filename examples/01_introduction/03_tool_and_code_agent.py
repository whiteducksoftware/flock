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
    input="a_person",
    output="persons_age_in_days",
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



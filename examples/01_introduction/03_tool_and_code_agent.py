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
# A FlockAgent can call any callable during processing
# in a hopefully smart and useful way
# flock comes with quite a few tools in flock.core.tools
# in this example we will use the web_search_duckduckgo and code_eval tools
# together the agent needs to orchestrate those tools
# to calculate the age of a celebrity in days
agent = FlockFactory.create_default_agent(
    name="my_celebrity_age_agent",
    input="a_person",
    output="persons_age_in_days",
    tools=[basic_tools.web_search_duckduckgo, basic_tools.code_eval],
    enable_rich_tables=True,
    output_theme=OutputTheme.adventuretime, # flock also comes with a few themes
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



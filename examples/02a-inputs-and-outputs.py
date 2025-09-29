
import json

from flock.cli.utils import print_header, print_subheader, print_success
from flock.core import DefaultAgent, Flock
from flock.core.logging.logging import configure_logging
from flock.core.registry.decorators import flock_tool

MODEL = "azure/gpt-4.1"

flock = Flock(
    name="example_02a", description="The flock input and output syntax", model=MODEL
)

@flock_tool
def save_movie_to_file(title: str, synopsis: str):
    with open("movie.json", "w") as f:
        json.dump({"title": title, "synopsis": synopsis}, f)


# --------------------------------
# Define the agent
# --------------------------------
# We claimed that flock doesn't care about prompts.
# This was a little bit of clickbait of course.
# Flock cares very much about prompts.
# But with flock you don't prompt the agent as a whole,
# but the properties of the input and output.
#
# General syntax rules:
# "field_name: type | description"
#
# If you need to specify the agents behavior, you can do so with the description field.
presentation_agent = DefaultAgent(
    name="my_movie_agent",
    description="Creates a fun movie about a given topic, and saves it to a file",  # Isn't just a description, but also a control mechanism
    input="topic: str",
    output="fun_title: str | The funny title of the movie in all caps, "
    "runtime: int | The runtime of the movie in minutes, "
    "synopsis: str | A crazy over the top synopsis of the movie, "
    "characters: list[dict[str, str]] | Key is character name, Value is a character description ",
    tools=[save_movie_to_file],
)
flock.add_agent(presentation_agent)


result = flock.run(agent=presentation_agent, input={"topic": "AI agents"})

# --------------------------------
# The result
# --------------------------------
# The result is a boxed dictionary which enables dot-notation access to the fields.

print_header("Results")
print_subheader(result.fun_title)
print_success(result.synopsis)
print_success(result.characters)

# YOUR TURN!
# Try changing the types and descriptions of the input and output fields
# What happens if agent description is at odds with the input and output fields?

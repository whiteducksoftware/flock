from typing import Literal

from pydantic import BaseModel, Field

from flock.cli.utils import print_header, print_subheader, print_success
from flock.core import Flock, FlockFactory
from flock.core.logging.logging import configure_logging
from flock.core.registry import (
    flock_type,  # Decorator for registering custom types
)

configure_logging("DEBUG", "DEBUG")

@flock_type
class MovieIdea(BaseModel):
    topic: str = Field(..., description="The topic of the movie.")
    genre: Literal["comedy", "drama", "horror", "action", "adventure"] = Field(
        ..., description="The genre of the movie."
    )

@flock_type
class Movie(BaseModel):
    fun_title: str = Field(..., description="The topic of the movie.")
    runtime: int = Field(..., description="The runtime of the movie.")
    synopsis: str = Field(..., description="The synopsis of the movie.")
    characters: list[dict[str, str]] = Field(
        ..., description="The characters of the movie."
    )


MODEL = "openai/gpt-5"

flock = Flock(
    name="example_02", description="The flock input and output syntax", model=MODEL
)


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
presentation_agent = FlockFactory.create_default_agent(
    name="my_movie_agent",
    description="Creates a fun movie about a given topic",  # Isn't just a description, but also a control mechanism
    input=MovieIdea,
    output=Movie,
)
flock.add_agent(presentation_agent)


result = flock.run(agent=presentation_agent, input=MovieIdea(topic="AI agents", genre="comedy"))

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

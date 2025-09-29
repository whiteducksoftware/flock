from typing import Literal

from pydantic import BaseModel, Field

from flock.cli.utils import print_header, print_subheader, print_success
from flock.core import DefaultAgent, Flock
from flock.core.logging.logging import configure_logging
from flock.core.registry import (
    flock_type,  # Decorator for registering custom types
)

# Logging (internal logs, external logs)
# configure_logging("DEBUG", "DEBUG")

@flock_type
class MovieIdea(BaseModel):
    """The idea of a movie."""
    topic: str = Field(..., description="The topic of the movie.")
    genre: Literal["comedy", "drama", "horror", "action", "adventure"] = Field(
        ..., description="The genre of the movie."
    )

@flock_type
class Movie(BaseModel):
    """The movie."""
    fun_title: str = Field(..., description="The title of the movie.")
    runtime: int = Field(..., description="The runtime of the movie.")
    synopsis: str = Field(..., description="The synopsis of the movie.")
    characters: list[dict[str, str]] = Field(
        ..., description="The characters of the movie."
    )


MODEL = "azure/gpt-4.1"

flock = Flock(
    name="example_02", description="The flock input and output syntax", model=MODEL
)


presentation_agent = DefaultAgent(
    name="my_movie_agent",
    description="Creates a fun movie about a given topic",  # Isn't just a description, but also a control mechanism
    input=MovieIdea,
    output=Movie,
)
flock.add_agent(presentation_agent)


result = flock.run(agent=presentation_agent, input=MovieIdea(topic="AI agents", genre="comedy"))

print_header("Results")
print_subheader(result.fun_title)
print_success(result.synopsis)
print_success(result.characters)

# YOUR TURN!
# Try changing the types and descriptions of the input and output fields
# What happens if agent description is at odds with the input and output fields?

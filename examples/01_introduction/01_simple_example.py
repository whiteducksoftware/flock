import os
from flock.core import Flock, FlockFactory
from flock.core.flock_api import FlockAPI


# --------------------------------
# Define the model
# --------------------------------
# Flock uses litellm to talk to LLMs
# Please consult the litellm documentation for valid IDs:
# https://docs.litellm.ai/docs/providers


MODEL = "azure/ara-gpt4o"


# --------------------------------
# Create the flock and context
# --------------------------------
# The flock is the place where all the agents are at home
flock = Flock(model=MODEL)

# --------------------------------
# Create an agent
# --------------------------------
# The Flock doesn't believe in prompts (see the docs for more info)
# The Flock just declares what agents get in and what agents produce
# bloggy takes in a blog_idea and outputs a funny_blog_title 
# and blog_headers
bloggy = FlockFactory.create_default_agent(
    name="bloggy",
    input="blog_idea",
    output="funny_blog_title, blog_headers",
)
flock.add_agent(bloggy)


# --------------------------------
# Run the flock
# --------------------------------
# Tell the flock who is the starting and what input to give it
flock.run(
    start_agent=bloggy, 
    input={"blog_idea": "A blog about cats"}
)


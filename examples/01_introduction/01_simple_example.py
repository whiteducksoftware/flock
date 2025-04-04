import os
from flock.core import Flock, FlockFactory 


# --------------------------------
# Define the model
# --------------------------------
# Flock uses litellm to talk to LLMs
# Please consult the litellm documentation for valid IDs:
# https://docs.litellm.ai/docs/providers
MODEL = "openai/gpt-4o"


# --------------------------------
# Create the flock and context
# --------------------------------
# The flock is the place where all the agents are at home
flock = Flock(name="Example 01", model=MODEL, enable_logging=False)

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
    output="funny_blog_title, blog_headers"
)
flock.add_agent(bloggy)


# --------------------------------
# Run the flock
# --------------------------------
# Tell the flock who the starting agent is and what input to give it
flock.run(
    start_agent=bloggy, 
    input={"blog_idea": "A blog about robot kittens"}
)
#flock.to_yaml_file("bloggy.flock.yaml")

# --------------------------------
# Start the CLI with the loaded Flock
# --------------------------------
# Uncomment the line below to start the CLI:
#flock.start_cli()

import os
from flock.core import Flock, FlockFactory 


# --------------------------------
# Define the model
# --------------------------------
# Flock uses litellm to talk to LLMs
# Please consult the litellm documentation for valid IDs:
# https://docs.litellm.ai/docs/providers
#MODEL = "openai/gpt-4o"
MODEL = "gemini/gemini-2.5-pro-exp-03-25" 


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
    max_tokens=60000,
)
flock.add_agent(bloggy)


# --------------------------------
# Run the flock
# --------------------------------
# Tell the flock who is the starting and what input to give it
flock.run(
    start_agent=bloggy, 
    input={"blog_idea": "A blog about robot kittens"}
)


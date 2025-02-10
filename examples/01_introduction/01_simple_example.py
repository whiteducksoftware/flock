"""
Title: Building Your First Flock Agent

In this example, we'll walk you through creating and running a simple Flock system with a single agent.
Flock enables you to build LLM-powered agents by simply declaring what data each agent receives and what it
produces—no more tedious prompt engineering!

What you'll learn:
  - How to set up the Flock model (using litellm; check out https://docs.litellm.ai/docs/providers for valid model IDs).
  - How to create a Flock instance that serves as the central orchestrator and context holder.
  - How to define a simple agent (named "bloggy") by declaring its input and output.
  - How to add the agent to your Flock.
  - How to run the agent workflow asynchronously in local debug mode (without needing Temporal).

The "bloggy" agent in this example is designed to take a blog idea as input and generate a funny blog title
along with a list of blog headers as output.

Let's get started!
"""

import asyncio

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent


# --------------------------------
# Define the model
# --------------------------------
# Flock uses litellm to talk to LLMs
# Please consult the litellm documentation for valid IDs:
# https://docs.litellm.ai/docs/providers
MODEL = "openai/gpt-4o"

async def main():
    # --------------------------------
    # Create the flock and context
    # --------------------------------
    # The flock is the place where all the agents are at home
    # set local_debug to True to run the flock without Temporal
    # Check out the examples in /temporal to learn about Temporal
    flock = Flock(model=MODEL, local_debug=True, enable_logging=True)

    # --------------------------------
    # Create an agent
    # --------------------------------
    # The Flock doesn't believe in prompts (see the readme for more info)
    # The Flock just declares what agents get in and what agents produce
    # bloggy takes in a blog_idea and outputs a funny_blog_title 
    # and blog_headers
    bloggy = FlockAgent(
        name="bloggy", 
        input="blog_idea", 
        output="funny_blog_title, blog_headers"
    )
    flock.add_agent(bloggy)

    # --------------------------------
    # Run the flock
    # --------------------------------
    # Tell the flock who is the starting and what input to give it
    await flock.run_async(
        start_agent=bloggy, 
        input={"blog_idea": "A blog about cats"}
    )

if __name__ == "__main__":
    asyncio.run(main())

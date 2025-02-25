"""Example demonstrating the agent-based auto-handoff feature.

This example shows how to use the agent-based auto-handoff feature to dynamically
determine the next agent in a workflow using a dedicated HandoffAgent.
"""

import asyncio
from typing import Dict, Any

from flock.core import Flock, FlockAgent


async def main():
    """Run the example."""
    # Create a Flock instance
    flock = Flock(model="openai/gpt-4o")

    # Create agents
    research_agent = FlockAgent(
        name="research_agent",
        description="Researches a topic and provides detailed findings",
        input="topic: str | The topic to research",
        output="findings: str | Detailed research findings",
    )
    research_agent.hand_off = "auto_handoff"

    summary_agent = FlockAgent(
        name="summary_agent",
        description="Creates a concise summary of research findings",
        input="findings: str | The research findings to summarize",
        output="summary: str | A concise summary of the findings",
    )

    blog_agent = FlockAgent(
        name="blog_agent",
        description="Creates a well-structured blog post based on research",
        input="findings: str | The research findings to use for the blog",
        output="blog_post: str | A complete blog post",
    )

    presentation_agent = FlockAgent(
        name="presentation_agent",
        description="Creates a presentation outline based on research",
        input="findings: str | The research findings to use for the presentation",
        output="presentation: str | A presentation outline",
    )

    # Add agents to the flock
    flock.add_agent(research_agent)
    flock.add_agent(summary_agent)
    flock.add_agent(blog_agent)
    flock.add_agent(presentation_agent)

    # Run the workflow with agent-based router
    print("Running workflow with agent-based router...")
    result = await flock.run(
        start_agent=research_agent,
        input={"topic": "Artificial Intelligence"},
        context={
            "router_type": "agent",  # Use the agent-based router
            "router_config": None,   # Use default configuration
        },
    )

    # Print the result
    print("\nWorkflow Result:")
    print_result(result)


def print_result(result: Dict[str, Any]):
    """Print the result in a readable format."""
    print("-" * 80)
    for key, value in result.items():
        print(f"{key}:")
        if isinstance(value, str) and len(value) > 100:
            # Print first 100 characters of long strings
            print(f"  {value[:100]}...")
        else:
            print(f"  {value}")
    print("-" * 80)


if __name__ == "__main__":
    asyncio.run(main())

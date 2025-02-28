"""Example demonstrating how to use routers with agents.

This example shows how to use different routers with agents for auto-handoff.
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
    # Create and attach an AgentRouter to the research agent
    from flock.routers.agent.agent_router import AgentRouter, AgentRouterConfig
    
    agent_router = AgentRouter(
        registry=None,  # Will be set by the framework
        config=AgentRouterConfig(
            confidence_threshold=0.6,  # Higher threshold for more confident decisions
        )
    )
    research_agent.handoff_router = agent_router

    summary_agent = FlockAgent(
        name="summary_agent",
        description="Creates a concise summary of research findings",
        input="findings: str | The research findings to summarize",
        output="summary: str | A concise summary of the findings",
    )
    # Create and attach an LLMRouter to the summary agent
    from flock.routers.llm.llm_router import LLMRouter, LLMRouterConfig
    
    llm_router = LLMRouter(
        config=LLMRouterConfig(
            temperature=0.1,  # Lower temperature for more deterministic decisions
            confidence_threshold=0.7,  # Higher threshold for more confident decisions
        )
    )
    summary_agent.handoff_router = llm_router

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

    # Run the workflow starting with the research agent
    print("Running workflow with agent-based router...")
    result = await flock.run(
        start_agent=research_agent,
        input={"topic": "Artificial Intelligence"},
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

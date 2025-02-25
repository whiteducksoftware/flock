"""Example comparing the original auto-handoff with the agent-based auto-handoff.

This example demonstrates the differences between the original auto-handoff
implementation and the new agent-based auto-handoff implementation.
"""

import asyncio
import time
from typing import Dict, Any

from flock.core import Flock, FlockAgent


async def run_llm_router():
    """Run the workflow with the LLM-based router."""
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

    # Run the workflow with original auto-handoff
    print("Running workflow with original auto-handoff...")
    start_time = time.time()
    result = await flock.run(
        start_agent=research_agent,
        input={"topic": "Artificial Intelligence"},
        # No use_agent_based_handoff flag, so it uses the original implementation
    )
    end_time = time.time()

    # Print the result
    print(f"\nOriginal Auto-Handoff Result (took {end_time - start_time:.2f} seconds):")
    print_result(result)
    
    return result


async def run_agent_based_auto_handoff():
    """Run the workflow with the agent-based auto-handoff."""
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

    # Run the workflow with agent-based auto-handoff
    print("\nRunning workflow with agent-based auto-handoff...")
    start_time = time.time()
    result = await flock.run(
        start_agent=research_agent,
        input={"topic": "Artificial Intelligence"},
        context={"use_agent_based_handoff": True},
    )
    end_time = time.time()

    # Print the result
    print(f"\nAgent-Based Auto-Handoff Result (took {end_time - start_time:.2f} seconds):")
    print_result(result)
    
    return result


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


async def main():
    """Run both auto-handoff implementations and compare the results."""
    # Run the original auto-handoff
    original_result = await run_original_auto_handoff()
    
    # Run the agent-based auto-handoff
    agent_based_result = await run_agent_based_auto_handoff()
    
    # Compare the results
    print("\nComparison:")
    print("-" * 80)
    
    # Determine which agent was selected in each case
    original_agent = list(original_result.keys())[0] if original_result else "None"
    agent_based_agent = list(agent_based_result.keys())[0] if agent_based_result else "None"
    
    print(f"Original Auto-Handoff selected: {original_agent}")
    print(f"Agent-Based Auto-Handoff selected: {agent_based_agent}")
    
    print("-" * 80)
    print("Note: The agent selection may differ between runs due to the probabilistic")
    print("nature of the LLM. The agent-based approach provides more transparency")
    print("and control over the selection process, as it uses a dedicated agent")
    print("with a clear input/output contract.")
    print("-" * 80)


if __name__ == "__main__":
    asyncio.run(main())

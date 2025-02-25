"""
Auto-Handoff Example

This example demonstrates how to use the auto-handoff feature in Flock.
With auto-handoff, the LLM decides which agent to hand off to next based on the current agent's output.
"""

import asyncio
from flock.core import Flock, FlockAgent


# Define the agents
research_agent = FlockAgent(
    name="research_agent",
    model="openai/gpt-4o",
    description="""
    A research agent that gathers information about a given topic.
    It searches for relevant information and provides a comprehensive overview.
    """,
    input="topic: str | The topic to research",
    output="""
        overview: str | A brief overview of the topic,
        key_points: list[str] | Key points about the topic,
        sources: list[str] | Sources of information
    """,
)

summary_agent = FlockAgent(
    name="summary_agent",
    model="openai/gpt-4o",
    description="""
    A summary agent that creates a concise summary of research findings.
    It takes research results and distills them into a brief, easy-to-understand summary.
    """,
    input="""
        overview: str | A brief overview of the topic,
        key_points: list[str] | Key points about the topic
    """,
    output="summary: str | A concise summary of the research findings",
)

blog_post_agent = FlockAgent(
    name="blog_post_agent",
    model="openai/gpt-4o",
    description="""
    A blog post agent that creates a well-structured blog post based on research findings.
    It takes research results and creates an engaging, informative blog post.
    """,
    input="""
        overview: str | A brief overview of the topic,
        key_points: list[str] | Key points about the topic
    """,
    output="""
        title: str | An engaging title for the blog post,
        content: str | The full content of the blog post,
        tags: list[str] | Relevant tags for the blog post
    """,
)

presentation_agent = FlockAgent(
    name="presentation_agent",
    model="openai/gpt-4o",
    description="""
    A presentation agent that creates a presentation outline based on research findings.
    It takes research results and creates a structured presentation with slides and talking points.
    """,
    input="""
        overview: str | A brief overview of the topic,
        key_points: list[str] | Key points about the topic
    """,
    output="""
        title: str | A title for the presentation,
        slides: list[dict] | A list of slides, each with a title and bullet points,
        notes: str | Speaker notes for the presentation
    """,
)


async def main():
    # Create a Flock instance
    flock = Flock(model="openai/gpt-4o")
    
    # Add the agents to the flock
    flock.add_agent(research_agent)
    flock.add_agent(summary_agent)
    flock.add_agent(blog_post_agent)
    flock.add_agent(presentation_agent)
    
    # Set the research agent to use auto-handoff
    research_agent.hand_off = "auto_handoff"
    
    # Run the flock with the research agent as the starting point
    topic = input("Enter a topic to research: ")
    result = await flock.run_async(
        start_agent=research_agent,
        input={"topic": topic}
    )
    
    # Print the result
    print("\n=== Final Result ===\n")
    
    if "summary" in result:
        print(f"Summary: {result['summary']}")
    elif "title" in result and "content" in result:
        print(f"Blog Post: {result['title']}")
        print(f"\n{result['content']}")
    elif "title" in result and "slides" in result:
        print(f"Presentation: {result['title']}")
        for i, slide in enumerate(result['slides']):
            print(f"\nSlide {i+1}: {slide['title']}")
            for bullet in slide.get('bullets', []):
                print(f"  • {bullet}")
    else:
        print("Research Results:")
        print(f"Overview: {result.get('overview', '')}")
        print("\nKey Points:")
        for point in result.get('key_points', []):
            print(f"  • {point}")
    
    print("\n=== Agent Chain ===\n")
    # Print the agent chain from the context
    for entry in flock.context.history:
        if entry.get("hand_off"):
            next_agent = entry["hand_off"].get("next_agent", "None")
            print(f"{entry['agent']} -> {next_agent}")
        else:
            print(f"{entry['agent']} (final agent)")


if __name__ == "__main__":
    asyncio.run(main())

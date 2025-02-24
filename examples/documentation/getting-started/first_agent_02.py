from flock.core import Flock, FlockAgent
from flock.core.tools import basic_tools

# Get your flock ready for action!
flock = Flock(
    model="openai/gpt-4",  # Pick your favorite model
)

# Meet your new AI friend
bloggy = FlockAgent(
            name="bloggy",
            input="topic",
            description="Bloggy creates fun blog outlines to any given topic",
            output="""
                catchy_title: str | In all caps, 
                blog_headers: list[str] | Catchy sub-headers
            """
        )
# Add your friend to the flock
flock.add_agent(bloggy)

# Let's see what they can do!
result = flock.run(
    start_agent=bloggy,
    input={"topic": "Why robots make great pets"}
)


# Check out their work
print("✨ Title:", result.funny_blog_title)
print("\n📝 Headers:", result.blog_headers)
print("\n📝 Analysis:", result.analysis_results)
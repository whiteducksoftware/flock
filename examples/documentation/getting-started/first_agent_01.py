from flock.core import Flock, FlockAgent

# Get your flock ready for action!
flock = Flock(
    model="openai/gpt-4",  # Pick your favorite model
    local_debug=True       # See what's happening behind the scenes
)

# Meet your new AI friend
bloggy = FlockAgent(
    name="bloggy",
    input="topic",
    output="catchy_title, blog_headers"
)

# Add your friend to the flock
flock.add_agent(bloggy)

# Let's see what they can do!
result = flock.run(
    start_agent=bloggy,
    input={"topic": "Why robots make great pets"}
)

# Check out their work
print("✨ Title:", result.catchy_title)
print("\n📝 Headers:", result.blog_headers)
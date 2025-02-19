from flock.core import Flock, FlockAgent
from flock.core.tools import basic_tools

# Get your flock ready for action!
flock = Flock(
    model="openai/gpt-4",  # Pick your favorite model
    local_debug=True       # See what's happening behind the scenes
)

# Meet your new AI friend
# bloggy = FlockAgent(
#             name="bloggy",
#             input="topic",
#             description="Bloggy creates fun blog outlines to any given topic",
#             output="""
#                 catchy_title: str | In all caps, 
#                 blog_headers: list[str] | Catchy sub-headers
#             """
#         )
# # Add your friend to the flock
# flock.add_agent(bloggy)

# # Let's see what they can do!
# result = flock.run(
#     start_agent=bloggy,
#     input={"topic": "Why robots make great pets"}
# )


bloggy = FlockAgent(
    name="bloggy",
    input="blog_idea: str|The topic to blog about",
    output=(
        "funny_blog_title: str|A catchy title for the blog, "
        "blog_headers: list[str]|List of section headers for the blog"
        "analysis_results: dict[str,Any] | Result of calculated analysis if necessary"
    ),
    tools=[basic_tools.web_search_duckduckgo, basic_tools.code_eval],
)
flock.add_agent(bloggy)
result = flock.run(
    input={"blog_idea": "A blog about cats, with an analysis how old the oldest cat became in days"},
    start_agent=bloggy
)

# Check out their work
print("✨ Title:", result.catchy_title)
print("\n📝 Headers:", result.blog_headers)
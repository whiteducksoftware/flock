from flock.core import Flock, FlockAgent
from flock.core.tools import basic_tools

# Get your flock ready for action!
flock = Flock(
    model="openai/gpt-4",  # Pick your favorite model  
    enable_logging=True
)


bloggy = FlockAgent(
    name="bloggy",
    description="Bloggy creates fun blog outlines and analysis to any given topic",
    input="blog_idea: str|The topic to blog about",
    output=(
        "funny_blog_title: str|A catchy title for the blog, "
        "blog_headers: list[str]|List of section headers for the blog, "
        "analysis_results: dict[str,int] | Result of all analysis done as key-value pairs"
    ),
    tools=[basic_tools.web_search_duckduckgo, basic_tools.code_eval],
)
flock.add_agent(bloggy)
result = flock.run(
    input={"blog_idea": "A blog about cats, with an analysis how old the oldest cat became in days"},
    start_agent=bloggy
)

# Check out their work
print("✨ Title:", result.funny_blog_title)
print("\n📝 Headers:", result.blog_headers)
print("\n📝 Analysis:", result.analysis_results)
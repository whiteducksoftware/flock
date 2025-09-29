from flock.core import Flock, FlockFactory, flock_tool
from flock.core.logging.formatters.themes import OutputTheme

@flock_tool
def write_file(string: str, file_path: str) -> None:
  with open(file_path, "w") as f:
    f.write(string)


flock = Flock(model="azure/gpt-4.1")

read_website_fast_mcp_server = FlockFactory.create_mcp_server(
    name="read-website-fast-mcp-server",
    enable_tools_feature=True,
    connection_params=FlockFactory.StdioParams(
        command="npx",
        args=[
            "-y",
            "@just-every/mcp-read-website-fast"
        ],
    ),
)
flock.add_server(read_website_fast_mcp_server)


agent = FlockFactory.create_default_agent(
    name="my_agent",
    input="url",
    output="title, headings: list[str],"
    "entities_and_metadata: list[dict[str, str]],"
    "type:Literal['news', 'blog', 'opinion piece', 'tweet']",
    servers=[read_website_fast_mcp_server],
    tools=[write_file],
    enable_rich_tables=True,  # Instead of the json output, you can use the rich library to render the output as a table
    output_theme=OutputTheme.aardvark_blue,  # flock also comes with a few themes
    use_cache=False,  # flock will cache the result of the agent and if the input is the same as before, the agent will return the cached result
)
flock.add_agent(agent)



result = flock.run(
    agent=agent,
    input={
        "url": "https://lite.cnn.com/travel/alexander-the-great-macedon-persian-empire-darius/index.html"
    },
)



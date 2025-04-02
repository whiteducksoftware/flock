"""
Title: Advanced Flock Agent with Caching, Type Hints, and Tool Integration

In this example, we'll show you how to build a more advanced Flock system that:
  - Uses a custom output formatter (RichTables) for a polished, swaggy display.
  - Defines output types using standard Python type hints (including lists and Literals) for structured results.
  - Integrates external tools (like a web content scraper) so that agents can perform more complex operations.
  - Leverages caching so that if an agent is called with the same input, the cached result is returned—this is particularly
    useful for expensive operations such as web scraping or during debugging.

The agent in this example takes a URL as input and outputs:
  - A title,
  - A list of headings,
  - A list of dictionaries mapping entities to metadata, and
  - A type (limited to one of 'news', 'blog', 'opinion piece', or 'tweet').

After executing the agent, you can work with the result as a real Python object that respects the defined types.

Let's dive in!
"""


from pprint import pprint

from flock.core import Flock, FlockFactory
from flock.core.logging.formatters.themes import OutputTheme
from flock.core.tools import basic_tools
from flock.modules.memory.memory_module import MemoryModule, MemoryModuleConfig
from flock.modules.zep.zep_module import ZepModule, ZepModuleConfig


flock = Flock(enable_logging=True)

agent = FlockFactory.create_default_agent(
    name="my_agent",
    input="url",
    output="title, headings: list[str]," 
            "entities_and_metadata: list[dict[str, str]]," 
            "type:Literal['news', 'blog', 'opinion piece', 'tweet']",
    tools=[basic_tools.get_web_content_as_markdown],
    enable_rich_tables=True,
    output_theme=OutputTheme.aardvark_blue,
)

# --------------------------------
# Add a module to the agent
# --------------------------------
# Modules are modules (heh) that can be added to an agent to extend its capabilities.
# Modules run at certain points in the agent's lifecycle and can manipulate the inputs and outputs and the agent itself.
# In this case, we're adding the Zep module to the agent, 
# which allows it to use Zep to store and retrieve information in Knowledge Graphs.
# Currently there are two graph based modules: Zep and Memory.
# Memory is more lightweight and easier to use, but Zep offers more features and is more powerful.

# zep = ZepModule(name="zep",config=ZepModuleConfig())
# agent.add_module(zep)

mem = MemoryModule(name="mem_split",config=MemoryModuleConfig(splitting_mode="characters", number_of_concepts_to_extract=5))
agent.add_module(mem)


flock.add_agent(agent)
result = flock.run(
    start_agent=agent,
    input={"url": "https://lite.cnn.com/travel/alexander-the-great-macedon-persian-empire-darius/index.html"},
)


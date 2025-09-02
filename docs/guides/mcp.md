# MCP Integration 🔌

Flock supports the Model Context Protocol (MCP) to expose and consume tools over standard transports (stdio, SSE, websockets, streamable http).

## Creating a Server (Factory)

```python
from flock.core import FlockFactory

server = FlockFactory.create_mcp_server(
    name="my-tools",
    connection_params=FlockFactory.StdioParams(command="uvx", args=["python", "./server.py"]),
    enable_tools_feature=True,
)

flock.add_server(server)
```

## Using MCP Tools in Agents

Registered servers contribute tools to an agent at runtime; the default evaluator will merge MCP tools and native tools when selecting the DSPy program (e.g., `ReAct`).

```python
from flock.core import DefaultAgent

agent = DefaultAgent(
    name="search_and_summarize",
    input="query: str",
    output="summary: str",
    servers=["my-tools"],  # or pass the server object
)
```

See `flock.core.mcp.*` for configuration options and callbacks.

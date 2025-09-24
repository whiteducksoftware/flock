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

## Tool Whitelisting 🛡️

Flock provides a two-level tool filtering system to control which tools are available to agents. This allows for fine-grained security and functionality control.

### How Tool Filtering Works

Tool filtering operates on two levels:

1. **Server-level filtering**: Filters tools at the MCP server level
2. **Agent-level filtering**: Further restricts tools at the individual agent level

**Recommendation**: Use agent-level filtering as the primary mechanism, as it provides better granular control and allows different agents to use different subsets of tools from the same server.

### Server-Level Tool Filtering

Filter tools at the MCP server level using `tool_whitelist` and `allow_all_tools` parameters:

```python
from flock.core import FlockFactory

# Create server with tool whitelist
server = FlockFactory.create_mcp_server(
    name="restricted-tools",
    connection_params=FlockFactory.StdioParams(command="uvx", args=["python", "./server.py"]),
    enable_tools_feature=True,
    tool_whitelist=["search_web", "get_weather"],  # Only allow these tools
    allow_all_tools=False,  # Explicitly disable all other tools
)

# Alternative: Allow all tools (default behavior)
server = FlockFactory.create_mcp_server(
    name="all-tools",
    connection_params=FlockFactory.StdioParams(command="uvx", args=["python", "./server.py"]),
    enable_tools_feature=True,
    allow_all_tools=True,  # Default: no filtering at server level
)
```

### Agent-Level Tool Filtering (Recommended)

Filter tools at the agent level using the `tool_whitelist` parameter. This approach is preferred as it allows multiple agents to use different tool subsets from the same server:

```python
from flock.core import DefaultAgent

# Agent with restricted tool access
research_agent = DefaultAgent(
    name="research_agent",
    input="query: str",
    output="research_result: str",
    servers=["my-tools"],
    tool_whitelist=["search_web", "summarize_text"],  # Only these tools allowed
)

# Agent with different tool restrictions
weather_agent = DefaultAgent(
    name="weather_agent", 
    input="location: str",
    output="weather_report: str",
    servers=["my-tools"],
    tool_whitelist=["get_weather", "get_location"],  # Different tool subset
)

# Agent with no tool restrictions (uses all available tools)
general_agent = DefaultAgent(
    name="general_agent",
    input="task: str", 
    output="result: str",
    servers=["my-tools"],
    # No tool_whitelist = all tools from server are available
)
```

### Combined Filtering

When both server-level and agent-level whitelists are used, the agent can only access tools that are allowed by **both** filters:

```python
# Server allows: ["search_web", "get_weather", "summarize_text", "translate"]
server = FlockFactory.create_mcp_server(
    name="limited-server",
    connection_params=FlockFactory.StdioParams(command="uvx", args=["python", "./server.py"]),
    tool_whitelist=["search_web", "get_weather", "summarize_text", "translate"],
    allow_all_tools=False,
)

# Agent further restricts to: ["search_web", "summarize_text"]
agent = DefaultAgent(
    name="content_agent",
    input="topic: str",
    output="content: str", 
    servers=["limited-server"],
    tool_whitelist=["search_web", "summarize_text"],  # Agent can't access get_weather or translate
)

# Final available tools for this agent: ["search_web", "summarize_text"]
```

### Implementation Details

#### Tool Identification

- **MCP Tools**: Identified by their `name` attribute
- **Native Python Tools**: Identified by their `__name__` attribute (function name)

#### Filtering Behavior

1. **Server-level filtering**: 
   - If `allow_all_tools=False` and `tool_whitelist` is provided, only whitelisted tools are exposed
   - If `allow_all_tools=True` (default), all tools are exposed regardless of whitelist

2. **Agent-level filtering**:
   - If `tool_whitelist` is provided, only tools in the whitelist are available to the agent
   - If `tool_whitelist` is `None` or empty, all tools from the server are available

3. **Combined filtering**:
   - Final tool set = Server allowed tools ∩ Agent allowed tools

### Security Considerations

- **Defense in depth**: Use both server and agent level filtering for maximum security
- **Principle of least privilege**: Only grant access to tools that agents actually need
- **Tool naming**: Ensure consistent and predictable tool names for reliable filtering
- **Validation**: Test your whitelist configurations to ensure expected tools are available

### Examples by Use Case

#### Development Environment
```python
# Allow all tools during development
dev_agent = DefaultAgent(
    name="dev_agent",
    servers=["dev-tools"],
    # No whitelist = all tools available
)
```

#### Production Environment with Security
```python
# Restrict to essential tools only
prod_agent = DefaultAgent(
    name="prod_agent", 
    servers=["prod-tools"],
    tool_whitelist=["safe_search", "validate_input", "log_activity"],
)
```

#### Multi-Agent System with Role-Based Access
```python
# Search specialist
search_agent = DefaultAgent(
    name="searcher",
    servers=["shared-tools"],
    tool_whitelist=["web_search", "database_query"],
)

# Content specialist  
content_agent = DefaultAgent(
    name="writer",
    servers=["shared-tools"], 
    tool_whitelist=["text_generation", "grammar_check", "plagiarism_check"],
)

# Admin agent with full access
admin_agent = DefaultAgent(
    name="admin",
    servers=["shared-tools"],
    # No whitelist = full access to all server tools
)
```

## Best Practices

1. **Prefer agent-level filtering** over server-level filtering for flexibility
2. **Use descriptive tool names** that clearly indicate their function
3. **Test whitelist configurations** in development before deploying
4. **Document tool dependencies** for each agent to avoid runtime errors
5. **Monitor tool usage** to identify unused whitelisted tools
6. **Regular security reviews** of tool access patterns

See `flock.core.mcp.*` for configuration options and callbacks.

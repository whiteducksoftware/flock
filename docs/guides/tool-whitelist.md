# Tool Whitelisting & Security 🛡️

The Flock framework provides a comprehensive tool filtering system that allows you to control which tools are available to your agents. This is essential for security, preventing tool conflicts, and ensuring agents only access the functionality they need.

## Overview

Tool filtering in Flock operates on two levels:

1. **Server-level filtering**: Controls which tools are exposed by MCP servers
2. **Agent-level filtering**: Controls which tools individual agents can access

**Best Practice**: Use agent-level filtering as your primary security mechanism, as it provides better granular control and allows different agents to use different tool subsets from the same server.

## How Tool Filtering Works

### Filtering Process

1. **MCP Server** exposes tools based on its whitelist configuration
2. **Agent** further filters available tools based on its own whitelist
3. **Final tool set** = Server allowed tools ∩ Agent allowed tools

### Tool Identification

- **MCP Tools**: Identified by their `name` attribute
- **Native Python Tools**: Identified by their `__name__` attribute (function name)

## Agent-Level Filtering (Recommended)

Agent-level filtering is the preferred approach for controlling tool access:

```python
from flock.core import DefaultAgent

# Agent with specific tool restrictions
research_agent = DefaultAgent(
    name="research_agent",
    input="query: str",
    output="research_result: str",
    servers=["my-tools"],
    tool_whitelist=["search_web", "summarize_text", "extract_facts"],
)

# Different agent with different tool access
writing_agent = DefaultAgent(
    name="writing_agent",
    input="content: str", 
    output="polished_content: str",
    servers=["my-tools"],
    tool_whitelist=["grammar_check", "style_improve", "plagiarism_check"],
)

# Agent with no restrictions (all server tools available)
admin_agent = DefaultAgent(
    name="admin_agent",
    input="task: str",
    output="result: str", 
    servers=["my-tools"],
    # No tool_whitelist = access to all tools from the server
)
```

### Benefits of Agent-Level Filtering

- **Granular Control**: Each agent gets exactly the tools it needs
- **Security**: Prevents agents from accessing inappropriate tools
- **Isolation**: Tool failures in one agent don't affect others
- **Flexibility**: Same server can serve multiple agents with different needs
- **Easier Testing**: Test individual agents with specific tool sets

## Server-Level Filtering

Server-level filtering controls which tools are exposed by MCP servers:

```python
from flock.core import FlockFactory

# Server with restricted tool set
restricted_server = FlockFactory.create_mcp_server(
    name="restricted-tools",
    connection_params=FlockFactory.StdioParams(
        command="uvx", 
        args=["python", "./server.py"]
    ),
    enable_tools_feature=True,
    tool_whitelist=["safe_search", "data_validate", "log_activity"],
    allow_all_tools=False,  # Enforce whitelist
)

# Server that allows all tools (default)
open_server = FlockFactory.create_mcp_server(
    name="open-tools",
    connection_params=FlockFactory.StdioParams(
        command="uvx",
        args=["python", "./open_server.py"]
    ),
    enable_tools_feature=True,
    allow_all_tools=True,  # Default: no server-level filtering
)
```

### Server Configuration Options

- `tool_whitelist`: List of tool names to allow from the server
- `allow_all_tools`: 
  - `True` (default): All tools available, whitelist ignored
  - `False`: Only whitelisted tools available

## Combined Filtering Examples

### Example 1: Layered Security

```python
# Server allows a broad set of "safe" tools
safe_server = FlockFactory.create_mcp_server(
    name="safe-server",
    connection_params=FlockFactory.StdioParams(
        command="uvx", 
        args=["python", "./safe_server.py"]
    ),
    tool_whitelist=[
        "search_web", "get_weather", "summarize_text", 
        "translate", "calculate", "validate_email"
    ],
    allow_all_tools=False,
)

# Agents further restrict based on their role
search_agent = DefaultAgent(
    name="searcher",
    servers=["safe-server"],
    tool_whitelist=["search_web", "summarize_text"],  # Only search tools
)

translation_agent = DefaultAgent(
    name="translator", 
    servers=["safe-server"],
    tool_whitelist=["translate", "validate_email"],  # Only translation tools
)

# Final tool access:
# - search_agent: ["search_web", "summarize_text"]
# - translation_agent: ["translate", "validate_email"]
```

### Example 2: Development vs Production

```python
# Development: Allow all tools for flexibility
if environment == "development":
    agent = DefaultAgent(
        name="dev_agent",
        servers=["dev-tools"],
        # No whitelist = all tools available
    )

# Production: Strict tool control
else:
    agent = DefaultAgent(
        name="prod_agent",
        servers=["prod-tools"],
        tool_whitelist=["approved_search", "safe_calculate", "log_only"],
    )
```

## Security Best Practices

### 1. Principle of Least Privilege

Only grant access to tools that agents actually need:

```python
# Bad: Agent gets access to all tools
broad_agent = DefaultAgent(
    name="content_agent",
    servers=["all-tools"],
    # No whitelist = potential security risk
)

# Good: Agent gets only necessary tools
focused_agent = DefaultAgent(
    name="content_agent", 
    servers=["all-tools"],
    tool_whitelist=["text_generate", "grammar_check", "spell_check"],
)
```

### 2. Defense in Depth

Use both server and agent filtering:

```python
# Server provides first line of defense
secure_server = FlockFactory.create_mcp_server(
    name="secure-server",
    tool_whitelist=["approved_tool_1", "approved_tool_2", "approved_tool_3"],
    allow_all_tools=False,
)

# Agent provides second line of defense
secure_agent = DefaultAgent(
    name="secure_agent",
    servers=["secure-server"],
    tool_whitelist=["approved_tool_1"],  # Even more restrictive
)
```

### 3. Tool Naming Convention

Use consistent, descriptive tool names:

```python
# Good: Clear, descriptive names
tool_whitelist = [
    "web_search_safe",       # Safe web searching
    "email_validate_format", # Email format validation
    "text_summarize_simple", # Basic text summarization
]

# Avoid: Vague or ambiguous names
tool_whitelist = [
    "tool1",     # What does this do?
    "process",   # Too generic
    "helper",    # Unclear purpose
]
```

### 4. Regular Security Audits

Monitor and review tool access patterns:

```python
# Log tool usage for security audits
from flock.components.utility.metrics_utility_component import MetricsUtilityComponent

agent = DefaultAgent(
    name="monitored_agent",
    tool_whitelist=["search", "summarize"],
    # Metrics component will track tool usage
)

# Review logs regularly to ensure tools are being used as expected
```

## Testing Tool Whitelists

### Unit Testing

Test that agents can only access whitelisted tools:

```python
def test_tool_whitelist():
    agent = DefaultAgent(
        name="test_agent",
        tool_whitelist=["allowed_tool"],
    )
    
    # Agent should have access to allowed tools
    assert "allowed_tool" in agent.get_available_tools()
    
    # Agent should not have access to other tools
    assert "forbidden_tool" not in agent.get_available_tools()
```

### Integration Testing

Test tool filtering across the entire workflow:

```python
def test_end_to_end_filtering():
    # Set up server with limited tools
    server = FlockFactory.create_mcp_server(
        name="test-server",
        tool_whitelist=["tool_a", "tool_b", "tool_c"],
        allow_all_tools=False,
    )
    
    # Set up agent with even more limited tools
    agent = DefaultAgent(
        name="test_agent",
        servers=["test-server"],
        tool_whitelist=["tool_a"],
    )
    
    # Run agent and verify only allowed tools are used
    result = flock.run(agent="test_agent", input={"query": "test"})
    
    # Verify tool usage in result or logs
    assert only_allowed_tools_were_used(result)
```

## Common Patterns

### Role-Based Access Control

```python
# Define tool sets for different roles
ADMIN_TOOLS = ["system_admin", "user_manage", "data_export", "log_access"]
USER_TOOLS = ["search", "summarize", "translate"]
GUEST_TOOLS = ["search", "basic_info"]

# Create agents with role-appropriate tools
admin_agent = DefaultAgent(
    name="admin",
    tool_whitelist=ADMIN_TOOLS,
)

user_agent = DefaultAgent(
    name="user", 
    tool_whitelist=USER_TOOLS,
)

guest_agent = DefaultAgent(
    name="guest",
    tool_whitelist=GUEST_TOOLS,
)
```

### Environment-Specific Filtering

```python
import os

# Different tool sets for different environments
if os.getenv("ENVIRONMENT") == "production":
    ALLOWED_TOOLS = ["prod_search", "prod_log", "prod_validate"]
elif os.getenv("ENVIRONMENT") == "staging":
    ALLOWED_TOOLS = ["staging_search", "debug_log", "test_validate"]
else:  # development
    ALLOWED_TOOLS = None  # All tools allowed in dev

agent = DefaultAgent(
    name="env_agent",
    tool_whitelist=ALLOWED_TOOLS,
)
```

### Feature Flags

```python
# Use feature flags to control tool access
FEATURE_FLAGS = {
    "enable_advanced_search": True,
    "enable_data_export": False,
    "enable_external_api": True,
}

# Build tool whitelist based on feature flags
allowed_tools = ["basic_search", "summarize"]

if FEATURE_FLAGS["enable_advanced_search"]:
    allowed_tools.append("advanced_search")

if FEATURE_FLAGS["enable_data_export"]:
    allowed_tools.append("export_data")

if FEATURE_FLAGS["enable_external_api"]:
    allowed_tools.extend(["api_call", "webhook_send"])

agent = DefaultAgent(
    name="feature_controlled_agent",
    tool_whitelist=allowed_tools,
)
```

## Troubleshooting

### Common Issues

1. **Tool Not Available**: Check both server and agent whitelists
2. **Unexpected Tool Access**: Verify whitelist configuration
3. **Tool Name Mismatch**: Ensure consistent naming between server and agent

### Debugging Tool Access

```python
# Check what tools are available to an agent
available_tools = agent.get_available_tools()
print(f"Available tools: {available_tools}")

# Check server-provided tools
server_tools = server.get_available_tools()
print(f"Server tools: {server_tools}")

# Check intersection
final_tools = set(server_tools) & set(agent.tool_whitelist or server_tools)
print(f"Final tools: {final_tools}")
```

### Logging Tool Usage

Enable detailed logging to track tool access:

```python
import logging

# Enable debug logging for tool access
logging.getLogger("flock.core.agent.lifecycle").setLevel(logging.DEBUG)
logging.getLogger("flock.core.mcp").setLevel(logging.DEBUG)

# Tool access will be logged during execution
agent.run(input={"query": "test"})
```

## Migration Guide

### From No Filtering to Filtered

1. **Audit Current Tool Usage**: Review logs to see which tools are actually used
2. **Create Minimal Whitelist**: Start with only essential tools
3. **Test Thoroughly**: Ensure agents still function correctly
4. **Gradually Restrict**: Remove unused tools from whitelist over time

### From Server to Agent Filtering

1. **Document Current Server Whitelists**: Know what's currently allowed
2. **Move Restrictions to Agents**: Add tool_whitelist to agent configurations
3. **Relax Server Restrictions**: Set allow_all_tools=True on servers
4. **Test Individual Agents**: Verify each agent has appropriate access

## Conclusion

Tool whitelisting is a powerful security feature that should be used in all production Flock deployments. By following the patterns and best practices outlined in this guide, you can ensure your agents have appropriate tool access while maintaining security and reliability.

Remember:
- **Prefer agent-level filtering** for flexibility and security
- **Use descriptive tool names** for clarity
- **Test your whitelist configurations** thoroughly
- **Monitor tool usage** in production
- **Review and update** whitelists regularly
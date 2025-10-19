# MCP Root/Mount Point Feature

## Overview

The MCP Root/Mount Point feature allows you to control which filesystem directories MCP servers can access on a **per-agent, per-server** basis. This provides fine-grained security and isolation for agents working with filesystem tools.

## Key Features

✨ **Server-Specific Mounts**: Different mount points for different MCP servers
🔒 **Per-Agent Isolation**: Each agent can have its own directory restrictions
🎯 **Explicit API**: Clear syntax showing which mounts apply to which servers
🔄 **Backward Compatible**: Old `.mount()` API still works (with deprecation warning)

## Architecture

### How It Works

1. **Agent Definition**: Use `.with_mcps({server: [paths]})` to specify mount points per server
2. **Runtime**: Server-specific mount points are passed to the MCP client manager
3. **Client Creation**: Each (agent_id, run_id) gets isolated MCP client with server-specific roots
4. **Server Notification**: Client notifies each MCP server only about roots relevant to it

### Protocol Flow

```
Agent.with_mcps({"filesystem": ["/workspace/src"]})
    ↓
Manager.get_tools_for_agent(server_mounts={"filesystem": ["/workspace/src"]})
    ↓
For each server:
    Manager.get_client(server_name, mount_points=["/workspace/src"])
    ↓
    Client.__init__ (sets current_roots from config.mount_points)
    ↓
    Client._perform_initial_handshake()
    ↓
    client_session.send_roots_list_changed()  [Notify server]
    ↓
    Server calls list_roots_callback()  [Request roots]
    ↓
    Callback returns ListRootsResult(roots=["/workspace/src"])  [Provide roots]
```

## Usage

### Basic Example - Single Server

```python
from flock import Flock
from flock.mcp import StdioServerParameters

flock = Flock(model="openai/gpt-4")

# Register MCP server with roots feature
flock.add_mcp(
    name="filesystem",
    connection_params=StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem"]
    ),
    enable_roots_feature=True
)

# Agent with server-specific mount points
(
    flock.agent("src_agent")
    .with_mcps({"filesystem": ["/workspace/src"]})  # ← Explicit server + mounts
    .consumes(Request)
    .publishes(Response)
)
```

### Multiple Mount Points for One Server

```python
# Agent with multiple mount points for a single server
(
    flock.agent("multi_dir_agent")
    .with_mcps({
        "filesystem": ["/data", "/logs", "/config"]  # Multiple directories
    })
    .consumes(Request)
    .publishes(Response)
)
```

### Multiple Servers with Different Mounts

```python
# Register multiple MCP servers
flock.add_mcp(name="filesystem", connection_params=..., enable_roots_feature=True)
flock.add_mcp(name="github", connection_params=..., enable_roots_feature=True)

# Agent using multiple servers with different mount points
(
    flock.agent("multi_server_agent")
    .with_mcps({
        "filesystem": ["/workspace/src", "/data"],  # Filesystem mounts
        "github": ["/workspace/.git"],              # GitHub mounts
    })
    .consumes(Request)
    .publishes(Response)
)
```

### Mixed Format (Backward Compatible)

```python
# Some servers with mounts, others without
(
    flock.agent("mixed_agent")
    .with_mcps([
        {"filesystem": ["/workspace/src"]},  # With mounts
        "github",                             # No mounts (unrestricted)
    ])
    .consumes(Request)
    .publishes(Response)
)
```

### No Mount Restrictions

```python
# Agent with no mount restrictions (full access)
(
    flock.agent("unrestricted_agent")
    .with_mcps(["filesystem"])  # String format = no restrictions
    .consumes(Request)
    .publishes(Response)
)
```

## API Reference

### MCPServerConfig (TypedDict)

```python
class MCPServerConfig(TypedDict, total=False):
    """Configuration for MCP server assignment to an agent.

    All fields are optional. If omitted, no restrictions apply.

    Attributes:
        roots: Filesystem paths this server can access.
               Empty list or omitted = no mount restrictions.
        tool_whitelist: Tool names the agent can use from this server.
                       Empty list or omitted = all tools available.
    """
    roots: list[str]
    tool_whitelist: list[str]
```

### AgentBuilder.with_mcps()

```python
def with_mcps(
    self,
    servers: Iterable[str] | dict[str, MCPServerConfig] | list[str | dict[str, MCPServerConfig]]
) -> AgentBuilder:
    """Assign MCP servers to agent with optional server-specific mount points.

    Args:
        servers: One of:
            - List of server names (strings) - no specific mounts
            - Dict mapping server names to MCPServerConfig - with restrictions
            - Mixed list of strings and dicts for flexibility

    Returns:
        AgentBuilder for method chaining

    Raises:
        ValueError: If any server name is not registered
        TypeError: If invalid server specification format

    Examples:
        # Simple: no mount restrictions
        agent.with_mcps(["filesystem", "github"])

        # Server-specific mounts and tool whitelist
        agent.with_mcps({
            "filesystem": {
                "roots": ["/workspace/src", "/data"],
                "tool_whitelist": ["read_file", "write_file"]
            },
            "github": {}  # No restrictions for github
        })

        # Mixed format
        agent.with_mcps([
            "github",  # No mounts
            {"filesystem": {"roots": ["/workspace/src"]}}  # With mounts
        ])
    """
```

### AgentBuilder.mount() [Deprecated]

```python
def mount(
    self,
    paths: str | list[str],
    *,
    validate: bool = False
) -> AgentBuilder:
    """Mount agent in specific directories for MCP root access.

    .. deprecated:: 0.2.0
        Use `.with_mcps({"server_name": ["/path"]})` instead.

    Args:
        paths: Single path or list of paths to mount
        validate: If True, validate that paths exist

    Returns:
        AgentBuilder for method chaining
    """
```

### Flock.add_mcp()

```python
def add_mcp(
    self,
    name: str,
    connection_params: ServerParameters,
    *,
    enable_roots_feature: bool = True,
    mount_points: list[str] | None = None,  # Global default
    ...
) -> Flock:
    """Register MCP server with optional global mount points."""
```

## Security Considerations

### Best Practices

1. **Principle of Least Privilege**: Only mount directories agents actually need
2. **Server-Specific Mounts**: Use dict format to be explicit about which server gets which mounts
3. **Agent-Specific Mounts**: Prefer per-agent mounts over global defaults
4. **Avoid Root Access**: Never mount `/` unless absolutely necessary

### Example: Secure File Processing

```python
# ❌ BAD: All servers get unrestricted access
(
    flock.agent("file_processor")
    .with_mcps(["filesystem", "github"])  # Both have unrestricted access
    .consumes(FileRequest)
    .publishes(FileData)
)

# ✅ GOOD: Each server gets only what it needs
(
    flock.agent("file_processor")
    .with_mcps({
        "filesystem": ["/data/input"],  # Filesystem only reads from input
        "github": ["/workspace/.git"],  # GitHub only accesses git directory
    })
    .consumes(FileRequest)
    .publishes(FileData)
)

# ✅ BETTER: Separate agents with minimal permissions
(
    flock.agent("file_reader")
    .with_mcps({"filesystem": ["/data/input"]})  # Read only
    .consumes(FileRequest)
    .publishes(FileData)
)

(
    flock.agent("file_writer")
    .with_mcps({"filesystem": ["/data/output"]})  # Write only
    .consumes(FileData)
    .publishes(FileResult)
)
```

## Implementation Details

### Server-Specific Mount Points

Each server only receives the mount points specified for it:

```python
agent.with_mcps({
    "filesystem": ["/workspace/src"],
    "github": ["/workspace/.git"],
})

# When connecting to "filesystem" → roots = ["/workspace/src"]
# When connecting to "github" → roots = ["/workspace/.git"]
# Each server only knows about its own roots
```

### Per-(agent_id, run_id) Isolation

Each unique (agent_id, run_id) pair gets its own isolated MCP client connection with server-specific mount points:

```python
# Same agent, different runs = different clients with same mounts
await orchestrator.invoke(agent, request_1)  # run_id=123 → client_1 (filesystem: ["/src"])
await orchestrator.invoke(agent, request_2)  # run_id=456 → client_2 (filesystem: ["/src"])
```

### Mount Point Precedence

1. **Agent-level server-specific mounts** (highest priority): `agent.with_mcps({"server": ["/path"]})`
2. **Server-level defaults**: `add_mcp(mount_points=["/path"])`
3. **No restrictions** (lowest priority): No mounts specified

### MCPRoot Format

Mount points are converted to `MCPRoot` objects:

```python
# Input
mount_points = ["/workspace/src", "/data"]

# Converted to
[
    MCPRoot(uri="file:///workspace/src", name="src"),
    MCPRoot(uri="file:///data", name="data")
]
```

## Troubleshooting

### Common Issues

**Issue**: Agent can't access files despite mount
```python
# Check if roots feature is enabled for the server
flock.add_mcp(
    name="filesystem",
    connection_params=...,
    enable_roots_feature=True  # ← Must be True
)

# Check if mounts are specified correctly
agent.with_mcps({
    "filesystem": ["/workspace/src"]  # ← Correct server name
})
```

**Issue**: Wrong server getting mount points
```python
# ❌ BAD: Typo in server name
agent.with_mcps({
    "filesytem": ["/workspace/src"]  # Typo!
})

# ✅ GOOD: Correct server name
agent.with_mcps({
    "filesystem": ["/workspace/src"]  # Must match add_mcp() name
})
```

**Issue**: Mount points not taking effect
```python
# Ensure mounts are specified in with_mcps() call
agent = (
    flock.agent("my_agent")
    .with_mcps({"filesystem": ["/path"]})  # ← Mounts here, not separate
    .consumes(Request)
    .publishes(Response)
)
```

### Debug Logging

Enable debug logging to see root notifications:

```python
import logging

logging.basicConfig(level=logging.DEBUG)

# Look for these log messages:
# INFO: Setting 2 mount point(s) for server 'filesystem' (agent=my_agent, run=123): ['file:///path1', 'file:///path2']
# DEBUG: Notifying server 'filesystem' of 2 root(s): ['file:///path1', 'file:///path2']
```

### Migration from Deprecated API

```python
# OLD (deprecated)
agent.with_mcps(["filesystem"]).mount("/workspace/src")

# NEW (recommended)
agent.with_mcps({"filesystem": ["/workspace/src"]})

# Migration for multiple servers
# OLD
agent.with_mcps(["filesystem", "github"]).mount(["/workspace/src", "/data"])

# NEW (specify per server)
agent.with_mcps({
    "filesystem": ["/workspace/src", "/data"],
    "github": []  # Or omit if no mounts needed
})
```

## Examples

See working examples in:
- [`examples/showcase/07_mcp_roots.py`](../examples/showcase/07_mcp_roots.py) - Complete demonstration
- [`examples/showcase/04_mcp_tools.py`](../examples/showcase/04_mcp_tools.py) - Basic MCP usage

## Related Documentation

- [MCP Protocol Specification](https://spec.modelcontextprotocol.io/)
- [Flock MCP Architecture](./mcp-architecture.md)
- [Agent Builder API](./agent-builder.md)

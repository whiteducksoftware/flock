from typing import TypedDict


class MCPServerConfig(TypedDict, total=False):
    """Configuration for MCP server assignment to an agent.

    All fields are optional. If omitted, no restrictions apply.

    Attributes:
        roots: Filesystem paths this server can access.
               Empty list or omitted = no mount restrictions.
        tool_whitelist: Tool names the agent can use from this server.
                       Empty list or omitted = all tools available.

    Examples:
        >>> # No restrictions
        >>> config: MCPServerConfig = {}

        >>> # Mount restrictions only
        >>> config: MCPServerConfig = {"roots": ["/workspace/data"]}

        >>> # Tool whitelist only
        >>> config: MCPServerConfig = {
        ...     "tool_whitelist": ["read_file", "write_file"]
        ... }

        >>> # Both restrictions
        >>> config: MCPServerConfig = {
        ...     "roots": ["/workspace/data"],
        ...     "tool_whitelist": ["read_file"],
        ... }
    """

    roots: list[str]
    tool_whitelist: list[str]

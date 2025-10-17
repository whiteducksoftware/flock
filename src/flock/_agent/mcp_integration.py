"""Agent MCP integration - server configuration and tool loading.

Phase 4: Extracted from agent.py to eliminate C-rated complexity in with_mcps() and _get_mcp_tools().
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any

from flock.logging.logging import get_logger


if TYPE_CHECKING:
    from flock.agent import MCPServerConfig
    from flock.orchestrator import Flock
    from flock.runtime import Context


logger = get_logger(__name__)


class MCPIntegration:
    """Handles MCP server configuration and tool loading for an agent.

    This module encapsulates all MCP-related logic including:
    - Server configuration parsing (dict, list, mixed formats)
    - Backward compatibility with old mount format
    - Tool loading and whitelisting
    - Graceful degradation on failures
    """

    def __init__(self, agent_name: str, orchestrator: Flock):
        """Initialize MCPIntegration for a specific agent.

        Args:
            agent_name: Name of the agent (for error messages and logging)
            orchestrator: Flock orchestrator instance (for MCP manager access)
        """
        self._agent_name = agent_name
        self._orchestrator = orchestrator
        self._logger = logging.getLogger(__name__)

        # Agent MCP state
        self.mcp_server_names: set[str] = set()
        self.mcp_server_mounts: dict[str, list[str]] = {}
        self.mcp_mount_points: list[str] = []  # Deprecated: Use mcp_server_mounts
        self.tool_whitelist: list[str] | None = None

    async def get_mcp_tools(self, ctx: Context) -> list[Callable]:
        """Lazy-load MCP tools from assigned servers.

        Architecture Decision: AD001 - Two-Level Architecture
        Agents fetch tools from servers registered at orchestrator level.

        Architecture Decision: AD003 - Tool Namespacing
        All tools are namespaced as {server}__{tool}.

        Architecture Decision: AD007 - Graceful Degradation
        If MCP loading fails, returns empty list so agent continues with native tools.

        Args:
            ctx: Current execution context with agent_id and run_id

        Returns:
            List of DSPy-compatible tool callables
        """
        if not self.mcp_server_names:
            # No MCP servers assigned to this agent
            return []

        try:
            # Get the MCP manager from orchestrator
            manager = self._orchestrator.get_mcp_manager()

            # Fetch tools from all assigned servers
            tools_dict = await manager.get_tools_for_agent(
                agent_id=self._agent_name,
                run_id=ctx.task_id,
                server_names=self.mcp_server_names,
                server_mounts=self.mcp_server_mounts,  # Pass server-specific mounts
            )

            # Whitelisting logic
            tool_whitelist = self.tool_whitelist
            if (
                tool_whitelist is not None
                and isinstance(tool_whitelist, list)
                and len(tool_whitelist) > 0
            ):
                filtered_tools: dict[str, Any] = {}
                for tool_key, tool_entry in tools_dict.items():
                    if isinstance(tool_entry, dict):
                        original_name = tool_entry.get("original_name", None)
                        if (
                            original_name is not None
                            and original_name in tool_whitelist
                        ):
                            filtered_tools[tool_key] = tool_entry

                tools_dict = filtered_tools

            # Convert to DSPy tool callables
            dspy_tools = []
            for namespaced_name, tool_info in tools_dict.items():
                tool_info["server_name"]
                flock_tool = tool_info["tool"]  # Already a FlockMCPTool
                client = tool_info["client"]

                # Convert to DSPy tool
                dspy_tool = flock_tool.as_dspy_tool(server=client)

                # Update name to include namespace
                dspy_tool.name = namespaced_name

                dspy_tools.append(dspy_tool)

            return dspy_tools

        except Exception as e:
            # Architecture Decision: AD007 - Graceful Degradation
            # Agent continues with native tools only
            logger.error(
                f"Failed to load MCP tools for agent {self._agent_name}: {e}",
                exc_info=True,
            )
            return []

    def configure_servers(
        self,
        servers: (
            Iterable[str]
            | dict[str, MCPServerConfig | list[str]]  # Support both new and old format
            | list[str | dict[str, MCPServerConfig | list[str]]]
        ),
        registered_servers: set[str],
    ) -> None:
        """Configure MCP servers for this agent with optional server-specific mount points.

        Architecture Decision: AD001 - Two-Level Architecture
        Agents reference servers registered at orchestrator level.

        Args:
            servers: One of:
                - List of server names (strings) - no specific mounts
                - Dict mapping server names to MCPServerConfig or list[str] (backward compatible)
                - Mixed list of strings and dicts for flexibility
            registered_servers: Set of server names registered with orchestrator (for validation)

        Raises:
            ValueError: If any server name is not registered with orchestrator
            TypeError: If server specification format is invalid

        Examples:
            >>> # Simple: no mount restrictions
            >>> integration.configure_servers(["filesystem", "github"], registered)

            >>> # New format: Server-specific config with roots and tool whitelist
            >>> integration.configure_servers(
            ...     {
            ...         "filesystem": {
            ...             "roots": ["/workspace/dir/data"],
            ...             "tool_whitelist": ["read_file"],
            ...         },
            ...         "github": {},  # No restrictions for github
            ...     },
            ...     registered,
            ... )

            >>> # Old format: Direct list (backward compatible)
            >>> integration.configure_servers(
            ...     {
            ...         "filesystem": ["/workspace/dir/data"],  # Old format still works
            ...     },
            ...     registered,
            ... )

            >>> # Mixed: backward compatible
            >>> integration.configure_servers(
            ...     [
            ...         "github",  # No mounts
            ...         {"filesystem": {"roots": ["mount1", "mount2"]}},
            ...     ],
            ...     registered,
            ... )
        """
        # Parse input into server_names and mounts
        server_set: set[str] = set()
        server_mounts: dict[str, list[str]] = {}
        whitelist = None

        if isinstance(servers, dict):
            # Dict format: supports both old and new formats
            # Old: {"server": ["/path1", "/path2"]}
            # New: {"server": {"roots": ["/path1"], "tool_whitelist": ["tool1"]}}
            for server_name, server_config in servers.items():
                server_set.add(server_name)

                # Check if it's the old format (direct list) or new format (MCPServerConfig dict)
                if isinstance(server_config, list):
                    # Old format: direct list of paths (backward compatibility)
                    if len(server_config) > 0:
                        server_mounts[server_name] = list(server_config)
                elif isinstance(server_config, dict):
                    # New format: MCPServerConfig with optional roots and tool_whitelist
                    mounts = server_config.get("roots", None)
                    if (
                        mounts is not None
                        and isinstance(mounts, list)
                        and len(mounts) > 0
                    ):
                        server_mounts[server_name] = list(mounts)

                    config_whitelist = server_config.get("tool_whitelist", None)
                    if (
                        config_whitelist is not None
                        and isinstance(config_whitelist, list)
                        and len(config_whitelist) > 0
                    ):
                        whitelist = config_whitelist
        elif isinstance(servers, list):
            # List format: can be mixed
            for item in servers:
                if isinstance(item, str):
                    # Simple server name
                    server_set.add(item)
                elif isinstance(item, dict):
                    # Dict with mounts
                    for server_name, mounts in item.items():
                        server_set.add(server_name)
                        if mounts:
                            server_mounts[server_name] = list(mounts)
                else:
                    raise TypeError(
                        f"Invalid server specification: {item}. "
                        f"Expected string or dict, got {type(item).__name__}"
                    )
        else:
            # Assume it's an iterable of strings (backward compatibility)
            server_set = set(servers)

        # Validate all servers exist in orchestrator
        invalid_servers = server_set - registered_servers

        if invalid_servers:
            available = list(registered_servers) if registered_servers else ["none"]
            raise ValueError(
                f"MCP servers not registered: {invalid_servers}. "
                f"Available servers: {available}. "
                f"Register servers using orchestrator.add_mcp() first."
            )

        # Store in integration
        self.mcp_server_names = server_set
        self.mcp_server_mounts = server_mounts
        self.tool_whitelist = whitelist

    def mount(self, paths: str | list[str], *, validate: bool = False) -> None:
        """Mount agent in specific directories for MCP root access.

        .. deprecated:: 0.2.0
            Use configure_servers({"server_name": ["/path"]}) instead for server-specific mounts.
            This method applies mounts globally to all MCP servers.

        This sets the filesystem roots that MCP servers will operate under for this agent.
        Paths are cumulative across multiple calls.

        Args:
            paths: Single path or list of paths to mount
            validate: If True, validate that paths exist (default: False)

        Raises:
            ValueError: If validate=True and path doesn't exist

        Example:
            >>> # Old way (deprecated)
            >>> integration.mount("/workspace/src")
            >>>
            >>> # New way (recommended)
            >>> integration.configure_servers(
            ...     {"filesystem": ["/workspace/src"]}, registered
            ... )
        """
        import warnings

        warnings.warn(
            "Agent.mount() is deprecated. Use .with_mcps({'server': ['/path']}) "
            "for server-specific mounts instead.",
            DeprecationWarning,
            stacklevel=3,  # Skip this method and the AgentBuilder wrapper
        )

        if isinstance(paths, str):
            paths = [paths]
        if validate:
            from pathlib import Path

            for path in paths:
                if not Path(path).exists():
                    raise ValueError(f"Mount path does not exist: {path}")

        # Add to deprecated mount points (cumulative) - for backward compatibility
        self.mcp_mount_points.extend(paths)

        # Also add to all configured servers for backward compatibility
        for server_name in self.mcp_server_names:
            if server_name not in self.mcp_server_mounts:
                self.mcp_server_mounts[server_name] = []
            self.mcp_server_mounts[server_name].extend(paths)


__all__ = ["MCPIntegration"]

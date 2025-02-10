"""Registry for storing and managing agents and tools."""

from collections.abc import Callable

from flock.core.flock_agent import FlockAgent


class Registry:
    """Registry for storing and managing agents and tools.

    This singleton class maintains a centralized registry of agents and tools,
    which is particularly important for Temporal workflows where only basic Python
    types can be passed between activities.
    """

    _instance = None

    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize the registry's storage."""
        self._agents: list[FlockAgent] = []
        self._tools: list[tuple[str, Callable]] = []

    def register_tool(self, tool_name: str, tool: Callable) -> None:
        """Register a tool with the registry.

        Args:
            tool_name: The name to register the tool under
            tool: The tool function to register
        """
        try:
            self._tools.append((tool_name, tool))
        except Exception:
            raise

    def register_agent(self, agent: FlockAgent) -> None:
        """Register an agent with the registry.

        Args:
            agent: The agent instance to register
        """
        try:
            self._agents.append(agent)
        except Exception:
            raise

    def get_agent(self, name: str) -> FlockAgent | None:
        """Retrieve an agent by name.

        Args:
            name: The name of the agent to retrieve

        Returns:
            The agent instance if found, None otherwise
        """
        try:
            for agent in self._agents:
                if agent.name == name:
                    return agent
            return None
        except Exception:
            raise

    def get_tool(self, name: str) -> Callable | None:
        """Retrieve a tool by name.

        Args:
            name: The name of the tool to retrieve

        Returns:
            The tool function if found, None otherwise
        """
        try:
            for tool_name, tool in self._tools:
                if tool_name == name:
                    return tool
            return None
        except Exception:
            raise

    def get_tools(self, names: list[str] | None) -> list[Callable]:
        """Retrieve multiple tools by name.

        Args:
            names: List of tool names to retrieve

        Returns:
            List of found tool functions (may be empty if none found)
        """
        try:
            if not names:
                return []

            tools = [self.get_tool(name) for name in names]
            return [tool for tool in tools if tool is not None]
        except Exception:
            raise

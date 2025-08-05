# src/flock/core/registry/agent_registry.py
"""Agent instance registration and lookup functionality."""

import threading
from typing import TYPE_CHECKING

from flock.core.logging.logging import get_logger

if TYPE_CHECKING:
    from flock.core.flock_agent import FlockAgent

logger = get_logger("registry.agents")


class AgentRegistry:
    """Manages FlockAgent instance registration and lookup with thread safety."""

    def __init__(self, lock: threading.RLock):
        self._lock = lock
        self._agents: dict[str, "FlockAgent"] = {}

    def register_agent(self, agent: "FlockAgent", *, force: bool = False) -> None:
        """Register a FlockAgent instance by its name.

        Args:
            agent: The agent instance to register.
            force: If True, allow overwriting an existing **different** agent registered under the same name.
                   If False and a conflicting registration exists, a ValueError is raised.
        """
        if not hasattr(agent, "name") or not agent.name:
            logger.error("Attempted to register an agent without a valid 'name' attribute.")
            return

        with self._lock:
            if agent.name in self._agents and self._agents[agent.name] is not agent:
                # Same agent already registered → silently ignore; different instance → error/force.
                if not force:
                    raise ValueError(
                        f"Agent '{agent.name}' already registered with a different instance. "
                        "Pass force=True to overwrite the existing registration."
                    )
                logger.warning(f"Overwriting existing agent '{agent.name}' registration due to force=True.")

            self._agents[agent.name] = agent
            logger.debug(f"Registered agent: {agent.name}")

    def get_agent(self, name: str) -> "FlockAgent | None":
        """Retrieve a registered FlockAgent instance by name."""
        with self._lock:
            agent = self._agents.get(name)
            if not agent:
                logger.warning(f"Agent '{name}' not found in registry.")
            return agent

    def get_all_agent_names(self) -> list[str]:
        """Return a list of names of all registered agents."""
        with self._lock:
            return list(self._agents.keys())

    def get_all_agents(self) -> dict[str, "FlockAgent"]:
        """Get all registered agents."""
        with self._lock:
            return self._agents.copy()

    def clear(self) -> None:
        """Clear all registered agents."""
        with self._lock:
            self._agents.clear()
            logger.debug("Cleared all registered agents")

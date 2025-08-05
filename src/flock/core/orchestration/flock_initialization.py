# src/flock/core/orchestration/flock_initialization.py
"""Initialization functionality for Flock orchestrator."""

import os
import uuid
from typing import TYPE_CHECKING

from opentelemetry.baggage import get_baggage, set_baggage

from flock.core.logging.logging import get_logger
from flock.core.registry import get_registry
from flock.core.util.cli_helper import init_console

if TYPE_CHECKING:
    from flock.core.flock import Flock
    from flock.core.flock_agent import FlockAgent
    from flock.core.mcp.flock_mcp_server import FlockMCPServer

logger = get_logger("flock.initialization")


class FlockInitialization:
    """Handles initialization logic for Flock orchestrator."""

    def __init__(self, flock: "Flock"):
        self.flock = flock

    def setup(
        self,
        agents: list["FlockAgent"] | None = None,
        servers: list["FlockMCPServer"] | None = None,
    ) -> None:
        """Handle all initialization side effects and setup."""
        # Register passed servers first (agents may depend on them)
        if servers:
            self._register_servers(servers)

        # Register passed agents
        if agents:
            self._register_agents(agents)

        # Initialize console if needed for banner
        if self.flock.show_flock_banner:
            init_console(clear_screen=True, show_banner=self.flock.show_flock_banner)

        # Set Temporal debug environment variable
        self._set_temporal_debug_flag()

        # Ensure session ID exists in baggage
        self._ensure_session_id()

        # Auto-discover components
        registry = get_registry()
        registry.discover_and_register_components()

        # Setup Opik if enabled
        if self.flock.enable_opik:
            self._setup_opik()

        logger.info(
            "Flock instance initialized",
            name=self.flock.name,
            model=self.flock.model,
            enable_temporal=self.flock.enable_temporal,
        )

    def _register_servers(self, servers: list["FlockMCPServer"]) -> None:
        """Register servers with the Flock instance."""
        from flock.core.mcp.flock_mcp_server import (
            FlockMCPServer as ConcreteFlockMCPServer,
        )

        for server in servers:
            if isinstance(server, ConcreteFlockMCPServer):
                self.flock.add_server(server)
            else:
                logger.warning(
                    f"Item provided in 'servers' list is not a FlockMCPServer: {type(server)}"
                )

    def _register_agents(self, agents: list["FlockAgent"]) -> None:
        """Register agents with the Flock instance."""
        from flock.core.flock_agent import FlockAgent as ConcreteFlockAgent

        for agent in agents:
            if isinstance(agent, ConcreteFlockAgent):
                self.flock.add_agent(agent)
            else:
                logger.warning(
                    f"Item provided in 'agents' list is not a FlockAgent: {type(agent)}"
                )

    def _set_temporal_debug_flag(self) -> None:
        """Set or remove LOCAL_DEBUG env var based on enable_temporal."""
        if not self.flock.enable_temporal:
            if "LOCAL_DEBUG" not in os.environ:
                os.environ["LOCAL_DEBUG"] = "1"
                logger.debug("Set LOCAL_DEBUG environment variable for local execution.")
        elif "LOCAL_DEBUG" in os.environ:
            del os.environ["LOCAL_DEBUG"]
            logger.debug("Removed LOCAL_DEBUG environment variable for Temporal execution.")

    def _ensure_session_id(self) -> None:
        """Ensure a session_id exists in the OpenTelemetry baggage."""
        session_id = get_baggage("session_id")
        if not session_id:
            session_id = str(uuid.uuid4())
            set_baggage("session_id", session_id)
            logger.debug(f"Generated new session_id: {session_id}")

    def _setup_opik(self) -> None:
        """Setup Opik integration."""
        try:
            import dspy
            import opik
            from opik.integrations.dspy.callback import OpikCallback

            opik.configure(use_local=True, automatic_approvals=True)
            opik_callback = OpikCallback(project_name=self.flock.name, log_graph=True)
            dspy.settings.configure(callbacks=[opik_callback])
            logger.info("Opik integration enabled")
        except ImportError as e:
            logger.error(f"Failed to setup Opik integration: {e}")
            logger.warning("Disabling Opik integration")
            self.flock.enable_opik = False

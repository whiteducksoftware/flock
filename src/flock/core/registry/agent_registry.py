"""Registry for storing and managing agents and tools with logging and tracing integration."""

from collections.abc import Callable

from opentelemetry import trace

from flock.core.flock_agent import FlockAgent
from flock.core.logging.logging import get_logger

logger = get_logger("registry")
tracer = trace.get_tracer(__name__)


class Registry:
    """Registry for storing and managing agents and tools.

    This singleton class maintains a centralized registry of agents and tools,
    which is particularly important for Temporal workflows where only basic Python
    types can be passed between activities.
    """

    _instance = None

    def __new__(cls):
        with tracer.start_as_current_span("Registry.__new__") as span:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialize()
                logger.info("Registry instance created")
                span.set_attribute("instance.created", True)
            return cls._instance

    def _initialize(self):
        with tracer.start_as_current_span("Registry._initialize"):
            self._agents: list[FlockAgent] = []
            self._tools: list[tuple[str, Callable]] = []
            logger.info("Registry initialized", agents_count=0, tools_count=0)

    def register_tool(self, tool_name: str, tool: Callable) -> None:
        with tracer.start_as_current_span("Registry.register_tool") as span:
            span.set_attribute("tool_name", tool_name)
            try:
                self._tools.append((tool_name, tool))
                logger.info("Tool registered", tool_name=tool_name)
            except Exception as e:
                logger.error(
                    "Error registering tool", tool_name=tool_name, error=str(e)
                )
                span.record_exception(e)
                raise

    def register_agent(self, agent: FlockAgent) -> None:
        with tracer.start_as_current_span("Registry.register_agent") as span:
            span.set_attribute("agent_name", agent.name)
            try:
                self._agents.append(agent)
                logger.info("Agent registered", agent=agent.name)
            except Exception as e:
                logger.error(
                    "Error registering agent", agent=agent.name, error=str(e)
                )
                span.record_exception(e)
                raise

    def get_agent(self, name: str) -> FlockAgent | None:
        with tracer.start_as_current_span("Registry.get_agent") as span:
            span.set_attribute("search_agent_name", name)
            try:
                for agent in self._agents:
                    if agent.name == name:
                        logger.info("Agent found", agent=name)
                        span.set_attribute("found", True)
                        return agent
                logger.warning("Agent not found", agent=name)
                span.set_attribute("found", False)
                return None
            except Exception as e:
                logger.error("Error retrieving agent", agent=name, error=str(e))
                span.record_exception(e)
                raise

    def get_tool(self, name: str) -> Callable | None:
        with tracer.start_as_current_span("Registry.get_tool") as span:
            span.set_attribute("search_tool_name", name)
            try:
                for tool_name, tool in self._tools:
                    if tool_name == name:
                        logger.info("Tool found", tool=name)
                        span.set_attribute("found", True)
                        return tool
                logger.warning("Tool not found", tool=name)
                span.set_attribute("found", False)
                return None
            except Exception as e:
                logger.error("Error retrieving tool", tool=name, error=str(e))
                span.record_exception(e)
                raise

    def get_tools(self, names: list[str] | None) -> list[Callable]:
        with tracer.start_as_current_span("Registry.get_tools") as span:
            span.set_attribute("search_tool_names", str(names))
            try:
                if not names:
                    logger.info("No tool names provided")
                    return []
                tools = [self.get_tool(name) for name in names]
                found_tools = [tool for tool in tools if tool is not None]
                logger.info(
                    "Tools retrieved", requested=names, found=len(found_tools)
                )
                span.set_attribute("found_tools_count", len(found_tools))
                return found_tools
            except Exception as e:
                logger.error(
                    "Error retrieving tools", names=str(names), error=str(e)
                )
                span.record_exception(e)
                raise

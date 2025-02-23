"""Base classes and implementations for the Flock module system."""

from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel, Field, create_model

T = TypeVar("T", bound="FlockModuleConfig")


class FlockModuleConfig(BaseModel):
    """Base configuration class for Flock modules.

    This class serves as the base for all module-specific configurations.
    Each module should define its own config class inheriting from this one.

    Example:
        class MemoryModuleConfig(FlockModuleConfig):
            file_path: str = Field(default="memory.json")
            save_after_update: bool = Field(default=True)
    """

    enabled: bool = Field(
        default=True, description="Whether the module is currently enabled"
    )

    @classmethod
    def with_fields(cls: type[T], **field_definitions) -> type[T]:
        """Create a new config class with additional fields.

        This helper method allows modules to easily define their config
        requirements without subclassing.

        Args:
            **field_definitions: Field definitions to add to the config class

        Returns:
            A new config class with the specified fields

        Example:
            MyConfig = FlockModuleConfig.with_fields(
                api_key=Field(str, description="API key for the service"),
                max_retries=Field(int, default=3)
            )
        """
        return create_model(
            f"Dynamic{cls.__name__}", __base__=cls, **field_definitions
        )


class FlockModule(BaseModel, ABC):
    """Base class for all Flock modules.

    Modules can hook into agent lifecycle events and modify or enhance agent behavior.
    They are initialized when added to an agent and can maintain their own state.

    Each module should define its configuration requirements either by:
    1. Creating a subclass of FlockModuleConfig
    2. Using FlockModuleConfig.with_fields() to create a config class
    """

    name: str = Field(..., description="Unique identifier for the module")
    config: FlockModuleConfig = Field(
        default_factory=FlockModuleConfig, description="Module configuration"
    )

    @abstractmethod
    async def pre_initialize(self, agent: Any, inputs: dict[str, Any]) -> None:
        """Called before agent initialization."""
        pass

    @abstractmethod
    async def post_initialize(self, agent: Any, inputs: dict[str, Any]) -> None:
        """Called after agent initialization."""
        pass

    @abstractmethod
    async def pre_evaluate(
        self, agent: Any, inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """Called before agent evaluation, can modify inputs."""
        return inputs

    @abstractmethod
    async def post_evaluate(
        self, agent: Any, inputs: dict[str, Any], result: dict[str, Any]
    ) -> dict[str, Any]:
        """Called after agent evaluation, can modify results."""
        return result

    @abstractmethod
    async def pre_terminate(
        self, agent: Any, inputs: dict[str, Any], result: dict[str, Any]
    ) -> None:
        """Called before agent termination."""
        pass

    @abstractmethod
    async def post_terminate(
        self, agent: Any, inputs: dict[str, Any], result: dict[str, Any]
    ) -> None:
        """Called after agent termination."""
        pass

    async def on_error(
        self, agent: Any, error: Exception, inputs: dict[str, Any]
    ) -> None:
        """Called when an error occurs during agent execution."""
        pass


class ModuleManager:
    """Manages modules for a FlockAgent.

    Handles module registration, lifecycle events, and maintaining module state.
    """

    def __init__(self):
        self.modules: dict[str, FlockModule] = {}

    def add_module(self, module: FlockModule) -> None:
        """Add a module to the manager."""
        self.modules[module.name] = module

    def remove_module(self, module_name: str) -> None:
        """Remove a module from the manager."""
        if module_name in self.modules:
            del self.modules[module_name]

    def get_module(self, module_name: str) -> FlockModule | None:
        """Get a module by name."""
        return self.modules.get(module_name)

    def get_enabled_modules(self) -> list[FlockModule]:
        """Get all enabled modules."""
        return [m for m in self.modules.values() if m.enabled]

    async def run_pre_initialize(
        self, agent: Any, inputs: dict[str, Any]
    ) -> None:
        """Run pre_initialize for all enabled modules."""
        for module in self.get_enabled_modules():
            await module.pre_initialize(agent, inputs)

    async def run_post_initialize(
        self, agent: Any, inputs: dict[str, Any]
    ) -> None:
        """Run post_initialize for all enabled modules."""
        for module in self.get_enabled_modules():
            await module.post_initialize(agent, inputs)

    async def run_pre_evaluate(
        self, agent: Any, inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """Run pre_evaluate for all enabled modules."""
        current_inputs = inputs
        for module in self.get_enabled_modules():
            current_inputs = await module.pre_evaluate(agent, current_inputs)
        return current_inputs

    async def run_post_evaluate(
        self, agent: Any, inputs: dict[str, Any], result: dict[str, Any]
    ) -> dict[str, Any]:
        """Run post_evaluate for all enabled modules."""
        current_result = result
        for module in self.get_enabled_modules():
            current_result = await module.post_evaluate(
                agent, inputs, current_result
            )
        return current_result

    async def run_pre_terminate(
        self, agent: Any, inputs: dict[str, Any], result: dict[str, Any]
    ) -> None:
        """Run pre_terminate for all enabled modules."""
        for module in self.get_enabled_modules():
            await module.pre_terminate(agent, inputs, result)

    async def run_post_terminate(
        self, agent: Any, inputs: dict[str, Any], result: dict[str, Any]
    ) -> None:
        """Run post_terminate for all enabled modules."""
        for module in self.get_enabled_modules():
            await module.post_terminate(agent, inputs, result)

    async def run_on_error(
        self, agent: Any, error: Exception, inputs: dict[str, Any]
    ) -> None:
        """Run on_error for all enabled modules."""
        for module in self.get_enabled_modules():
            await module.on_error(agent, error, inputs)

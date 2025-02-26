"""FlockAgent is the core, declarative base class for all agents in the Flock framework."""

import asyncio
import json
import os
from abc import ABC
from collections.abc import Callable
from typing import Any, TypeVar

import cloudpickle
from opentelemetry import trace
from pydantic import BaseModel, Field

from flock.core.flock_evaluator import FlockEvaluator
from flock.core.flock_module import FlockModule
from flock.core.flock_router import FlockRouter
from flock.core.logging.logging import get_logger

logger = get_logger("agent")
tracer = trace.get_tracer(__name__)


T = TypeVar("T", bound="FlockAgent")


class FlockAgent(BaseModel, ABC):
    name: str = Field(..., description="Unique identifier for the agent.")
    model: str | None = Field(
        None, description="The model to use (e.g., 'openai/gpt-4o')."
    )
    description: str | Callable[..., str] | None = Field(
        "", description="A human-readable description of the agent."
    )

    input: str | Callable[..., str] | None = Field(
        None,
        description=(
            "A comma-separated list of input keys. Optionally supports type hints (:) and descriptions (|). "
            "For example: 'query: str | The search query, chapter_list: list[str] | The chapter list of the document'."
        ),
    )
    output: str | Callable[..., str] | None = Field(
        None,
        description=(
            "A comma-separated list of output keys.  Optionally supports type hints (:) and descriptions (|). "
            "For example: 'result|The generated result, summary|A brief summary'."
        ),
    )

    tools: list[Callable[..., Any] | Any] | None = Field(
        default=None,
        description="An optional list of callable tools that the agent can leverage during execution.",
    )

    use_cache: bool = Field(
        default=True,
        description="Set to True to enable caching of the agent's results.",
    )

    handoff_router: FlockRouter | None = Field(
        default=None,
        description="Router to use for determining the next agent in the workflow.",
    )

    evaluator: FlockEvaluator = Field(
        None,
        description="Evaluator to use for agent evaluation",
    )

    modules: dict[str, FlockModule] = Field(
        default_factory=dict,
        description="FlockModules attached to this agent",
    )

    def add_module(self, module: FlockModule) -> None:
        """Add a module to this agent."""
        self.modules[module.name] = module

    def remove_module(self, module_name: str) -> None:
        """Remove a module from this agent."""
        if module_name in self.modules:
            del self.modules[module_name]

    def get_module(self, module_name: str) -> FlockModule | None:
        """Get a module by name."""
        return self.modules.get(module_name)

    def get_enabled_modules(self) -> list[FlockModule | None]:
        """Get a module by name."""
        return [m for m in self.modules.values() if m.config.enabled]

    # Lifecycle hooks
    async def initialize(self, inputs: dict[str, Any]) -> None:
        with tracer.start_as_current_span("agent.initialize") as span:
            span.set_attribute("agent.name", self.name)
            span.set_attribute("inputs", str(inputs))

            try:
                for module in self.get_enabled_modules():
                    logger.info(
                        f"agent.initialize - module {module.name}",
                        agent=self.name,
                    )
                    await module.initialize(self, inputs)
            except Exception as module_error:
                logger.error(
                    "Error during initialize",
                    agent=self.name,
                    error=str(module_error),
                )
                span.record_exception(module_error)

    async def terminate(
        self, inputs: dict[str, Any], result: dict[str, Any]
    ) -> None:
        with tracer.start_as_current_span("agent.terminate") as span:
            span.set_attribute("agent.name", self.name)
            span.set_attribute("inputs", str(inputs))
            span.set_attribute("result", str(result))
            logger.info(
                f"agent.terminate",
                agent=self.name,
            )
            try:
                for module in self.get_enabled_modules():
                    await module.terminate(self, inputs, inputs)
            except Exception as module_error:
                logger.error(
                    "Error during terminate",
                    agent=self.name,
                    error=str(module_error),
                )
                span.record_exception(module_error)

    async def on_error(self, error: Exception, inputs: dict[str, Any]) -> None:
        with tracer.start_as_current_span("agent.on_error") as span:
            span.set_attribute("agent.name", self.name)
            span.set_attribute("inputs", str(inputs))
            try:
                for module in self.get_enabled_modules():
                    await module.on_error(self, error, inputs)
            except Exception as module_error:
                logger.error(
                    "Error during on_error",
                    agent=self.name,
                    error=str(module_error),
                )
                span.record_exception(module_error)

    async def evaluate(self, inputs: dict[str, Any]) -> dict[str, Any]:
        with tracer.start_as_current_span("agent.evaluate") as span:
            span.set_attribute("agent.name", self.name)
            span.set_attribute("inputs", str(inputs))

            for module in self.get_enabled_modules():
                inputs = await module.pre_evaluate(self, inputs)

            try:
                result = await self.evaluator.evaluate(self, inputs, self.tools)

                for module in self.get_enabled_modules():
                    result = await module.post_evaluate(self, inputs, result)

                span.set_attribute("result", str(result))

                logger.info("Evaluation successful", agent=self.name)
                return result
            except Exception as eval_error:
                logger.error(
                    "Error during evaluation",
                    agent=self.name,
                    error=str(eval_error),
                )
                span.record_exception(eval_error)
                raise

    def save_to_file(self, file_path: str | None = None) -> None:
        """Save the serialized agent to a file."""
        if file_path is None:
            file_path = f"{self.name}.json"
        dict_data = self.to_dict()

        # create all needed directories
        path = os.path.dirname(file_path)
        if path:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, "w") as file:
            file.write(json.dumps(dict_data))

    @classmethod
    def load_from_file(cls: type[T], file_path: str) -> T:
        """Load a serialized agent from a file."""
        with open(file_path) as file:
            data = json.load(file)
        # Fallback: use the current class.
        return cls.from_dict(data)

    def run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Run the agent with the given inputs and return its generated output."""
        return asyncio.run(self.run_async(inputs))

    async def run_async(self, inputs: dict[str, Any]) -> dict[str, Any]:
        with tracer.start_as_current_span("agent.run") as span:
            span.set_attribute("agent.name", self.name)
            span.set_attribute("inputs", str(inputs))
            try:
                await self.initialize(inputs)

                result = await self.evaluate(inputs)

                await self.terminate(inputs, result)
                span.set_attribute("result", str(result))
                logger.info("Agent run completed", agent=self.name)
                return result
            except Exception as run_error:
                logger.error(
                    "Error running agent", agent=self.name, error=str(run_error)
                )
                await self.on_error(run_error, inputs)
                span.record_exception(run_error)
                raise

    async def run_temporal(self, inputs: dict[str, Any]) -> dict[str, Any]:
        with tracer.start_as_current_span("agent.run_temporal") as span:
            span.set_attribute("agent.name", self.name)
            span.set_attribute("inputs", str(inputs))
            try:
                from temporalio.client import Client

                from flock.workflow.agent_activities import (
                    run_flock_agent_activity,
                )
                from flock.workflow.temporal_setup import run_activity

                client = await Client.connect(
                    "localhost:7233", namespace="default"
                )
                agent_data = self.to_dict()
                inputs_data = inputs

                result = await run_activity(
                    client,
                    self.name,
                    run_flock_agent_activity,
                    {"agent_data": agent_data, "inputs": inputs_data},
                )
                span.set_attribute("result", str(result))
                logger.info("Temporal run successful", agent=self.name)
                return result
            except Exception as temporal_error:
                logger.error(
                    "Error in Temporal workflow",
                    agent=self.name,
                    error=str(temporal_error),
                )
                span.record_exception(temporal_error)
                raise

    def resolve_callables(self, context) -> None:
        if isinstance(self.input, Callable):
            self.input = self.input(context)
        if isinstance(self.output, Callable):
            self.output = self.output(context)
        if isinstance(self.description, Callable):
            self.description = self.description(context)

    def to_dict(self) -> dict[str, Any]:
        def convert_callable(obj: Any) -> Any:
            if callable(obj) and not isinstance(obj, type):
                return cloudpickle.dumps(obj).hex()
            if isinstance(obj, list):
                return [convert_callable(item) for item in obj]
            if isinstance(obj, dict):
                return {k: convert_callable(v) for k, v in obj.items()}
            return obj

        data = self.model_dump()
        module_data = {}
        for name, module in self.modules.items():
            module_data[name] = module.dict()

        data["modules"] = module_data

        return convert_callable(data)

    @classmethod
    def from_dict(cls: type[T], data: dict[str, Any]) -> T:
        def convert_callable(obj: Any) -> Any:
            if isinstance(obj, str) and len(obj) > 2:
                try:
                    return cloudpickle.loads(bytes.fromhex(obj))
                except Exception:
                    return obj
            if isinstance(obj, list):
                return [convert_callable(item) for item in obj]
            if isinstance(obj, dict):
                return {k: convert_callable(v) for k, v in obj.items()}
            return obj

        module_data = data.pop("modules", {})
        converted = convert_callable(data)
        agent = cls(**converted)

        for name, module_dict in module_data.items():
            module_type = module_dict.pop("type", None)
            if module_type:
                module_class = globals()[module_type]
                module = module_class(**module_dict)
                agent.add_module(module)

        return agent

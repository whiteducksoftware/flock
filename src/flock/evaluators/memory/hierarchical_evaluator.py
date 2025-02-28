from typing import Any, Literal

from pydantic import Field

from flock.core.flock_agent import FlockAgent
from flock.core.flock_evaluator import FlockEvaluator, FlockEvaluatorConfig
from flock.core.mixin.dspy_integration import DSPyIntegrationMixin
from flock.core.mixin.prompt_parser import PromptParserMixin
from flock.modules.hierarchical.memory import HierarchicalMemoryModuleConfig
from flock.modules.hierarchical.module import HierarchicalMemoryModule


class HierarchicalMemoryEvaluatorConfig(FlockEvaluatorConfig):
    folder_path: str = Field(
        default="concept_memory/",
        description="Directory where memory file and concept graph will be saved",
    )
    concept_graph_file: str = Field(
        default="concept_graph.png",
        description="Base filename for the concept graph image",
    )
    file_path: str | None = Field(
        default="agent_memory.json", description="Path to save memory file"
    )
    memory_mapping: str | None = Field(
        default=None, description="Memory mapping configuration"
    )
    similarity_threshold: float = Field(
        default=0.5, description="Threshold for semantic similarity"
    )
    max_length: int = Field(
        default=1000, description="Max length of memory entry before splitting"
    )
    save_after_update: bool = Field(
        default=True, description="Whether to save memory after each update"
    )
    splitting_mode: Literal["summary", "semantic", "characters"] = Field(
        default="splitter"
    )
    enable_read_only_mode: bool = Field(
        default=False, description="Whether to enable read only mode"
    )
    enable_hierarchical_concepts: bool = Field(
        default=True,
        description="Whether to enable hierarchical concept representation",
    )
    hierarchical_activation_boost: float = Field(
        default=1.5,
        description="Boost factor for activation when following hierarchical relationships",
    )
    upward_propagation_factor: float = Field(
        default=0.8,
        description="How much activation propagates upward in the hierarchy",
    )
    downward_propagation_factor: float = Field(
        default=0.6,
        description="How much activation propagates downward in the hierarchy",
    )


class HierarchicalMemoryEvaluator(
    FlockEvaluator, DSPyIntegrationMixin, PromptParserMixin
):
    """Evaluator that uses DSPy for generation."""

    config: HierarchicalMemoryEvaluatorConfig = Field(
        default_factory=HierarchicalMemoryEvaluatorConfig,
        description="Evaluator configuration",
    )

    async def evaluate(
        self, agent: FlockAgent, inputs: dict[str, Any], tools: list[Any]
    ) -> dict[str, Any]:
        """Simple evaluator that uses a memory concept graph.

        if inputs contain "query", it searches memory for the query and returns the facts.
        if inputs contain "data", it adds the data to memory
        """
        result = {}
        memory_module = HierarchicalMemoryModule(
            name=self.name,
            config=HierarchicalMemoryModuleConfig(
                folder_path=self.config.folder_path,
                enable_hierarchical_concepts=self.config.enable_hierarchical_concepts,
                upward_propagation_factor=self.config.upward_propagation_factor,
                downward_propagation_factor=self.config.downward_propagation_factor,
                similarity_threshold=self.config.similarity_threshold,
                splitting_mode=self.config.splitting_mode,
                enable_read_only_mode=self.config.enable_read_only_mode,
                max_length=self.config.max_length,
                save_after_update=self.config.save_after_update,
                hierarchical_activation_boost=self.config.hierarchical_activation_boost,
                file_path=self.config.file_path,
                memory_mapping=self.config.memory_mapping,
            ),
        )

        await memory_module.initialize(agent, inputs)

        if "query" in inputs:
            facts = await memory_module.search_memory(agent, inputs)
            result = {"facts": facts}

        if "data" in inputs:
            await memory_module.add_to_memory(agent, inputs)
            result = {"message": "Data added to memory"}
        return result

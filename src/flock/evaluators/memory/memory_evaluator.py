from typing import Any, Literal

from pydantic import Field

from flock.core.flock_agent import FlockAgent
from flock.core.flock_evaluator import FlockEvaluator, FlockEvaluatorConfig
from flock.core.mixin.dspy_integration import DSPyIntegrationMixin
from flock.core.mixin.prompt_parser import PromptParserMixin
from flock.modules.memory.memory_module import MemoryModule, MemoryModuleConfig


class MemoryEvaluatorConfig(FlockEvaluatorConfig):
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
    splitting_mode: Literal["summary", "semantic", "characters", "none"] = (
        Field(default="none", description="Mode to split memory content")
    )
    enable_read_only_mode: bool = Field(
        default=False, description="Whether to enable read only mode"
    )
    number_of_concepts_to_extract: int = Field(
        default=3, description="Number of concepts to extract from the memory"
    )


class MemoryEvaluator(FlockEvaluator, DSPyIntegrationMixin, PromptParserMixin):
    """Evaluator that uses DSPy for generation."""

    config: MemoryEvaluatorConfig = Field(
        default_factory=MemoryEvaluatorConfig,
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
        memory_module = MemoryModule(
            name=self.name,
            config=MemoryModuleConfig(
                folder_path=self.config.folder_path,
                concept_graph_file=self.config.concept_graph_file,
                file_path=self.config.file_path,
                memory_mapping=self.config.memory_mapping,
                similarity_threshold=self.config.similarity_threshold,
                max_length=self.config.max_length,
                save_after_update=self.config.save_after_update,
                splitting_mode=self.config.splitting_mode,
                enable_read_only_mode=self.config.enable_read_only_mode,
                number_of_concepts_to_extract=self.config.number_of_concepts_to_extract,
            ),
        )

        if "query" in inputs:
            facts = await memory_module.search_memory(agent, inputs)
            result = {"facts": facts}

        if "data" in inputs:
            await memory_module.add_to_memory(agent, inputs)
            result = {"message": "Data added to memory"}
        return result

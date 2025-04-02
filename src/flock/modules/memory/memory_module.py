import json
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field
from tqdm import tqdm

from flock.core.context.context import FlockContext

# if TYPE_CHECKING:
#     from flock.core import FlockAgent
from flock.core.flock_agent import FlockAgent
from flock.core.flock_module import FlockModule, FlockModuleConfig
from flock.core.logging.logging import get_logger
from flock.modules.memory.memory_parser import MemoryMappingParser
from flock.modules.memory.memory_storage import FlockMemoryStore, MemoryEntry

logger = get_logger("memory")


class MemoryModuleConfig(FlockModuleConfig):
    """Configuration for the MemoryModule.

    This class defines the configuration for the MemoryModule.
    """

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


class MemoryModule(FlockModule):
    """Module that adds memory capabilities to a Flock agent."""

    name: str = "memory"
    config: MemoryModuleConfig = Field(
        default_factory=MemoryModuleConfig,
        description="Memory module configuration",
    )
    memory_store: FlockMemoryStore | None = None
    memory_ops: list[Any] = []

    def __init__(self, name: str, config: MemoryModuleConfig):
        super().__init__(name=name, config=config)
        self.memory_store = FlockMemoryStore.load_from_file(
            self.get_memory_filename(name)
        )
        self.memory_ops = (
            MemoryMappingParser().parse(self.config.memory_mapping)
            if self.config.memory_mapping
            else [{"type": "semantic"}]
        )

    async def initialize(
        self,
        agent: FlockAgent,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
    ) -> None:
        """Initialize memory store if needed."""
        if not self.memory_store:
            self.memory_store = FlockMemoryStore.load_from_file(
                self.get_memory_filename(self.name)
            )
        self.memory_ops = (
            MemoryMappingParser().parse(self.config.memory_mapping)
            if self.config.memory_mapping
            else [{"type": "semantic"}]
        )
        logger.debug(f"Initialized memory module for agent {agent.name}")

    async def pre_evaluate(
        self,
        agent: FlockAgent,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
    ) -> dict[str, Any]:
        """Check memory before evaluation."""
        if not self.memory_store:
            return inputs

        inputs = await self.search_memory(agent, inputs)

        if "context" in inputs:
            agent.input = (
                agent.input + ", context: list | context with more information"
            )

        return inputs

    def get_memory_filename(self, module_name: str) -> str:
        """Generate the full file path for the memory file."""
        folder = self.config.folder_path
        if not folder.endswith(("/", "\\")):
            folder += "/"
        import os

        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        # Determine base filename and extension from file_path config
        if self.config.file_path:
            file_name = self.config.file_path.rsplit("/", 1)[-1].rsplit(
                "\\", 1
            )[-1]
            if "." in file_name:
                base, ext = file_name.rsplit(".", 1)
                ext = f".{ext}"
            else:
                base, ext = file_name, ""
        else:
            base, ext = "agent_memory", ".json"
        return f"{folder}{module_name}_{base}{ext}"

    def get_concept_graph_filename(self, module_name: str) -> str:
        """Generate the full file path for the concept graph image."""
        folder = self.config.folder_path
        if not folder.endswith(("/", "\\")):
            folder += "/"
        import os

        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        # Use timestamp to create a unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        if self.config.concept_graph_file:
            file_name = self.config.concept_graph_file.rsplit("/", 1)[
                -1
            ].rsplit("\\", 1)[-1]
            if "." in file_name:
                base, ext = file_name.rsplit(".", 1)
                ext = f".{ext}"
            else:
                base, ext = file_name, ""
        else:
            base, ext = "concept_graph", ".png"
        return f"{folder}{module_name}_{base}_{timestamp}{ext}"

    async def search_memory(
        self, agent: FlockAgent, query: dict[str, Any]
    ) -> list[str]:
        """Search memory for the query."""
        if not self.memory_store:
            return []

        try:
            input_text = json.dumps(query)
            query_embedding = self.memory_store.compute_embedding(input_text)
            concepts = await self._extract_concepts(
                agent, input_text, self.config.number_of_concepts_to_extract
            )

            memory_results = []
            for op in self.memory_ops:
                if op["type"] == "semantic":
                    semantic_results = self.memory_store.retrieve(
                        query_embedding,
                        concepts,
                        similarity_threshold=self.config.similarity_threshold,
                    )
                    memory_results.extend(semantic_results)
                elif op["type"] == "exact":
                    exact_results = self.memory_store.exact_match(query)
                    memory_results.extend(exact_results)

            context: list[dict[str, Any]] = []
            if memory_results:
                for result in memory_results:
                    context.append(
                        {"content": result.content, "concepts": result.concepts}
                    )

                logger.debug(
                    f"Found {len(memory_results)} relevant memories",
                    agent=agent.name,
                )
                query["context"] = context

            return query

        except Exception as e:
            logger.warning(f"Memory retrieval failed: {e}", agent=agent.name)
            return query

    async def add_to_memory(
        self, agent: FlockAgent, data: dict[str, Any]
    ) -> None:
        """Add data to memory."""
        if not self.memory_store:
            return

        try:
            chunks = await self._get_chunks(agent, data, None)
            await self._store_chunks(agent, chunks)
        except Exception as e:
            logger.warning(f"Memory storage failed: {e}", agent=agent.name)

    async def post_evaluate(
        self,
        agent: FlockAgent,
        inputs: dict[str, Any],
        result: dict[str, Any],
        context: FlockContext | None = None,
    ) -> dict[str, Any]:
        """Store results in memory after evaluation."""
        if not self.memory_store:
            return result

        try:
            chunks = await self._get_chunks(agent, inputs, result)
            await self._store_chunks(agent, chunks)
        except Exception as e:
            logger.warning(f"Memory storage failed: {e}", agent=agent.name)

        return result

    async def terminate(
        self,
        agent: Any,
        inputs: dict[str, Any],
        result: dict[str, Any],
        context: FlockContext | None = None,
    ) -> None:
        """Save memory store if configured."""
        if self.config.save_after_update and self.memory_store:
            self.save_memory()

    async def _extract_concepts(
        self, agent: FlockAgent, text: str, number_of_concepts: int = 3
    ) -> set[str]:
        """Extract concepts using the agent's LLM capabilities."""
        existing_concepts = set()
        if self.memory_store and self.memory_store.concept_graph:
            existing_concepts = set(
                self.memory_store.concept_graph.graph.nodes()
            )

        input_signature = "text: str | Text to analyze"
        if existing_concepts:
            input_signature += ", existing_concepts: list[str] | Already known concepts that might apply"

        concept_signature = agent.create_dspy_signature_class(
            f"{agent.name}_concept_extractor",
            "Extract key concepts from text",
            f"{input_signature} -> concepts: list[str] | Max {number_of_concepts} key concepts all lower case",
        )

        agent._configure_language_model(agent.model, True, 0.0, 8192)
        predictor = agent._select_task(concept_signature, "Completion")
        result_obj = predictor(
            text=text,
            existing_concepts=list(existing_concepts)
            if existing_concepts
            else None,
        )
        concept_list = getattr(result_obj, "concepts", [])
        return set(concept_list)

    async def _summarize_mode(
        self,
        agent: FlockAgent,
        inputs: dict[str, Any],
        result: dict[str, Any],
    ) -> str:
        """Extract information chunks using summary mode."""
        split_signature = agent.create_dspy_signature_class(
            f"{agent.name}_splitter",
            "Extract a list of potentially needed data and information for future reference",
            """
            content: str | The content to split
            -> chunks: list[str] | List of data and information for future reference
            """,
        )
        agent._configure_language_model(agent.model, True, 0.0, 8192)
        splitter = agent._select_task(split_signature, "Completion")
        full_text = json.dumps(inputs) + json.dumps(result)
        split_result = splitter(content=full_text)
        return "\n".join(split_result.chunks)

    async def _semantic_splitter_mode(
        self,
        agent: FlockAgent,
        inputs: dict[str, Any],
        result: dict[str, Any],
    ) -> str | list[dict[str, str]]:
        """Extract information chunks using semantic mode."""
        split_signature = agent.create_dspy_signature_class(
            f"{self.name}_splitter",
            "Split content into meaningful, self-contained chunks",
            """
            content: str | The content to split
            -> chunks: list[dict[str,str]] | List of chunks as key-value pairs - keys are a short title and values are the chunk content
            """,
        )
        agent._configure_language_model(agent.model, True, 0.0, 8192)
        splitter = agent._select_task(split_signature, "Completion")
        full_text = json.dumps(inputs) + (json.dumps(result) if result else "")
        split_result = splitter(content=full_text)
        return split_result.chunks

    async def _character_splitter_mode(
        self,
        agent: FlockAgent,
        inputs: dict[str, Any],
        result: dict[str, Any],
    ) -> list[str]:
        """Extract information chunks by splitting text into fixed character lengths."""
        full_text = json.dumps(inputs) + (json.dumps(result) if result else "")
        return [
            full_text[i : i + self.config.max_length]
            for i in range(0, len(full_text), self.config.max_length)
        ]

    async def _get_chunks(
        self,
        agent: FlockAgent,
        inputs: dict[str, Any],
        result: dict[str, Any] | None,
    ) -> str | list[str]:
        """Get memory chunks based on the configured splitting mode."""
        mode = self.config.splitting_mode
        if mode == "semantic":
            return await self._semantic_splitter_mode(agent, inputs, result)
        elif mode == "summary":
            return await self._summarize_mode(agent, inputs, result)
        elif mode == "characters":
            return await self._character_splitter_mode(agent, inputs, result)
        elif mode == "none":
            return (
                json.dumps(inputs) + json.dumps(result)
                if result
                else json.dumps(inputs)
            )
        else:
            raise ValueError(f"Unknown splitting mode: {mode}")

    async def _store_chunk(self, agent: FlockAgent, chunk: str) -> None:
        """Store a single chunk in memory."""
        chunk_concepts = await self._extract_concepts(
            agent, chunk, self.config.number_of_concepts_to_extract
        )
        entry = MemoryEntry(
            id=str(uuid.uuid4()),
            content=chunk,
            embedding=self.memory_store.compute_embedding(chunk).tolist(),
            concepts=chunk_concepts,
            timestamp=datetime.now(),
        )
        self.memory_store.add_entry(entry)
        if self.config.save_after_update:
            self.save_memory()
        logger.debug(
            "Stored interaction in memory",
            agent=agent.name,
            entry_id=entry.id,
            concepts=chunk_concepts,
        )

    async def _store_chunks(
        self, agent: FlockAgent, chunks: str | list[str]
    ) -> None:
        """Store chunks (single or multiple) in memory."""
        if isinstance(chunks, str):
            await self._store_chunk(agent, chunks)
        elif isinstance(chunks, list):
            for chunk in tqdm(chunks, desc="Storing chunks in memory"):
                await self._store_chunk(agent, chunk)

    def save_memory(self) -> None:
        """Save memory store to file."""
        if self.memory_store and self.config.file_path:
            json_str = self.memory_store.model_dump_json()
            filename = self.get_memory_filename(self.name)
            with open(filename, "w") as file:
                file.write(json_str)
            self.memory_store.concept_graph.save_as_image(
                self.get_concept_graph_filename(self.name)
            )

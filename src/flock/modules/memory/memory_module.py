"""Memory module implementation for Flock agents."""

import json
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import Field
from tqdm import tqdm

from flock.core import FlockAgent, FlockModule, FlockModuleConfig
from flock.core.logging.logging import get_logger
from flock.modules.memory.memory_parser import MemoryMappingParser
from flock.modules.memory.memory_storage import FlockMemoryStore, MemoryEntry


class MemoryModuleConfig(FlockModuleConfig):
    """Configuration for the MemoryModule.

    This class defines the configuration for the MemoryModule, which is used to configure the memory module.
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
    splitting_mode: Literal["summary", "semantic", "characters"] = Field(
        default="splitter"
    )
    enable_read_only_mode: bool = Field(
        default=False, description="Whether to enable read only mode"
    )


logger = get_logger("memory")


class MemoryModule(FlockModule):
    """Module that adds memory capabilities to a Flock agent.

    This module encapsulates all memory-related functionality that was previously
    hardcoded into FlockAgent.
    """

    name: str = "memory"
    config: MemoryModuleConfig = Field(
        default_factory=MemoryModuleConfig,
        description="Memory module configuration",
    )
    memory_store: FlockMemoryStore | None = None
    memory_ops: list = []

    def __init__(self, name, config: MemoryModuleConfig):
        super().__init__(name=name, config=config)
        self.memory_store = FlockMemoryStore.load_from_file(
            self.get_memory_filename(name)
        )

        if not self.config.memory_mapping:
            self.memory_ops = []
            self.memory_ops.append({"type": "semantic"})
        else:
            self.memory_ops = MemoryMappingParser().parse(
                self.config.memory_mapping
            )

    async def initialize(
        self, agent: FlockAgent, inputs: dict[str, Any]
    ) -> None:
        """Initialize memory store if needed."""
        if not self.memory_store:
            self.memory_store = FlockMemoryStore.load_from_file(
                self.get_memory_filename(self.name)
            )

        if not self.config.memory_mapping:
            self.memory_ops = []
            self.memory_ops.append({"type": "semantic"})
        else:
            self.memory_ops = MemoryMappingParser().parse(
                self.config.memory_mapping
            )

        logger.debug(f"Initialized memory module for agent {agent.name}")

    async def pre_evaluate(
        self, agent: FlockAgent, inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """Check memory before evaluation."""
        if not self.memory_store:
            return inputs

        try:
            # Convert input to embedding
            input_text = json.dumps(inputs)
            query_embedding = self.memory_store.compute_embedding(input_text)

            # Extract concepts
            concepts = await self._extract_concepts(agent, input_text)

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
                    exact_results = self.memory_store.exact_match(inputs)
                    memory_results.extend(exact_results)

            if memory_results:
                logger.debug(
                    f"Found {len(memory_results)} relevant memories",
                    agent=agent.name,
                )
                inputs["memory_results"] = memory_results

            return inputs

        except Exception as e:
            logger.warning(f"Memory retrieval failed: {e!s}", agent=agent.name)
            return inputs

    def get_memory_filename(self, module_name: str) -> str:
        """Generate the full file path for the memory file.
        The filename is constructed as:
          {folder_path}{module_name}_{base_name}_{timestamp}{extension}
        where:
          - base_name is derived from the 'file_path' config (default "agent_memory")
          - timestamp is formatted with millisecond accuracy.
        """
        folder = self.config.folder_path
        if not folder.endswith("/") and not folder.endswith("\\"):
            folder += "/"
        import os

        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        # Get current time with millisecond accuracy
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        # Determine base filename and extension from file_path config
        if self.config.file_path:
            # Remove any directory components if accidentally provided
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
        """Generate the full file path for the concept graph image.
        The filename is constructed as:
          {folder_path}{module_name}_{base_name}_{timestamp}{extension}
        where:
          - base_name is derived from the 'concept_graph_file' config (default "concept_graph")
          - timestamp is formatted with millisecond accuracy.
        """
        folder = self.config.folder_path
        if not folder.endswith("/") and not folder.endswith("\\"):
            folder += "/"
        import os

        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
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
            # Convert input to embedding
            input_text = json.dumps(query)
            query_embedding = self.memory_store.compute_embedding(input_text)

            # Extract concepts
            concepts = await self._extract_concepts(agent, input_text)

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

            if memory_results:
                logger.debug(
                    f"Found {len(memory_results)} relevant memories",
                    agent=agent.name,
                )
                query["memory_results"] = memory_results

            return query

        except Exception as e:
            logger.warning(f"Memory retrieval failed: {e!s}", agent=agent.name)
            return query

    async def add_to_memory(
        self, agent: FlockAgent, data: dict[str, Any]
    ) -> None:
        """Add data to memory."""
        if not self.memory_store:
            return

        try:
            # Extract information chunks
            if self.config.splitting_mode == "semantic":
                chunks = await self._semantic_splitter_mode(agent, data, None)
            if self.config.splitting_mode == "summary":
                chunks = await self._summarize_mode(agent, data, None)
            elif self.config.splitting_mode == "characters":
                chunks = await self._character_splitter_mode(agent, data, None)

            if isinstance(chunks, str):
                chunk_concepts = await self._extract_concepts(agent, chunks)

                # Create memory entry
                entry = MemoryEntry(
                    id=str(uuid.uuid4()),
                    content=chunks,
                    embedding=self.memory_store.compute_embedding(
                        chunks
                    ).tolist(),
                    concepts=chunk_concepts,
                    timestamp=datetime.now(),
                )

                # Add to memory store
                self.memory_store.add_entry(entry)

                if self.config.save_after_update:
                    self.save_memory()

                logger.debug(
                    "Stored interaction in memory",
                    agent=agent.name,
                    entry_id=entry.id,
                    concepts=chunk_concepts,
                )

            if isinstance(chunks, list):
                for chunk in tqdm(chunks, desc="Storing chunks in memory"):
                    chunk_concepts = await self._extract_concepts(agent, chunk)

                    # Create memory entry
                    entry = MemoryEntry(
                        id=str(uuid.uuid4()),
                        content=str(chunk),
                        embedding=self.memory_store.compute_embedding(
                            str(chunk)
                        ).tolist(),
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

        except Exception as e:
            logger.warning(f"Memory storage failed: {e!s}", agent=agent.name)

    async def post_evaluate(
        self, agent: FlockAgent, inputs: dict[str, Any], result: dict[str, Any]
    ) -> dict[str, Any]:
        """Store results in memory after evaluation."""
        if not self.memory_store:
            return result

        try:
            # Extract information chunks
            if self.config.splitting_mode == "semantic":
                chunks = await self._semantic_splitter_mode(
                    agent, inputs, result
                )
            if self.config.splitting_mode == "summary":
                chunks = await self._summarize_mode(agent, inputs, result)
            elif self.config.splitting_mode == "characters":
                chunks = await self._character_splitter_mode(
                    agent, inputs, result
                )

            if isinstance(chunks, str):
                chunk_concepts = await self._extract_concepts(agent, chunks)

                # Create memory entry
                entry = MemoryEntry(
                    id=str(uuid.uuid4()),
                    content=chunks,
                    embedding=self.memory_store.compute_embedding(
                        chunks
                    ).tolist(),
                    concepts=chunk_concepts,
                    timestamp=datetime.now(),
                )

                # Add to memory store
                self.memory_store.add_entry(entry)

                if self.config.save_after_update:
                    self.save_memory()

                logger.debug(
                    "Stored interaction in memory",
                    agent=agent.name,
                    entry_id=entry.id,
                    concepts=chunk_concepts,
                )

            if isinstance(chunks, list):
                for chunk in tqdm(chunks, desc="Storing chunks in memory"):
                    chunk_concepts = await self._extract_concepts(agent, chunk)

                    # Create memory entry
                    entry = MemoryEntry(
                        id=str(uuid.uuid4()),
                        content=str(chunk),
                        embedding=self.memory_store.compute_embedding(
                            str(chunk)
                        ).tolist(),
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

        except Exception as e:
            logger.warning(f"Memory storage failed: {e!s}", agent=agent.name)

        return result

    async def terminate(
        self, agent: Any, inputs: dict[str, Any], result: dict[str, Any]
    ) -> None:
        """Save memory store if configured."""
        if self.config.save_after_update and self.memory_store:
            self.save_memory()

    async def _extract_concepts(self, agent: FlockAgent, text: str) -> set[str]:
        """Extract concepts using agent's LLM capabilities."""
        existing_concepts = None
        if self.memory_store.concept_graph:
            existing_concepts = set(
                self.memory_store.concept_graph.graph.nodes()
            )

        input = "text: str | Text to analyze"
        if existing_concepts:
            input += ", existing_concepts: list[str] | Already known concepts that might apply"

        # Create signature for concept extraction using agent's capabilities
        concept_signature = agent.create_dspy_signature_class(
            f"{agent.name}_concept_extractor",
            "Extract key concepts from text",
            f"{input} -> concepts: list[str] | Max five key concepts all lower case",
        )

        # Configure and run the predictor
        agent._configure_language_model(agent.model, True, 0.0, 8192)
        predictor = agent._select_task(concept_signature, "Completion")
        result = predictor(
            text=text,
            existing_concepts=list(existing_concepts)
            if existing_concepts
            else None,
        )

        concept_list = result.concepts if hasattr(result, "concepts") else []
        return set(concept_list)

    async def _summarize_mode(
        self, agent: FlockAgent, inputs: dict[str, Any], result: dict[str, Any]
    ) -> str:
        """Extract information chunks from interaction."""
        # Create splitter signature using agent's capabilities
        split_signature = agent.create_dspy_signature_class(
            f"{agent.name}_splitter",
            "Extract a list of potentially needed data and information for future reference",
            """
            content: str | The content to split
            -> chunks: list[str] | list of data and information for future reference
            """,
        )

        # Configure and run the predictor
        agent._configure_language_model(agent.model, True, 0.0, 8192)
        splitter = agent._select_task(split_signature, "Completion")

        # Get the content to split
        full_text = json.dumps(inputs) + json.dumps(result)
        split_result = splitter(content=full_text)

        return "\n".join(split_result.chunks)

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

    async def _semantic_splitter_mode(
        self, agent: FlockAgent, inputs: dict[str, Any], result: dict[str, Any]
    ) -> str:
        """Extract information chunks from interaction."""
        # Create splitter signature using agent's capabilities
        split_signature = agent.create_dspy_signature_class(
            f"{self.name}_splitter",
            "Split content into meaningful, self-contained chunks",
            """
            content: str | The content to split
            -> chunks: list[dict[str,str]] | List of chunks as key value pairs - keys are a short title and values are the content of the chunk
            """,
        )

        # Configure and run the predictor
        agent._configure_language_model(agent.model, True, 0.0, 8192)
        splitter = agent._select_task(split_signature, "Completion")

        # Get the content to split
        if result:
            full_text = json.dumps(inputs) + json.dumps(result)
        else:
            full_text = json.dumps(inputs)
        split_result = splitter(content=full_text)

        return split_result.chunks

    async def _character_splitter_mode(
        self, agent: FlockAgent, inputs: dict[str, Any], result: dict[str, Any]
    ) -> str:
        """Extract information chunks from interaction."""
        # Create splitter signature using agent's capabilities

        # Get the content to split
        if result:
            full_text = json.dumps(inputs) + json.dumps(result)
        else:
            full_text = json.dumps(inputs)
        # Split full text by max_length characters
        chunks = [
            full_text[i : i + self.config.max_length]
            for i in range(0, len(full_text), self.config.max_length)
        ]

        return chunks

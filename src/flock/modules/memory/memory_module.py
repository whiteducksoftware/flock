"""Memory module implementation for Flock agents."""

import json
import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from flock.core import FlockAgent, FlockModule, FlockModuleConfig
from flock.core.logging.logging import get_logger
from flock.modules.memory.memory_parser import MemoryMappingParser
from flock.modules.memory.memory_storage import FlockMemoryStore, MemoryEntry


class MemoryModuleConfig(FlockModuleConfig):
    """Configuration for the memory module."""

    file_path: str | None = Field(
        default="agent_memory.json", description="Path to save memory file"
    )
    memory_mapping: str | None = Field(
        default=None, description="Memory mapping configuration"
    )
    similarity_threshold: float = Field(
        default=0.5, description="Threshold for semantic similarity"
    )
    context_window: int = Field(
        default=3, description="Number of memory entries to return"
    )
    max_length: int = Field(
        default=1000, description="Max length of memory entry before splitting"
    )
    save_after_update: bool = Field(
        default=True, description="Whether to save memory after each update"
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

    async def pre_initialize(
        self, agent: FlockAgent, inputs: dict[str, Any]
    ) -> None:
        """Initialize memory store if needed."""
        if not self.memory_store:
            self.memory_store = FlockMemoryStore.load_from_file(
                self.config.file_path
            )

        if not self.config.memory_mapping:
            self.memory_ops = []
            self.memory_ops.append({"type": "semantic"})
        else:
            self.memory_ops = MemoryMappingParser().parse(
                self.config.memory_mapping
            )

        logger.debug(f"Initialized memory module for agent {agent.name}")

    async def post_initialize(self, agent: Any, inputs: dict[str, Any]) -> None:
        """No post-initialization needed."""
        pass

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

    async def post_evaluate(
        self, agent: FlockAgent, inputs: dict[str, Any], result: dict[str, Any]
    ) -> dict[str, Any]:
        """Store results in memory after evaluation."""
        if not self.memory_store:
            return result

        try:
            # Extract information chunks
            chunks = await self._extract_information(agent, inputs, result)
            chunk_concepts = await self._extract_concepts(agent, chunks)

            # Create memory entry
            entry = MemoryEntry(
                id=str(uuid.uuid4()),
                content=chunks,
                embedding=self.memory_store.compute_embedding(chunks).tolist(),
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

        except Exception as e:
            logger.warning(f"Memory storage failed: {e!s}", agent=agent.name)

        return result

    async def pre_terminate(
        self, agent: Any, inputs: dict[str, Any], result: dict[str, Any]
    ) -> None:
        """No pre-termination needed."""
        pass

    async def post_terminate(
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
        agent._configure_language_model()
        predictor = agent._select_task(concept_signature, "Completion")
        result = predictor(
            text=text,
            existing_concepts=list(existing_concepts)
            if existing_concepts
            else None,
        )

        concept_list = result.concepts if hasattr(result, "concepts") else []
        return set(concept_list)

    async def _extract_information(
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
        agent._configure_language_model()
        splitter = agent._select_task(split_signature, "Completion")

        # Get the content to split
        full_text = json.dumps(inputs) + json.dumps(result)
        split_result = splitter(content=full_text)

        return "\n".join(split_result.chunks)

    def save_memory(self) -> None:
        """Save memory store to file."""
        if self.memory_store and self.config.file_path:
            json_str = self.memory_store.model_dump_json()
            with open(self.config.file_path, "w") as file:
                file.write(json_str)

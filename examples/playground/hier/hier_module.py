"""Hierarchical Memory module implementation for Flock agents."""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import Field
from tqdm import tqdm

from flock.core import FlockAgent, FlockModule
from flock.core.logging.logging import get_logger
from flock.modules.memory.memory_parser import MemoryMappingParser
from flock.modules.memory.memory_storage import FlockMemoryStore, MemoryEntry

# Import our new hierarchical components
from hierarchical_memory_implementation import (
    ConceptRelationType,
    HierarchicalFlockMemoryStore, 
    HierarchicalMemoryGraph,
    MemoryModuleConfig
)

logger = get_logger("memory")


class HierarchicalMemoryModule(FlockModule):
    """Module that adds hierarchical memory capabilities to a Flock agent.

    This module extends the original MemoryModule with support for concept hierarchies,
    allowing for more nuanced and powerful knowledge organization.
    """

    name: str = "hierarchical_memory"
    config: MemoryModuleConfig = Field(
        default_factory=MemoryModuleConfig,
        description="Hierarchical memory module configuration",
    )
    memory_store: HierarchicalFlockMemoryStore | None = None
    memory_ops: list = []

    def __init__(self, name, config: MemoryModuleConfig):
        super().__init__(name=name, config=config)
        self.memory_store = HierarchicalFlockMemoryStore.load_from_file(
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
            self.memory_store = HierarchicalFlockMemoryStore.load_from_file(
                self.get_memory_filename(self.name)
            )

        if not self.config.memory_mapping:
            self.memory_ops = []
            self.memory_ops.append({"type": "semantic"})
        else:
            self.memory_ops = MemoryMappingParser().parse(
                self.config.memory_mapping
            )

        logger.debug(f"Initialized hierarchical memory module for agent {agent.name}")

    async def pre_evaluate(
        self, agent: FlockAgent, inputs: dict[str, Any]
    ) -> dict[str, Any]:
        """Check memory before evaluation, using hierarchical concept retrieval."""
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
                    # Use hierarchical retrieval if enabled
                    semantic_results = self.memory_store.retrieve(
                        query_embedding,
                        concepts,
                        similarity_threshold=self.config.similarity_threshold,
                        use_hierarchical=self.config.enable_hierarchical_concepts,
                        upward_factor=self.config.upward_propagation_factor,
                        downward_factor=self.config.downward_propagation_factor,
                    )
                    memory_results.extend(semantic_results)

                elif op["type"] == "exact":
                    exact_results = self.memory_store.exact_match(inputs)
                    memory_results.extend(exact_results)

            if memory_results:
                logger.debug(
                    f"Found {len(memory_results)} relevant memories using hierarchical concepts",
                    agent=agent.name,
                )
                inputs["memory_results"] = memory_results

            return inputs

        except Exception as e:
            logger.warning(f"Hierarchical memory retrieval failed: {e!s}", agent=agent.name)
            return inputs

    def get_memory_filename(self, module_name: str) -> str:
        """Generate the full file path for the memory file."""
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
            base, ext = "hierarchical_memory", ".json"
        return f"{folder}{module_name}_{base}{ext}"

    def get_concept_graph_filename(self, module_name: str) -> str:
        """Generate the full file path for the concept graph image."""
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
            base, ext = "hierarchical_concept_graph", ".png"
        return f"{folder}{module_name}_{base}_{timestamp}{ext}"

    async def add_hierarchical_relationship(
        self, 
        agent: FlockAgent, 
        child_concept: str, 
        parent_concept: str,
        relation_type: ConceptRelationType = ConceptRelationType.IS_A,
        weight: float = 1.0,
        metadata: Dict[str, Any] = None
    ) -> None:
        """Add a hierarchical relationship between concepts.
        
        Args:
            agent: The FlockAgent using this memory module
            child_concept: The more specific concept (e.g., "cat")
            parent_concept: The more general concept (e.g., "animal")
            relation_type: Type of relationship (IS_A, HAS_A, etc.)
            weight: Strength of the relationship
            metadata: Additional information about the relationship
        """
        if not self.memory_store:
            logger.warning("Cannot add relationship - memory store not initialized")
            return
            
        try:
            self.memory_store.add_hierarchical_concept(
                child_concept=child_concept,
                parent_concept=parent_concept,
                relation_type=relation_type,
                weight=weight,
                metadata=metadata
            )
            
            logger.debug(
                f"Added hierarchical relationship: {child_concept} -{relation_type}-> {parent_concept}",
                agent=agent.name
            )
            
            if self.config.save_after_update:
                self.save_memory()
                
        except Exception as e:
            logger.warning(f"Failed to add hierarchical relationship: {e}", agent=agent.name)

    async def infer_hierarchical_relationships(
        self, 
        agent: FlockAgent, 
        concepts: Set[str]
    ) -> None:
        """Automatically infer possible hierarchical relationships among concepts.
        
        This uses the agent's LLM capabilities to identify potential hierarchical
        relationships between concepts.
        
        Args:
            agent: The FlockAgent to use for inference
            concepts: Set of concepts to analyze for relationships
        """
        if not self.memory_store or len(concepts) < 2:
            return
            
        try:
            # Create signature for relationship extraction
            relation_signature = agent.create_dspy_signature_class(
                f"{agent.name}_hierarchy_extractor",
                "Extract hierarchical relationships between concepts",
                """
                concepts: list[str] | List of concepts to analyze
                -> relationships: list[dict] | List of dictionaries with 'child', 'parent', and 'relation_type' keys
                """,
            )
            
            # Configure and run the predictor
            agent._configure_language_model(agent.model, True, 0.0, 8192)
            predictor = agent._select_task(relation_signature, "Completion")
            
            # Run inference to extract potential relationships
            result = predictor(concepts=list(concepts))
            
            if hasattr(result, "relationships") and result.relationships:
                for rel in result.relationships:
                    if "child" in rel and "parent" in rel:
                        # Default to IS_A if no relation_type specified
                        rel_type = rel.get("relation_type", "IS_A").upper()
                        
                        # Convert string relation type to enum
                        try:
                            relation_type = ConceptRelationType[rel_type]
                        except KeyError:
                            relation_type = ConceptRelationType.IS_A
                            
                        # Add the inferred relationship
                        await self.add_hierarchical_relationship(
                            agent=agent,
                            child_concept=rel["child"],
                            parent_concept=rel["parent"],
                            relation_type=relation_type
                        )
                        
                logger.debug(
                    f"Inferred {len(result.relationships)} hierarchical relationships",
                    agent=agent.name
                )
                
        except Exception as e:
            logger.warning(f"Failed to infer hierarchical relationships: {e}", agent=agent.name)

    async def search_memory(
        self, agent: FlockAgent, query: dict[str, Any]
    ) -> list[str]:
        """Search memory for the query using hierarchical concepts."""
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
                        use_hierarchical=self.config.enable_hierarchical_concepts,
                    )
                    memory_results.extend(semantic_results)

                elif op["type"] == "exact":
                    exact_results = self.memory_store.exact_match(query)
                    memory_results.extend(exact_results)

            if memory_results:
                logger.debug(
                    f"Found {len(memory_results)} relevant memories with hierarchical search",
                    agent=agent.name,
                )
                query["memory_results"] = memory_results

            return query

        except Exception as e:
            logger.warning(f"Hierarchical memory search failed: {e!s}", agent=agent.name)
            return query

    async def add_to_memory(
        self, agent: FlockAgent, data: dict[str, Any]
    ) -> None:
        """Add data to memory with hierarchical concept extraction."""
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
                
                # If hierarchical concepts are enabled, try to infer relationships
                if self.config.enable_hierarchical_concepts and len(chunk_concepts) > 1:
                    await self.infer_hierarchical_relationships(agent, chunk_concepts)

                if self.config.save_after_update:
                    self.save_memory()

                logger.debug(
                    "Stored interaction in hierarchical memory",
                    agent=agent.name,
                    entry_id=entry.id,
                    concepts=chunk_concepts,
                )

            if isinstance(chunks, list):
                all_concepts = set()
                
                for chunk in tqdm(chunks, desc="Storing chunks in hierarchical memory"):
                    chunk_concepts = await self._extract_concepts(agent, chunk)
                    all_concepts.update(chunk_concepts)

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
                        "Stored chunk in hierarchical memory",
                        agent=agent.name,
                        entry_id=entry.id,
                        concepts=chunk_concepts,
                    )
                
                # Process all concepts together for better hierarchy inference
                if self.config.enable_hierarchical_concepts and len(all_concepts) > 1:
                    await self.infer_hierarchical_relationships(agent, all_concepts)

        except Exception as e:
            logger.warning(f"Hierarchical memory storage failed: {e!s}", agent=agent.name)

    async def post_evaluate(
        self, agent: FlockAgent, inputs: dict[str, Any], result: dict[str, Any]
    ) -> dict[str, Any]:
        """Store results in memory after evaluation, with hierarchical concept support."""
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
                
                # Try to infer hierarchical relationships
                if self.config.enable_hierarchical_concepts and len(chunk_concepts) > 1:
                    await self.infer_hierarchical_relationships(agent, chunk_concepts)

                if self.config.save_after_update:
                    self.save_memory()

                logger.debug(
                    "Stored evaluation in hierarchical memory",
                    agent=agent.name,
                    entry_id=entry.id,
                    concepts=chunk_concepts,
                )

            if isinstance(chunks, list):
                all_concepts = set()
                
                for chunk in tqdm(chunks, desc="Storing evaluation chunks in memory"):
                    chunk_concepts = await self._extract_concepts(agent, chunk)
                    all_concepts.update(chunk_concepts)

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
                        "Stored evaluation chunk in hierarchical memory",
                        agent=agent.name,
                        entry_id=entry.id,
                        concepts=chunk_concepts,
                    )
                
                # Process all concepts together for better hierarchy inference
                if self.config.enable_hierarchical_concepts and len(all_concepts) > 1:
                    await self.infer_hierarchical_relationships(agent, all_concepts)

        except Exception as e:
            logger.warning(f"Hierarchical memory evaluation storage failed: {e!s}", agent=agent.name)

        return result

    async def terminate(
        self, agent: Any, inputs: dict[str, Any], result: dict[str, Any]
    ) -> None:
        """Save memory store if configured."""
        if self.config.save_after_update and self.memory_store:
            self.save_memory()

    async def _extract_concepts(self, agent: FlockAgent, text: str) -> set[str]:
        """Extract concepts using agent's LLM capabilities, with hierarchy awareness."""
        existing_concepts = None
        if self.memory_store and hasattr(self.memory_store, 'concept_graph'):
            existing_concepts = set(
                self.memory_store.concept_graph.graph.nodes()
            )

        input_desc = "text: str | Text to analyze"
        if existing_concepts:
            input_desc += ", existing_concepts: list[str] | Already known concepts that might apply"

        # Create signature for concept extraction using agent's capabilities
        concept_signature = agent.create_dspy_signature_class(
            f"{agent.name}_hierarchical_concept_extractor",
            "Extract key concepts from text with hierarchical awareness",
            f"{input_desc} -> concepts: list[str] | Key concepts extracted from text, all lowercase",
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
        """Save memory store to file with hierarchical concept graph."""
        if self.memory_store and self.config.file_path:
            json_str = self.memory_store.model_dump_json()
            filename = self.get_memory_filename(self.name)
            with open(filename, "w") as file:
                file.write(json_str)

            # Save the enhanced hierarchical concept graph
            if hasattr(self.memory_store, 'concept_graph'):
                self.memory_store.concept_graph.save_as_image(
                    self.get_concept_graph_filename(self.name)
                )
            
            logger.info(f"Saved hierarchical memory to {filename}")

    async def _semantic_splitter_mode(
        self, agent: FlockAgent, inputs: dict[str, Any], result: dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Extract information chunks from interaction with hierarchical awareness.
        
        This version tries to identify potential hierarchical relationships within the content.
        """
        # Create splitter signature using agent's capabilities
        split_signature = agent.create_dspy_signature_class(
            f"{self.name}_hierarchical_splitter",
            "Split content into meaningful, self-contained chunks with concept hierarchies",
            """
            content: str | The content to split
            -> chunks: list[dict[str,str]] | List of chunks as key value pairs - keys are a short title and values are the content of the chunk
            -> potential_hierarchies: list[dict] | Optional list of hierarchical relationships in the form [{"child": "concept1", "parent": "concept2", "relation_type": "IS_A"}, ...]
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
        
        # Process any extracted hierarchical relationships
        if self.config.enable_hierarchical_concepts and hasattr(split_result, "potential_hierarchies"):
            hierarchies = split_result.potential_hierarchies
            for rel in hierarchies:
                if "child" in rel and "parent" in rel:
                    # Default to IS_A if no relation_type specified
                    rel_type = rel.get("relation_type", "IS_A").upper()
                    
                    # Convert string relation type to enum
                    try:
                        relation_type = ConceptRelationType[rel_type]
                    except KeyError:
                        relation_type = ConceptRelationType.IS_A
                        
                    # Add the relationship to the memory store
                    if self.memory_store:
                        self.memory_store.add_hierarchical_concept(
                            child_concept=rel["child"].lower(),
                            parent_concept=rel["parent"].lower(),
                            relation_type=relation_type,
                            weight=1.0
                        )
            
            if hierarchies:
                logger.debug(f"Added {len(hierarchies)} hierarchical relationships from semantic splitter")

        return split_result.chunks

    async def _character_splitter_mode(
        self, agent: FlockAgent, inputs: dict[str, Any], result: dict[str, Any]
    ) -> List[str]:
        """Extract information chunks from interaction based on character count."""
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
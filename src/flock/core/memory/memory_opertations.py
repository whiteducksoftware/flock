from abc import ABC, abstractmethod
from typing import Any, Optional
from pydantic import BaseModel, Field

class MemoryOperation(BaseModel, ABC):
    """Base class for all memory operations."""
    
    name: str
    threshold: float = Field(default=0.8)
    
    @abstractmethod
    async def execute(self, inputs: dict[str, Any], context: Any) -> Optional[dict[str, Any]]:
        """Execute the memory operation."""
        pass

class SemanticOperation(MemoryOperation):
    """Semantic search using DSPy embeddings."""
    
    name: str = "semantic"
    model: str = Field(default="default")  # Uses agent's model if default
    
    async def execute(self, inputs: dict[str, Any], context: Any) -> Optional[dict[str, Any]]:
        # Use DSPy's infrastructure for embeddings
        signature = context.create_dspy_signature_class(
            "semantic_search",
            "Semantic search in memory",
            "query: str -> embedding: list[float]"
        )
        predictor = context._select_task(signature, "Completion")
        return await predictor(query=str(inputs))

class ExactOperation(MemoryOperation):
    """Exact matching using input patterns."""
    
    name: str = "exact"
    
    async def execute(self, inputs: dict[str, Any], context: Any) -> Optional[dict[str, Any]]:
        # Direct key-based lookup
        return context.memory_store.exact_match(inputs)

class CombineOperation(MemoryOperation):
    """Combines results from multiple operations."""
    
    name: str = "combine"
    weights: dict[str, float] = Field(default_factory=lambda: {"semantic": 0.7, "exact": 0.3})
    
    async def execute(self, inputs: dict[str, Any], context: Any) -> Optional[dict[str, Any]]:
        # Weighted combination of results
        return context.memory_store.combine_results(inputs, self.weights)
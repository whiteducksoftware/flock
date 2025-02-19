from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel

class MemoryEntry(BaseModel):
    """A single memory entry."""
    
    id: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    embedding: Optional[list[float]] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)

class FlockMemoryStore(BaseModel):
    """Native Flock memory storage."""
    
    entries: list[MemoryEntry] = Field(default_factory=list)
    index: Optional[Any] = None  # Vector index for fast similarity search
    
    def add_entry(self, entry: MemoryEntry) -> None:
        """Add a new memory entry."""
        self.entries.append(entry)
        if entry.embedding is not None:
            self._update_index(entry)
    
    def semantic_search(self, embedding: list[float], threshold: float = 0.8) -> list[MemoryEntry]:
        """Search by embedding similarity."""
        if self.index is None:
            return []
        return self._search_index(embedding, threshold)
    
    def exact_match(self, pattern: dict[str, Any]) -> list[MemoryEntry]:
        """Search for exact matches."""
        return [e for e in self.entries if self._matches_pattern(e, pattern)]
    
    def combine_results(self, semantic_results: list[MemoryEntry], 
                       exact_results: list[MemoryEntry],
                       weights: dict[str, float]) -> list[MemoryEntry]:
        """Combine results using weighted scoring."""
        # Implementation of result combination
        pass
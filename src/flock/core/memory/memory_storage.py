from datetime import datetime
from typing import Any

import networkx as nx
import numpy as np
from opentelemetry import trace
from pydantic import BaseModel, Field

tracer = trace.get_tracer(__name__)


class MemoryEntry(BaseModel):
    """A single memory entry."""

    id: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    embedding: list[float] | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
    access_count: int = Field(default=0)
    concepts: set[str] = Field(default_factory=set)
    decay_factor: float = Field(default=1.0)


class MemoryGraph(BaseModel):
    """Graph representation of concept relationships."""

    graph: nx.Graph = Field(default_factory=nx.Graph)

    def add_concepts(self, concepts: set[str]) -> None:
        """Add concepts and their relationships to the graph."""
        for concept in concepts:
            self.graph.add_node(concept)

        # Add edges between concepts (associations)
        for c1 in concepts:
            for c2 in concepts:
                if c1 != c2:
                    if self.graph.has_edge(c1, c2):
                        self.graph[c1][c2]["weight"] += 1
                    else:
                        self.graph.add_edge(c1, c2, weight=1)

    def spread_activation(
        self, initial_concepts: set[str], decay_factor: float = 0.5
    ) -> dict[str, float]:
        """Spread activation through the concept graph."""
        activated = {concept: 1.0 for concept in initial_concepts}
        frontier = list(initial_concepts)

        while frontier:
            current = frontier.pop(0)
            current_activation = activated[current]

            for neighbor in self.graph.neighbors(current):
                weight = self.graph[current][neighbor]["weight"]
                new_activation = current_activation * decay_factor * weight

                if (
                    neighbor not in activated
                    or activated[neighbor] < new_activation
                ):
                    activated[neighbor] = new_activation
                    frontier.append(neighbor)

        return activated


class FlockMemoryStore(BaseModel):
    """Enhanced Flock memory storage with short-term and long-term memory."""

    short_term: list[MemoryEntry] = Field(default_factory=list)
    long_term: list[MemoryEntry] = Field(default_factory=list)
    concept_graph: MemoryGraph = Field(default_factory=MemoryGraph)

    # Clustering and organization
    clusters: dict[int, list[MemoryEntry]] = Field(default_factory=dict)
    cluster_centroids: dict[int, np.ndarray] = Field(default_factory=dict)

    def add_entry(self, entry: MemoryEntry) -> None:
        """Add a new memory entry to short-term memory."""
        with tracer.start_as_current_span("memory.add_entry") as span:
            span.set_attribute("entry.id", entry.id)

            self.short_term.append(entry)
            self.concept_graph.add_concepts(entry.concepts)
            self._update_clusters()

            # Check for promotion to long-term memory
            if entry.access_count > 10:
                self._promote_to_long_term(entry)

    def _promote_to_long_term(self, entry: MemoryEntry) -> None:
        """Promote an entry to long-term memory."""
        if entry not in self.long_term:
            self.long_term.append(entry)
            # Could implement additional long-term processing here

    def retrieve(
        self,
        query_embedding: np.ndarray,
        query_concepts: set[str],
        similarity_threshold: float = 0.8,
        exclude_last_n: int = 0,
    ) -> list[MemoryEntry]:
        """Advanced retrieval using multiple strategies."""
        with tracer.start_as_current_span("memory.retrieve") as span:
            # Semantic similarity
            semantic_matches = self._semantic_search(
                query_embedding,
                threshold=similarity_threshold,
                exclude_last_n=exclude_last_n,
            )

            # Concept-based activation
            activated_concepts = self.concept_graph.spread_activation(
                query_concepts
            )

            # Combine results with decay and reinforcement
            results = []
            for entry in semantic_matches:
                # Calculate semantic similarity score
                similarity = self._calculate_similarity(
                    query_embedding, entry.embedding
                )

                # Calculate concept activation score
                concept_score = sum(
                    activated_concepts.get(c, 0) for c in entry.concepts
                )

                # Apply time-based decay
                time_diff = (datetime.now() - entry.timestamp).total_seconds()
                decay = np.exp(-0.0001 * time_diff)  # Configurable decay rate

                # Apply reinforcement from access count
                reinforcement = np.log1p(entry.access_count)

                # Calculate final score
                final_score = (
                    similarity * 0.4  # Semantic similarity weight
                    + concept_score * 0.3  # Concept relevance weight
                    + decay * 0.2  # Recency weight
                    + reinforcement * 0.1  # Usage weight
                ) * entry.decay_factor

                results.append((final_score, entry))

            # Sort by final score
            results.sort(key=lambda x: x[0], reverse=True)

            # Update access counts and decay factors
            for _, entry in results:
                entry.access_count += 1
                self._update_decay_factors(entry)

            return [entry for _, entry in results]

    def _update_decay_factors(self, retrieved_entry: MemoryEntry) -> None:
        """Update decay factors based on retrieval."""
        # Increase decay factor for retrieved entry
        retrieved_entry.decay_factor *= 1.1  # Configurable increase

        # Decrease decay factor for non-retrieved entries
        for entry in self.short_term:
            if entry != retrieved_entry:
                entry.decay_factor *= 0.9  # Configurable decrease

    def _update_clusters(self) -> None:
        """Update memory clusters using embeddings."""
        if len(self.short_term) < 2:
            return

        embeddings = np.vstack([entry.embedding for entry in self.short_term])

        # Use k-means clustering
        from sklearn.cluster import KMeans

        n_clusters = min(10, len(self.short_term))
        kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        labels = kmeans.fit_predict(embeddings)

        # Update clusters
        self.clusters.clear()
        self.cluster_centroids.clear()

        for i in range(n_clusters):
            cluster_entries = [
                entry
                for entry, label in zip(self.short_term, labels)
                if label == i
            ]
            self.clusters[i] = cluster_entries
            self.cluster_centroids[i] = kmeans.cluster_centers_[i]

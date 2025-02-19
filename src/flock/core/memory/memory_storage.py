import json
from datetime import datetime
from typing import Any

import networkx as nx
import numpy as np
from networkx.readwrite import json_graph
from opentelemetry import trace
from pydantic import BaseModel, Field, PrivateAttr

# Import SentenceTransformer for production-grade embeddings.
from sentence_transformers import SentenceTransformer

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


from pydantic import BaseModel, Field


class MemoryGraph(BaseModel):
    """Graph representation of concept relationships.
    The graph is stored as a JSON string for serialization, while a private attribute holds the actual NetworkX graph.
    """

    # JSON representation using the node-link format with explicit edges="links" to avoid warnings.
    graph_json: str = Field(
        default_factory=lambda: json.dumps(
            json_graph.node_link_data(nx.Graph(), edges="links")
        )
    )

    # Private attribute for the actual NetworkX graph.
    _graph: nx.Graph = PrivateAttr()

    def __init__(self, **data):
        super().__init__(**data)
        try:
            # Reconstruct the graph from the JSON representation, explicitly setting edges="links".
            data_graph = json.loads(self.graph_json)
            self._graph = json_graph.node_link_graph(data_graph, edges="links")
        except Exception:
            self._graph = nx.Graph()

    @property
    def graph(self) -> nx.Graph:
        """Provides access to the internal NetworkX graph."""
        return self._graph

    def update_graph_json(self) -> None:
        """Update the JSON representation based on the current state of the graph."""
        self.graph_json = json.dumps(
            json_graph.node_link_data(self._graph, edges="links")
        )

    def add_concepts(self, concepts: set[str]) -> None:
        """Add a set of concepts to the graph and update their associations."""
        for concept in concepts:
            self._graph.add_node(concept)
        for c1 in concepts:
            for c2 in concepts:
                if c1 != c2:
                    if self._graph.has_edge(c1, c2):
                        self._graph[c1][c2]["weight"] += 1
                    else:
                        self._graph.add_edge(c1, c2, weight=1)
        self.update_graph_json()

    def spread_activation(
        self, initial_concepts: set[str], decay_factor: float = 0.5
    ) -> dict[str, float]:
        """Spread activation through the concept graph.

        Args:
            initial_concepts: The starting set of concepts.
            decay_factor: How much the activation decays at each step.

        Returns:
            A dictionary mapping each concept to its activation level.
        """
        activated = {concept: 1.0 for concept in initial_concepts}
        frontier = list(initial_concepts)

        while frontier:
            current = frontier.pop(0)
            current_activation = activated[current]
            for neighbor in self._graph.neighbors(current):
                weight = self._graph[current][neighbor]["weight"]
                new_activation = current_activation * decay_factor * weight
                if (
                    neighbor not in activated
                    or activated[neighbor] < new_activation
                ):
                    activated[neighbor] = new_activation
                    frontier.append(neighbor)

        return activated


class FlockMemoryStore(BaseModel):
    """Enhanced Flock memory storage with short-term and long-term memory,
    including embedding-based semantic search, exact matching, and result combination.
    """

    short_term: list[MemoryEntry] = Field(default_factory=list)
    long_term: list[MemoryEntry] = Field(default_factory=list)
    concept_graph: MemoryGraph = Field(default_factory=MemoryGraph)
    clusters: dict[int, list[MemoryEntry]] = Field(default_factory=dict)
    # Instead of np.ndarray, store centroids as lists of floats.
    cluster_centroids: dict[int, list[float]] = Field(default_factory=dict)

    # The embedding model is stored as a private attribute, as it's not serializable.
    _embedding_model: SentenceTransformer | None = PrivateAttr(default=None)

    def get_embedding_model(self) -> SentenceTransformer:
        """Initialize and return the SentenceTransformer model.
        Uses "all-MiniLM-L6-v2" as the default model.
        """
        if self._embedding_model is None:
            try:
                self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception as e:
                raise RuntimeError(f"Failed to load embedding model: {e}")
        return self._embedding_model

    def compute_embedding(self, text: str) -> np.ndarray:
        """Compute and return the embedding for the provided text as a NumPy array."""
        model = self.get_embedding_model()
        try:
            embedding = model.encode(text, convert_to_numpy=True)
            return embedding
        except Exception as e:
            raise RuntimeError(f"Error computing embedding: {e}")

    def _calculate_similarity(
        self, query_embedding: np.ndarray, entry_embedding: np.ndarray
    ) -> float:
        """Compute the cosine similarity between two embeddings.
        Returns a float between 0 and 1.
        """
        try:
            norm_query = np.linalg.norm(query_embedding)
            norm_entry = np.linalg.norm(entry_embedding)
            if norm_query == 0 or norm_entry == 0:
                return 0.0
            similarity = float(
                np.dot(query_embedding, entry_embedding)
                / (norm_query * norm_entry)
            )
            return similarity
        except Exception as e:
            raise RuntimeError(f"Error computing similarity: {e}")

    def exact_match(self, inputs: dict[str, Any]) -> list[MemoryEntry]:
        """Perform an exact key-based lookup in short-term memory.
        Returns entries where all provided key-value pairs exist in the entry's inputs.
        """
        matches = []
        for entry in self.short_term:
            if all(item in entry.inputs.items() for item in inputs.items()):
                matches.append(entry)
        return matches

    def combine_results(
        self, inputs: dict[str, Any], weights: dict[str, float]
    ) -> dict[str, Any]:
        """Combine semantic and exact match results using the provided weights.

        Args:
            inputs: Input dictionary to search memory.
            weights: Dictionary with keys "semantic" and "exact" for weighting.

        Returns:
            A dictionary with "combined_results" as a sorted list of memory entries.
        """
        query_text = " ".join(str(value) for value in inputs.values())
        query_embedding = self.compute_embedding(query_text)

        semantic_matches = self.retrieve(
            query_embedding, set(inputs.values()), similarity_threshold=0.8
        )
        exact_matches = self.exact_match(inputs)

        combined: dict[str, dict[str, Any]] = {}
        for entry in semantic_matches:
            if entry.embedding is None:
                continue
            semantic_score = self._calculate_similarity(
                query_embedding, np.array(entry.embedding)
            )
            combined[entry.id] = {
                "entry": entry,
                "semantic_score": semantic_score * weights.get("semantic", 0.7),
                "exact_score": 0.0,
            }
        for entry in exact_matches:
            if entry.id in combined:
                combined[entry.id]["exact_score"] = 1.0 * weights.get(
                    "exact", 0.3
                )
            else:
                combined[entry.id] = {
                    "entry": entry,
                    "semantic_score": 0.0,
                    "exact_score": 1.0 * weights.get("exact", 0.3),
                }
        results: list[tuple[float, MemoryEntry]] = []
        for data in combined.values():
            total_score = data["semantic_score"] + data["exact_score"]
            results.append((total_score, data["entry"]))
        results.sort(key=lambda x: x[0], reverse=True)
        return {"combined_results": [entry for score, entry in results]}

    def add_entry(self, entry: MemoryEntry) -> None:
        """Add a new memory entry to short-term memory, update the concept graph and clusters.

        and check for promotion to long-term memory.
        """
        with tracer.start_as_current_span("memory.add_entry") as span:
            span.set_attribute("entry.id", entry.id)
            self.short_term.append(entry)
            self.concept_graph.add_concepts(entry.concepts)
            self._update_clusters()
            if entry.access_count > 10:
                self._promote_to_long_term(entry)

    def _promote_to_long_term(self, entry: MemoryEntry) -> None:
        """Promote an entry to long-term memory."""
        if entry not in self.long_term:
            self.long_term.append(entry)

    def retrieve(
        self,
        query_embedding: np.ndarray,
        query_concepts: set[str],
        similarity_threshold: float = 0.8,
        exclude_last_n: int = 0,
    ) -> list[MemoryEntry]:
        """Retrieve memory entries using semantic similarity and concept-based activation.

        Args:
            query_embedding: The embedding for the query text.
            query_concepts: A set of concepts derived from the query.
            similarity_threshold: Minimum score to consider a match.
            exclude_last_n: Exclude the last N entries (if needed).

        Returns:
            A list of MemoryEntry objects sorted by a combined score.
        """
        with tracer.start_as_current_span("memory.retrieve") as span:
            results = []
            current_time = datetime.now()
            decay_rate = 0.0001
            norm_query = query_embedding / (
                np.linalg.norm(query_embedding) + 1e-8
            )

            entries = (
                self.short_term[:-exclude_last_n]
                if exclude_last_n > 0
                else self.short_term
            )
            for entry in entries:
                if entry.embedding is None:
                    continue
                entry_embedding = np.array(entry.embedding)
                norm_entry = entry_embedding / (
                    np.linalg.norm(entry_embedding) + 1e-8
                )
                similarity = float(np.dot(norm_query, norm_entry))
                time_diff = (current_time - entry.timestamp).total_seconds()
                decay = np.exp(-decay_rate * time_diff)
                reinforcement = np.log1p(entry.access_count)
                final_score = (
                    similarity * decay * reinforcement * entry.decay_factor
                )
                span.add_event(
                    "memory score",
                    attributes={"entry_id": entry.id, "score": final_score},
                )
                if final_score >= similarity_threshold:
                    results.append((final_score, entry))
            for _, entry in results:
                entry.access_count += 1
                self._update_decay_factors(entry)
            results.sort(key=lambda x: x[0], reverse=True)
            return [entry for score, entry in results]

    def _update_decay_factors(self, retrieved_entry: MemoryEntry) -> None:
        """Update decay factors: increase for the retrieved entry and decrease for others."""
        retrieved_entry.decay_factor *= 1.1
        for entry in self.short_term:
            if entry != retrieved_entry:
                entry.decay_factor *= 0.9

    def _update_clusters(self) -> None:
        """Update memory clusters using k-means clustering on entry embeddings."""
        if len(self.short_term) < 2:
            return

        valid_entries = [
            entry for entry in self.short_term if entry.embedding is not None
        ]
        if not valid_entries:
            return

        embeddings = [np.array(entry.embedding) for entry in valid_entries]
        embeddings_matrix = np.vstack(embeddings)

        from sklearn.cluster import KMeans

        n_clusters = min(10, len(embeddings))
        kmeans = KMeans(n_clusters=n_clusters, random_state=42)
        labels = kmeans.fit_predict(embeddings_matrix)

        self.clusters.clear()
        self.cluster_centroids.clear()

        for i in range(n_clusters):
            cluster_entries = [
                entry
                for entry, label in zip(valid_entries, labels)
                if label == i
            ]
            self.clusters[i] = cluster_entries
            # Convert the centroid (np.ndarray) to a list of floats.
            self.cluster_centroids[i] = kmeans.cluster_centers_[i].tolist()

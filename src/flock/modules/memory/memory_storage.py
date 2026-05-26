"""Flock memory storage with short-term and long-term memory, concept graph, and clustering.

Based on concept graph spreading activation and embedding-based semantic search.
"""

import json
from datetime import datetime
from enum import Enum
from typing import Any, Literal

import networkx as nx
import numpy as np
from networkx.readwrite import json_graph
from opentelemetry import trace
from pydantic import BaseModel, Field, PrivateAttr

# Import SentenceTransformer for production-grade embeddings.
from sentence_transformers import SentenceTransformer

# Import the Flock logger.
from flock.core.logging.logging import get_logger

tracer = trace.get_tracer(__name__)
logger = get_logger("memory")


class MemoryScope(Enum):
    LOCAL = "local"
    GLOBAL = "global"
    BOTH = "both"


class MemoryOperation(BaseModel):
    """Base class for memory operations."""

    type: str
    scope: MemoryScope = MemoryScope.BOTH


class CombineOperation(MemoryOperation):
    """Combine results from multiple operations using weighted scoring."""

    type: Literal["combine"] = "combine"
    weights: dict[str, float] = Field(
        default_factory=lambda: {"semantic": 0.7, "exact": 0.3}
    )


class SemanticOperation(MemoryOperation):
    """Semantic search operation."""

    type: Literal["semantic"] = "semantic"
    threshold: float = 0.5
    max_results: int = 10
    recency_filter: str | None = None  # e.g., "7d", "24h"


class ExactOperation(MemoryOperation):
    """Exact matching operation."""

    type: Literal["exact"] = "exact"
    keys: list[str] = Field(default_factory=list)


class ChunkOperation(MemoryOperation):
    """Operation for handling chunked entries."""

    type: Literal["chunk"] = "chunk"
    reconstruct: bool = True


class EnrichOperation(MemoryOperation):
    """Enrich memory with tool results."""

    type: Literal["enrich"] = "enrich"
    tools: list[str]
    strategy: Literal["comprehensive", "quick", "validated"] = "comprehensive"


class FilterOperation(MemoryOperation):
    """Filter memory results."""

    type: Literal["filter"] = "filter"
    recency: str | None = None
    relevance: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SortOperation(MemoryOperation):
    """Sort memory results."""

    type: Literal["sort"] = "sort"
    by: Literal["relevance", "recency", "access_count"] = "relevance"
    ascending: bool = False


class MemoryEntry(BaseModel):
    """A single memory entry."""

    id: str
    content: str
    embedding: list[float] | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
    access_count: int = Field(default=0)
    concepts: set[str] = Field(default_factory=set)
    decay_factor: float = Field(default=1.0)


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
        """Initialize the MemoryGraph with a NetworkX graph from JSON data."""
        super().__init__(**data)
        try:
            data_graph = json.loads(self.graph_json)
            self._graph = json_graph.node_link_graph(data_graph, edges="links")
            logger.debug(
                f"MemoryGraph initialized from JSON with {len(self._graph.nodes())} nodes."
            )
        except Exception as e:
            logger.error(f"Failed to load MemoryGraph from JSON: {e}")
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
        logger.debug("MemoryGraph JSON updated.")

    def add_concepts(self, concepts: set[str]) -> None:
        """Add a set of concepts to the graph and update their associations."""
        concept_list = list(concepts)
        logger.debug(f"Adding concepts: {concept_list}")
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
        logger.debug(f"Spreading activation from concepts: {initial_concepts}")
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

        logger.debug(f"Activation levels: {activated}")
        return activated

    def save_as_image(self, filename: str = "memory_graph.png") -> None:
        """Visualize the concept graph and save it as a PNG image with improved readability.

        This method uses matplotlib to create a clear and readable visualization by:
        - Using a larger figure size
        - Implementing better node spacing
        - Adding adjustable text labels
        - Using a more visually appealing color scheme
        - Adding edge weight visualization

        Args:
            filename: The path (including .png) where the image will be saved.
        """
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        logger.info(f"Saving MemoryGraph visualization to '{filename}'")

        if self._graph.number_of_nodes() == 0:
            logger.warning("MemoryGraph is empty; skipping image creation.")
            return

        try:
            # Create a larger figure with higher DPI
            plt.figure(figsize=(16, 12), dpi=100)

            # Use Kamada-Kawai layout for better node distribution
            pos = nx.kamada_kawai_layout(self._graph)

            # Calculate node sizes based on degree
            node_degrees = dict(self._graph.degree())
            node_sizes = [
                2000 * (1 + node_degrees[node] * 0.2)
                for node in self._graph.nodes()
            ]

            # Calculate edge weights for width and transparency
            edge_weights = [
                d["weight"] for (u, v, d) in self._graph.edges(data=True)
            ]
            max_weight = max(edge_weights) if edge_weights else 1
            edge_widths = [1 + (w / max_weight) * 3 for w in edge_weights]
            edge_alphas = [0.2 + (w / max_weight) * 0.8 for w in edge_weights]

            # Draw the network with custom styling
            # Nodes
            nx.draw_networkx_nodes(
                self._graph,
                pos,
                node_size=node_sizes,
                node_color="#5fa4d4",  # Lighter blue
                alpha=0.7,
                edgecolors="white",
            )

            # Edges with varying width and transparency
            for (u, v, d), width, alpha in zip(
                self._graph.edges(data=True), edge_widths, edge_alphas
            ):
                nx.draw_networkx_edges(
                    self._graph,
                    pos,
                    edgelist=[(u, v)],
                    width=width,
                    alpha=alpha,
                    edge_color="#2c3e50",  # Darker blue-grey
                )

            # Add labels with better positioning and background
            labels = nx.get_node_attributes(self._graph, "name") or {
                node: node for node in self._graph.nodes()
            }
            label_pos = {
                node: (x, y + 0.02) for node, (x, y) in pos.items()
            }  # Slightly offset labels

            # Draw labels with white background for better readability
            for node, (x, y) in label_pos.items():
                plt.text(
                    x,
                    y,
                    labels[node],
                    horizontalalignment="center",
                    verticalalignment="center",
                    fontsize=8,
                    fontweight="bold",
                    bbox=dict(
                        facecolor="white", edgecolor="none", alpha=0.7, pad=2.0
                    ),
                )

            # Add edge weight labels for significant weights
            edge_labels = nx.get_edge_attributes(self._graph, "weight")
            significant_edges = {
                (u, v): w
                for (u, v), w in edge_labels.items()
                if w > max_weight * 0.3
            }
            if significant_edges:
                nx.draw_networkx_edge_labels(
                    self._graph,
                    pos,
                    edge_labels=significant_edges,
                    font_size=6,
                    bbox=dict(facecolor="white", edgecolor="none", alpha=0.7),
                )

            # Improve layout
            plt.title("Memory Concept Graph", fontsize=16, pad=20)
            plt.axis("off")

            # Add padding and save
            plt.tight_layout(pad=2.0)
            plt.savefig(filename, bbox_inches="tight", facecolor="white")
            plt.close()

            logger.info(f"MemoryGraph image saved successfully to '{filename}'")

        except Exception as e:
            logger.error(f"Failed to save MemoryGraph image: {e}")
            plt.close()


class FlockMemoryStore(BaseModel):
    """Enhanced Flock memory storage with short-term and long-term memory.

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

    @classmethod
    def load_from_file(cls, file_path: str | None = None) -> "FlockMemoryStore":
        """Load a memory store from a JSON file.

        Args:
            file_path: Path to the JSON file containing the serialized memory store.
                      If None, returns an empty memory store.

        Returns:
            FlockMemoryStore: A new memory store instance with loaded data.

        Raises:
            FileNotFoundError: If the specified file doesn't exist
            JSONDecodeError: If the file contains invalid JSON
            ValueError: If the JSON structure is invalid
        """
        if file_path is None:
            logger.debug("No file path provided, creating new memory store")
            return cls()

        try:
            logger.info(f"Loading memory store from {file_path}")
            with open(file_path) as f:
                data = json.load(f)

            # Initialize a new store
            store = cls()

            # Load short-term memory entries
            store.short_term = [
                MemoryEntry(
                    id=entry["id"],
                    content=entry["content"],
                    embedding=entry.get("embedding"),
                    timestamp=datetime.fromisoformat(entry["timestamp"]),
                    access_count=entry.get("access_count", 0),
                    concepts=set(entry.get("concepts", [])),
                    decay_factor=entry.get("decay_factor", 1.0),
                )
                for entry in data.get("short_term", [])
            ]

            # Load long-term memory entries
            store.long_term = [
                MemoryEntry(
                    id=entry["id"],
                    content=entry["content"],
                    embedding=entry.get("embedding"),
                    timestamp=datetime.fromisoformat(entry["timestamp"]),
                    access_count=entry.get("access_count", 0),
                    concepts=set(entry.get("concepts", [])),
                    decay_factor=entry.get("decay_factor", 1.0),
                )
                for entry in data.get("long_term", [])
            ]

            # Load concept graph
            if "concept_graph" in data:
                graph_data = json.loads(data["concept_graph"]["graph_json"])
                store.concept_graph = MemoryGraph(
                    graph_json=json.dumps(graph_data)
                )

            # Load clusters
            if "clusters" in data:
                store.clusters = {
                    int(k): [
                        MemoryEntry(
                            id=entry["id"],
                            content=entry["content"],
                            embedding=entry.get("embedding"),
                            timestamp=datetime.fromisoformat(
                                entry["timestamp"]
                            ),
                            access_count=entry.get("access_count", 0),
                            concepts=set(entry.get("concepts", [])),
                            decay_factor=entry.get("decay_factor", 1.0),
                        )
                        for entry in v
                    ]
                    for k, v in data["clusters"].items()
                }

            # Load cluster centroids
            if "cluster_centroids" in data:
                store.cluster_centroids = {
                    int(k): v for k, v in data["cluster_centroids"].items()
                }

            # Initialize the embedding model
            store._embedding_model = None  # Will be lazy-loaded when needed

            logger.info(
                f"Successfully loaded memory store with "
                f"{len(store.short_term)} short-term and "
                f"{len(store.long_term)} long-term entries"
            )
            return store

        except FileNotFoundError:
            logger.warning(
                f"Memory file {file_path} not found, creating new store"
            )
            return cls()
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in memory file: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading memory store: {e}")
            raise ValueError(f"Failed to load memory store: {e}")

    @classmethod
    def merge_stores(
        cls, stores: list["FlockMemoryStore"]
    ) -> "FlockMemoryStore":
        """Merge multiple memory stores into a single store.

        Args:
            stores: List of FlockMemoryStore instances to merge

        Returns:
            FlockMemoryStore: A new memory store containing merged data
        """
        merged = cls()

        # Merge short-term and long-term memories
        for store in stores:
            merged.short_term.extend(store.short_term)
            merged.long_term.extend(store.long_term)

        # Merge concept graphs
        merged_graph = nx.Graph()
        for store in stores:
            if store.concept_graph and store.concept_graph.graph:
                merged_graph = nx.compose(
                    merged_graph, store.concept_graph.graph
                )

        merged.concept_graph = MemoryGraph(
            graph_json=json.dumps(
                nx.node_link_data(merged_graph, edges="links")
            )
        )

        # Recompute clusters for the merged data
        if merged.short_term:
            merged._update_clusters()

        return merged

    def get_embedding_model(self) -> SentenceTransformer:
        """Initialize and return the SentenceTransformer model.

        Uses "all-MiniLM-L6-v2" as the default model.
        """
        if self._embedding_model is None:
            try:
                logger.debug(
                    "Loading SentenceTransformer model 'all-MiniLM-L6-v2'."
                )
                self._embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                raise RuntimeError(f"Failed to load embedding model: {e}")
        return self._embedding_model

    def compute_embedding(self, text: str) -> np.ndarray:
        """Compute and return the embedding for the provided text as a NumPy array."""
        logger.debug(
            f"Computing embedding for text: {text[:100].replace('{', '{{').replace('}', '}}')}..."
        )  # Log first 30 chars for brevity.
        model = self.get_embedding_model()
        try:
            embedding = model.encode(text, convert_to_numpy=True)
            return embedding
        except Exception as e:
            logger.error(f"Error computing embedding: {e}")
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
            logger.error(f"Error computing similarity: {e}")
            raise RuntimeError(f"Error computing similarity: {e}")

    def exact_match(self, inputs: dict[str, Any]) -> list[MemoryEntry]:
        """Perform an exact key-based lookup in short-term memory.

        Returns entries where all provided key-value pairs exist in the entry's inputs.
        """
        logger.debug(f"Performing exact match lookup with inputs: {inputs}")
        matches = []
        for entry in self.short_term:
            if all(item in entry.inputs.items() for item in inputs.items()):
                matches.append(entry)
        logger.debug(f"Exact match found {len(matches)} entries.")
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
        logger.debug(
            f"Combining results for inputs: {inputs} with weights: {weights}"
        )
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
        logger.debug(f"Combined results count: {len(results)}")
        return {"combined_results": [entry for score, entry in results]}

    def add_entry(self, entry: MemoryEntry) -> None:
        """Add a new memory entry to short-term memory, update the concept graph and clusters.

        and check for promotion to long-term memory.
        """
        with tracer.start_as_current_span("memory.add_entry") as span:
            logger.info(f"Adding memory entry with id: {entry.id}")
            span.set_attribute("entry.id", entry.id)
            self.short_term.append(entry)
            self.concept_graph.add_concepts(entry.concepts)
            self._update_clusters()
            if entry.access_count > 10:
                self._promote_to_long_term(entry)

    def _promote_to_long_term(self, entry: MemoryEntry) -> None:
        """Promote an entry to long-term memory."""
        logger.info(f"Promoting entry {entry.id} to long-term memory.")
        if entry not in self.long_term:
            self.long_term.append(entry)

    def retrieve(
        self,
        query_embedding: np.ndarray,
        query_concepts: set[str],
        similarity_threshold: float = 0.8,
        exclude_last_n: int = 0,
    ) -> list[MemoryEntry]:
        """Retrieve memory entries using semantic similarity and concept-based activation."""
        with tracer.start_as_current_span("memory.retrieve") as span:
            logger.debug("Retrieving memory entries...")
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

                # Calculate base similarity
                entry_embedding = np.array(entry.embedding)
                norm_entry = entry_embedding / (
                    np.linalg.norm(entry_embedding) + 1e-8
                )
                similarity = float(np.dot(norm_query, norm_entry))

                # Calculate modifiers
                time_diff = (current_time - entry.timestamp).total_seconds()
                decay = np.exp(-decay_rate * time_diff)
                # Add 1 to base score so new entries aren't zeroed out
                reinforcement = 1.0 + np.log1p(entry.access_count)

                # Calculate final score
                final_score = (
                    similarity * decay * reinforcement * entry.decay_factor
                )

                span.add_event(
                    "memory score",
                    attributes={
                        "entry_id": entry.id,
                        "similarity": similarity,
                        "final_score": final_score,
                    },
                )

                # If base similarity passes threshold, include in results
                if similarity >= similarity_threshold:
                    results.append((final_score, entry))

            # Update access counts and decay for retrieved entries
            for _, entry in results:
                entry.access_count += 1
                self._update_decay_factors(entry)

            # Sort by final score
            results.sort(key=lambda x: x[0], reverse=True)
            logger.debug(f"Retrieved {len(results)} memory entries.")
            return [entry for score, entry in results]

    def _update_decay_factors(self, retrieved_entry: MemoryEntry) -> None:
        """Update decay factors: increase for the retrieved entry and decrease for others."""
        logger.debug(f"Updating decay factor for entry {retrieved_entry.id}")
        retrieved_entry.decay_factor *= 1.1
        for entry in self.short_term:
            if entry != retrieved_entry:
                entry.decay_factor *= 0.9

    def _update_clusters(self) -> None:
        """Update memory clusters using k-means clustering on entry embeddings."""
        logger.debug("Updating memory clusters...")
        if len(self.short_term) < 2:
            logger.debug("Not enough entries for clustering.")
            return

        valid_entries = [
            entry for entry in self.short_term if entry.embedding is not None
        ]
        if not valid_entries:
            logger.debug(
                "No valid entries with embeddings found for clustering."
            )
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
        logger.debug(f"Clustering complete with {n_clusters} clusters.")

"""Enhanced Memory module implementation with hierarchical concept representation for Flock agents."""

import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Set, Tuple, Union

import networkx as nx
import numpy as np
from networkx.readwrite import json_graph
from opentelemetry import trace
from pydantic import BaseModel, Field, PrivateAttr
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from flock.core import FlockAgent, FlockModule, FlockModuleConfig
from flock.core.logging.logging import get_logger
from flock.modules.memory.memory_parser import MemoryMappingParser

tracer = trace.get_tracer(__name__)
logger = get_logger("memory")


class ConceptRelationType(str, Enum):
    """Types of relationships between concepts."""
    
    ASSOCIATION = "association"  # Generic association (original type)
    IS_A = "is_a"                # Hierarchical relationship (child -> parent)
    HAS_A = "has_a"              # Compositional relationship
    INSTANCE_OF = "instance_of"  # Instance relationship
    PART_OF = "part_of"          # Part-whole relationship


class MemoryScope(Enum):
    """Scope for memory operations."""
    
    LOCAL = "local"
    GLOBAL = "global"
    BOTH = "both"


class MemoryOperation(BaseModel):
    """Base class for memory operations."""

    type: str
    scope: MemoryScope = MemoryScope.BOTH


class MemoryModuleConfig(FlockModuleConfig):
    """Configuration for the MemoryModule with hierarchical concepts support."""

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
    enable_hierarchical_concepts: bool = Field(
        default=True, description="Whether to enable hierarchical concept representation"
    )
    hierarchical_activation_boost: float = Field(
        default=1.5, 
        description="Boost factor for activation when following hierarchical relationships"
    )
    upward_propagation_factor: float = Field(
        default=0.8,
        description="How much activation propagates upward in the hierarchy"
    )
    downward_propagation_factor: float = Field(
        default=0.6,
        description="How much activation propagates downward in the hierarchy"
    )


class MemoryEntry(BaseModel):
    """A single memory entry."""

    id: str
    content: str
    embedding: list[float] | None = None
    timestamp: datetime = Field(default_factory=datetime.now)
    access_count: int = Field(default=0)
    concepts: set[str] = Field(default_factory=set)
    decay_factor: float = Field(default=1.0)


class ConceptRelation(BaseModel):
    """Represents a typed relationship between concepts."""
    
    source: str
    target: str
    relation_type: ConceptRelationType = ConceptRelationType.ASSOCIATION
    weight: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HierarchicalMemoryGraph(BaseModel):
    """Enhanced graph representation of concept relationships with hierarchy support.
    
    The graph is stored as a JSON string for serialization, while a private attribute 
    holds the actual NetworkX graph. This version supports typed edges for hierarchical
    relationships.
    """

    # JSON representation using the node-link format with explicit edges="links" to avoid warnings.
    graph_json: str = Field(
        default_factory=lambda: json.dumps(
            json_graph.node_link_data(nx.MultiDiGraph(), edges="links")
        )
    )
    # Private attribute for the actual NetworkX graph - now using MultiDiGraph for multiple edge types
    _graph: nx.MultiDiGraph = PrivateAttr()

    def __init__(self, **data):
        """Initialize the HierarchicalMemoryGraph with a NetworkX MultiDiGraph from JSON data."""
        super().__init__(**data)
        try:
            data_graph = json.loads(self.graph_json)
            self._graph = json_graph.node_link_graph(data_graph, edges="links", multigraph=True)
            logger.debug(
                f"HierarchicalMemoryGraph initialized from JSON with {len(self._graph.nodes())} nodes."
            )
        except Exception as e:
            logger.error(f"Failed to load HierarchicalMemoryGraph from JSON: {e}")
            self._graph = nx.MultiDiGraph()

    @property
    def graph(self) -> nx.MultiDiGraph:
        """Provides access to the internal NetworkX graph."""
        return self._graph

    def update_graph_json(self) -> None:
        """Update the JSON representation based on the current state of the graph."""
        self.graph_json = json.dumps(
            json_graph.node_link_data(self._graph, edges="links")
        )
        logger.debug("HierarchicalMemoryGraph JSON updated.")

    def add_concepts(self, concepts: set[str]) -> None:
        """Add a set of concepts to the graph and update their associations."""
        concept_list = list(concepts)
        logger.debug(f"Adding concepts: {concept_list}")
        for concept in concepts:
            self._graph.add_node(concept)
        for c1 in concepts:
            for c2 in concepts:
                if c1 != c2:
                    # Check if there's already an association edge
                    if self._graph.has_edge(c1, c2, key=ConceptRelationType.ASSOCIATION):
                        # Increase weight of existing association
                        self._graph[c1][c2][ConceptRelationType.ASSOCIATION]["weight"] += 1
                    else:
                        # Add new association with default type
                        self._graph.add_edge(
                            c1, c2, 
                            key=ConceptRelationType.ASSOCIATION,
                            weight=1, 
                            relation_type=ConceptRelationType.ASSOCIATION
                        )
        self.update_graph_json()

    def add_hierarchical_relation(
        self, 
        child_concept: str, 
        parent_concept: str, 
        relation_type: ConceptRelationType = ConceptRelationType.IS_A,
        weight: float = 1.0,
        metadata: Dict[str, Any] = None
    ) -> None:
        """Add a hierarchical relationship between concepts.
        
        Args:
            child_concept: The more specific/child concept
            parent_concept: The more general/parent concept
            relation_type: Type of hierarchical relationship
            weight: Initial weight of the relationship
            metadata: Additional information about the relationship
        """
        # Ensure both concepts exist
        if child_concept not in self._graph:
            self._graph.add_node(child_concept)
        if parent_concept not in self._graph:
            self._graph.add_node(parent_concept)
            
        # Add the hierarchical edge with the appropriate type
        if not self._graph.has_edge(child_concept, parent_concept, key=relation_type):
            self._graph.add_edge(
                child_concept, 
                parent_concept, 
                key=relation_type,
                weight=weight, 
                relation_type=relation_type,
                metadata=metadata or {}
            )
            logger.debug(f"Added {relation_type} relationship: {child_concept} -> {parent_concept}")
        else:
            # Update weight if relationship already exists
            curr_weight = self._graph[child_concept][parent_concept][relation_type]["weight"]
            self._graph[child_concept][parent_concept][relation_type]["weight"] = curr_weight + weight
            logger.debug(f"Updated {relation_type} relationship: {child_concept} -> {parent_concept}")
            
        self.update_graph_json()

    def get_parents(self, concept: str, relation_type: ConceptRelationType = ConceptRelationType.IS_A) -> List[str]:
        """Get parent concepts for a given concept.
        
        Args:
            concept: The concept to find parents for
            relation_type: Type of hierarchical relationship to follow
            
        Returns:
            List of parent concept names
        """
        if concept not in self._graph:
            return []
            
        parents = []
        for _, parent, key, data in self._graph.out_edges(concept, keys=True, data=True):
            if key == relation_type:
                parents.append(parent)
                
        return parents
        
    def get_children(self, concept: str, relation_type: ConceptRelationType = ConceptRelationType.IS_A) -> List[str]:
        """Get child concepts for a given concept.
        
        Args:
            concept: The concept to find children for
            relation_type: Type of hierarchical relationship to follow
            
        Returns:
            List of child concept names
        """
        if concept not in self._graph:
            return []
            
        children = []
        for child, _, key, data in self._graph.in_edges(concept, keys=True, data=True):
            if key == relation_type:
                children.append(child)
                
        return children

    def get_ancestors(self, concept: str, relation_type: ConceptRelationType = ConceptRelationType.IS_A) -> List[str]:
        """Get all ancestor concepts by following hierarchical relationships transitively.
        
        Args:
            concept: The starting concept
            relation_type: Type of hierarchical relationship to follow
            
        Returns:
            List of ancestor concepts (parents, grandparents, etc.)
        """
        if concept not in self._graph:
            return []
            
        ancestors = []
        visited = set()
        queue = [concept]
        
        # Skip the starting concept itself
        visited.add(concept)
        
        while queue:
            current = queue.pop(0)
            parents = self.get_parents(current, relation_type)
            
            for parent in parents:
                if parent not in visited:
                    ancestors.append(parent)
                    visited.add(parent)
                    queue.append(parent)
                    
        return ancestors

    def get_descendants(self, concept: str, relation_type: ConceptRelationType = ConceptRelationType.IS_A) -> List[str]:
        """Get all descendant concepts by following hierarchical relationships transitively.
        
        Args:
            concept: The starting concept
            relation_type: Type of hierarchical relationship to follow
            
        Returns:
            List of descendant concepts (children, grandchildren, etc.)
        """
        if concept not in self._graph:
            return []
            
        descendants = []
        visited = set()
        queue = [concept]
        
        # Skip the starting concept itself
        visited.add(concept)
        
        while queue:
            current = queue.pop(0)
            children = self.get_children(current, relation_type)
            
            for child in children:
                if child not in visited:
                    descendants.append(child)
                    visited.add(child)
                    queue.append(child)
                    
        return descendants

    def hierarchical_spread_activation(
        self, 
        initial_concepts: set[str], 
        decay_factor: float = 0.5,
        upward_factor: float = 0.8,
        downward_factor: float = 0.6,
        max_depth: int = 3
    ) -> dict[str, float]:
        """Spread activation through the concept graph with special handling for hierarchical relationships.
        
        Args:
            initial_concepts: The starting set of concepts
            decay_factor: How much the activation decays at each step
            upward_factor: How much activation flows upward in hierarchies
            downward_factor: How much activation flows downward in hierarchies
            max_depth: Maximum depth of activation spread to prevent explosion
            
        Returns:
            A dictionary mapping each concept to its activation level
        """
        logger.debug(f"Hierarchical spreading activation from concepts: {initial_concepts}")
        activated = {concept: 1.0 for concept in initial_concepts}
        frontier = [(concept, 0) for concept in initial_concepts]  # (concept, depth)
        
        processed = set()  # Track processed nodes to avoid cycles

        while frontier:
            current, depth = frontier.pop(0)
            
            if current in processed or depth >= max_depth:
                continue
                
            processed.add(current)
            current_activation = activated.get(current, 0.0)
            
            # Process outgoing edges - these include both associations and hierarchical edges
            for _, neighbor, key, edge_data in self._graph.out_edges(current, keys=True, data=True):
                relation_type = edge_data.get('relation_type', ConceptRelationType.ASSOCIATION)
                weight = edge_data.get('weight', 1.0)
                
                # Determine propagation factor based on edge type
                if relation_type == ConceptRelationType.ASSOCIATION:
                    prop_factor = decay_factor
                elif relation_type in (ConceptRelationType.IS_A, ConceptRelationType.PART_OF, ConceptRelationType.INSTANCE_OF):
                    # These are upward hierarchical relationships
                    prop_factor = decay_factor * upward_factor
                else:
                    # Other relationships like HAS_A flow downward
                    prop_factor = decay_factor * downward_factor
                
                new_activation = current_activation * prop_factor * weight
                
                # Update activation if higher
                if neighbor not in activated or activated[neighbor] < new_activation:
                    activated[neighbor] = new_activation
                    frontier.append((neighbor, depth + 1))
            
            # Also process incoming edges for downward activation (from parents to children)
            for source, _, key, edge_data in self._graph.in_edges(current, keys=True, data=True):
                relation_type = edge_data.get('relation_type', ConceptRelationType.ASSOCIATION)
                weight = edge_data.get('weight', 1.0)
                
                # Only propagate for hierarchical relationships
                if relation_type in (ConceptRelationType.IS_A, ConceptRelationType.PART_OF, ConceptRelationType.INSTANCE_OF):
                    # These are downward when traversing incoming edges (parent -> child)
                    prop_factor = decay_factor * downward_factor
                    
                    new_activation = current_activation * prop_factor * weight
                    
                    if source not in activated or activated[source] < new_activation:
                        activated[source] = new_activation
                        frontier.append((source, depth + 1))

        logger.debug(f"Hierarchical activation levels: {activated}")
        return activated

    def spread_activation(
        self, initial_concepts: set[str], decay_factor: float = 0.5
    ) -> dict[str, float]:
        """Original spread activation method for backward compatibility.
        
        This just calls hierarchical_spread_activation with default parameters.
        """
        return self.hierarchical_spread_activation(
            initial_concepts, 
            decay_factor=decay_factor
        )

    def save_as_image(self, filename: str = "memory_graph.png") -> None:
        """Visualize the concept graph and save it as a PNG image with improved readability.
        
        This enhanced version adds visual differentiation for hierarchical relationships.
        """
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import FancyArrowPatch

        logger.info(f"Saving HierarchicalMemoryGraph visualization to '{filename}'")

        if self._graph.number_of_nodes() == 0:
            logger.warning("HierarchicalMemoryGraph is empty; skipping image creation.")
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

            # Draw nodes
            nx.draw_networkx_nodes(
                self._graph,
                pos,
                node_size=node_sizes,
                node_color="#5fa4d4",  # Lighter blue
                alpha=0.7,
                edgecolors="white",
            )
            
            # Draw association edges (original style)
            association_edges = []
            is_a_edges = []
            has_a_edges = []
            other_hier_edges = []
            
            # Collect edges by type
            for u, v, k, data in self._graph.edges(keys=True, data=True):
                relation_type = data.get('relation_type', ConceptRelationType.ASSOCIATION)
                if relation_type == ConceptRelationType.ASSOCIATION:
                    association_edges.append((u, v, data))
                elif relation_type == ConceptRelationType.IS_A:
                    is_a_edges.append((u, v, data))
                elif relation_type == ConceptRelationType.HAS_A:
                    has_a_edges.append((u, v, data))
                else:
                    other_hier_edges.append((u, v, data))
                    
            # Draw each edge type with different style
            # Association edges - standard style
            for u, v, data in association_edges:
                weight = data.get('weight', 1.0)
                width = 1 + (weight / 5) * 3
                alpha = 0.2 + (weight / 5) * 0.8
                nx.draw_networkx_edges(
                    self._graph,
                    pos,
                    edgelist=[(u, v)],
                    width=width,
                    alpha=alpha,
                    edge_color="#2c3e50",  # Darker blue-grey
                )
                # Add weight label
                if weight > 1:
                    edge_label = {(u, v): f"{weight:.0f}"}
                    nx.draw_networkx_edge_labels(
                        self._graph,
                        pos,
                        edge_labels=edge_label,
                        font_size=8,
                        bbox=dict(facecolor="white", edgecolor="none", alpha=0.7),
                    )
            
            # IS-A relationships - green with arrow
            for u, v, data in is_a_edges:
                weight = data.get('weight', 1.0)
                width = 1 + (weight / 5) * 3
                alpha = 0.2 + (weight / 5) * 0.8
                # Draw an arrow edge
                ax = plt.gca()
                arrow = FancyArrowPatch(
                    pos[u], 
                    pos[v],
                    connectionstyle="arc3,rad=0.1",
                    arrowstyle="-|>",
                    mutation_scale=20,
                    lw=width,
                    alpha=alpha,
                    color="#2e8540",  # Green
                )
                ax.add_patch(arrow)
                # Add IS-A label
                midpoint = ((pos[u][0] + pos[v][0])/2, (pos[u][1] + pos[v][1])/2)
                plt.text(
                    midpoint[0], midpoint[1], 
                    "IS-A", 
                    fontsize=7,
                    bbox=dict(facecolor="white", edgecolor="none", alpha=0.7, pad=1),
                    ha='center', va='center'
                )
                
            # HAS-A relationships - blue with arrow
            for u, v, data in has_a_edges:
                weight = data.get('weight', 1.0)
                width = 1 + (weight / 5) * 3
                alpha = 0.2 + (weight / 5) * 0.8
                # Draw an arrow edge
                ax = plt.gca()
                arrow = FancyArrowPatch(
                    pos[u], 
                    pos[v],
                    connectionstyle="arc3,rad=-0.1",
                    arrowstyle="-|>",
                    mutation_scale=20,
                    lw=width,
                    alpha=alpha,
                    color="#1E88E5",  # Blue
                )
                ax.add_patch(arrow)
                # Add HAS-A label
                midpoint = ((pos[u][0] + pos[v][0])/2, (pos[u][1] + pos[v][1])/2)
                plt.text(
                    midpoint[0], midpoint[1], 
                    "HAS-A", 
                    fontsize=7,
                    bbox=dict(facecolor="white", edgecolor="none", alpha=0.7, pad=1),
                    ha='center', va='center'
                )
                
            # Other hierarchical relationships - purple with arrow
            for u, v, data in other_hier_edges:
                weight = data.get('weight', 1.0)
                width = 1 + (weight / 5) * 3
                alpha = 0.2 + (weight / 5) * 0.8
                relation_type = data.get('relation_type', 'UNKNOWN')
                # Draw an arrow edge
                ax = plt.gca()
                arrow = FancyArrowPatch(
                    pos[u], 
                    pos[v],
                    connectionstyle="arc3,rad=0.15",
                    arrowstyle="-|>",
                    mutation_scale=20,
                    lw=width,
                    alpha=alpha,
                    color="#9C27B0",  # Purple
                )
                ax.add_patch(arrow)
                # Add type label
                midpoint = ((pos[u][0] + pos[v][0])/2, (pos[u][1] + pos[v][1])/2)
                plt.text(
                    midpoint[0], midpoint[1], 
                    str(relation_type).split('.')[-1], 
                    fontsize=7,
                    bbox=dict(facecolor="white", edgecolor="none", alpha=0.7, pad=1),
                    ha='center', va='center'
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

            # Improve layout
            plt.title("Hierarchical Memory Concept Graph", fontsize=16, pad=20)
            plt.axis("off")

            # Add legend for relationship types
            plt.plot([], [], '-', color="#2c3e50", label='Association')
            plt.plot([], [], '-', color="#2e8540", label='IS-A')
            plt.plot([], [], '-', color="#1E88E5", label='HAS-A')
            plt.plot([], [], '-', color="#9C27B0", label='Other Hierarchical')
            plt.legend(loc='upper right', frameon=True, framealpha=0.9)

            # Add padding and save
            plt.tight_layout(pad=2.0)
            plt.savefig(filename, bbox_inches="tight", facecolor="white")
            plt.close()

            logger.info(f"HierarchicalMemoryGraph image saved successfully to '{filename}'")

        except Exception as e:
            logger.error(f"Failed to save HierarchicalMemoryGraph image: {e}")
            plt.close()


class HierarchicalFlockMemoryStore(BaseModel):
    """Enhanced Flock memory storage with hierarchical concept representation.

    This extends the original FlockMemoryStore with support for hierarchical concepts,
    improved semantic search, and concept-based taxonomies.
    """

    short_term: list[MemoryEntry] = Field(default_factory=list)
    long_term: list[MemoryEntry] = Field(default_factory=list)
    concept_graph: HierarchicalMemoryGraph = Field(default_factory=HierarchicalMemoryGraph)
    clusters: dict[int, list[MemoryEntry]] = Field(default_factory=dict)
    # Instead of np.ndarray, store centroids as lists of floats
    cluster_centroids: dict[int, list[float]] = Field(default_factory=dict)
    # The embedding model is stored as a private attribute, as it's not serializable
    _embedding_model: SentenceTransformer | None = PrivateAttr(default=None)

    @classmethod
    def load_from_file(cls, file_path: str | None = None) -> "HierarchicalFlockMemoryStore":
        """Load a memory store from a JSON file.

        Args:
            file_path: Path to the JSON file containing the serialized memory store.
                      If None, returns an empty memory store.

        Returns:
            HierarchicalFlockMemoryStore: A new memory store instance with loaded data.

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

            # Load concept graph - now as HierarchicalMemoryGraph
            if "concept_graph" in data:
                graph_data = json.loads(data["concept_graph"]["graph_json"])
                store.concept_graph = HierarchicalMemoryGraph(
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
        )  # Log first 100 chars for brevity
        model = self.get_embedding_model()
        try:
            embedding = model.encode(text, convert_to_numpy=True)
            return embedding
        except Exception as e:
            logger.error(f"Error computing embedding: {e}")
            raise RuntimeError(f"Error computing embedding: {e}")

    def add_hierarchical_concept(
        self, 
        child_concept: str, 
        parent_concept: str, 
        relation_type: ConceptRelationType = ConceptRelationType.IS_A,
        weight: float = 1.0,
        metadata: Dict[str, Any] = None
    ) -> None:
        """Add a hierarchical relationship between concepts.
        
        Args:
            child_concept: The more specific/child concept
            parent_concept: The more general/parent concept
            relation_type: Type of hierarchical relationship
            weight: Initial weight of the relationship
            metadata: Additional information about the relationship
        """
        self.concept_graph.add_hierarchical_relation(
            child_concept=child_concept,
            parent_concept=parent_concept,
            relation_type=relation_type,
            weight=weight,
            metadata=metadata or {}
        )

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
        input_items = set(inputs.items())
        
        for entry in self.short_term:
            # Extract key-value pairs from entry content
            try:
                entry_data = json.loads(entry.content)
                if isinstance(entry_data, dict) and all(k in entry_data and entry_data[k] == v for k, v in inputs.items()):
                    matches.append(entry)
            except json.JSONDecodeError:
                # If entry content isn't JSON, check if it contains all input strings
                if all(f"{k}.*?{v}" in entry.content for k, v in inputs.items()):
                    matches.append(entry)
                    
        logger.debug(f"Exact match found {len(matches)} entries.")
        return matches

    def retrieve(
        self,
        query_embedding: np.ndarray,
        query_concepts: set[str],
        similarity_threshold: float = 0.8,
        exclude_last_n: int = 0,
        use_hierarchical: bool = True,
        upward_factor: float = 0.8,
        downward_factor: float = 0.6,
    ) -> list[MemoryEntry]:
        """Retrieve memory entries using semantic similarity and concept-based activation.
        
        This enhanced version supports hierarchical concept relationships.

        Args:
            query_embedding: The embedding vector of the query
            query_concepts: Set of concepts in the query
            similarity_threshold: Minimum similarity score to include an entry
            exclude_last_n: Number of most recent entries to exclude
            use_hierarchical: Whether to use hierarchical spread activation
            upward_factor: Factor for upward hierarchical propagation
            downward_factor: Factor for downward hierarchical propagation
            
        Returns:
            List of relevant memory entries sorted by relevance
        """
        with tracer.start_as_current_span("memory.retrieve") as span:
            logger.debug("Retrieving memory entries with hierarchical support...")
            results = []
            current_time = datetime.now()
            decay_rate = 0.0001
            norm_query = query_embedding / (
                np.linalg.norm(query_embedding) + 1e-8
            )

            # Get entries, excluding the most recent n if specified
            entries = (
                self.short_term[:-exclude_last_n]
                if exclude_last_n > 0
                else self.short_term
            )
            
            # Use hierarchical spread activation if enabled
            if use_hierarchical and query_concepts:
                if len(query_concepts) > 0:
                    concept_activations = self.concept_graph.hierarchical_spread_activation(
                        query_concepts,
                        decay_factor=0.5,
                        upward_factor=upward_factor,
                        downward_factor=downward_factor
                    )
                else:
                    concept_activations = {}
            else:
                # Fall back to traditional spread activation
                concept_activations = self.concept_graph.spread_activation(
                    query_concepts, decay_factor=0.5
                ) if query_concepts else {}

            for entry in entries:
                if entry.embedding is None:
                    continue

                # Calculate base similarity
                entry_embedding = np.array(entry.embedding)
                norm_entry = entry_embedding / (
                    np.linalg.norm(entry_embedding) + 1e-8
                )
                similarity = float(np.dot(norm_query, norm_entry))

                # Calculate time decay
                time_diff = (current_time - entry.timestamp).total_seconds()
                decay = np.exp(-decay_rate * time_diff)
                
                # Add 1 to base score so new entries aren't zeroed out
                reinforcement = 1.0 + np.log1p(entry.access_count)
                
                # Calculate concept activation boost
                concept_boost = 1.0
                if entry.concepts and concept_activations:
                    # Sum activations of all concepts in the entry
                    entry_activation = sum(
                        concept_activations.get(concept, 0.0) 
                        for concept in entry.concepts
                    )
                    # Apply a boost based on concept activation
                    if entry_activation > 0:
                        concept_boost = 1.0 + np.log1p(entry_activation)

                # Calculate final score with hierarchical concept boost
                final_score = (
                    similarity * decay * reinforcement * entry.decay_factor * concept_boost
                )

                span.add_event(
                    "memory score",
                    attributes={
                        "entry_id": entry.id,
                        "similarity": similarity,
                        "concept_boost": concept_boost,
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
            logger.debug(f"Retrieved {len(results)} memory entries with hierarchical support.")
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
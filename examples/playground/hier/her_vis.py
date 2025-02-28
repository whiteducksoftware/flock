"""Visualization tool to compare traditional vs. hierarchical concept activation."""

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from typing import Dict, List, Set, Tuple

from flock.modules.hierarchical.memory import ConceptRelationType, HierarchicalMemoryGraph




class MemoryVisualizer:
    """Visualizes the difference between traditional and hierarchical concept activation."""
    
    def __init__(self, memory_graph: HierarchicalMemoryGraph):
        """Initialize the visualizer with a memory graph.
        
        Args:
            memory_graph: The hierarchical memory graph to visualize
        """
        self.memory_graph = memory_graph
        
    def visualize_activation_comparison(
        self, 
        query_concepts: Set[str],
        filename: str = "activation_comparison.png",
        figsize: Tuple[int, int] = (20, 10),
        node_size_factor: float = 2000,
        title_fontsize: int = 16
    ) -> None:
        """Create a side-by-side visualization comparing traditional vs. hierarchical activation.
        
        Args:
            query_concepts: The set of concepts to start activation from
            filename: Output file to save the visualization
            figsize: Figure size (width, height) in inches
            node_size_factor: Base factor for node size calculation
            title_fontsize: Font size for the titles
        """
        # Get both types of activation results
        traditional = self.memory_graph.spread_activation(query_concepts)
        hierarchical = self.memory_graph.hierarchical_spread_activation(
            query_concepts, 
            upward_factor=0.8, 
            downward_factor=0.6
        )
        
        # Create a figure with two subplots
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)
        
        # Get the graph
        graph = self.memory_graph.graph
        
        # Use the same layout for both visualizations for consistency
        pos = nx.kamada_kawai_layout(graph)
        
        # Create a custom colormap (white to blue)
        cmap = LinearSegmentedColormap.from_list(
            "blue_activation", 
            [(1, 1, 1, 0.7), (0.2, 0.4, 0.8, 0.9)]
        )
        
        # First subplot: Traditional activation
        self._draw_activation_graph(
            ax=ax1,
            graph=graph,
            pos=pos,
            activation=traditional,
            cmap=cmap,
            node_size_factor=node_size_factor,
            title="Traditional Concept Activation",
            title_fontsize=title_fontsize,
            highlight_concepts=query_concepts
        )
        
        # Second subplot: Hierarchical activation
        self._draw_activation_graph(
            ax=ax2,
            graph=graph,
            pos=pos,
            activation=hierarchical,
            cmap=cmap,
            node_size_factor=node_size_factor,
            title="Hierarchical Concept Activation",
            title_fontsize=title_fontsize,
            highlight_concepts=query_concepts
        )
        
        # Add a legend for the relationship types - only on the second subplot
        ax2.plot([], [], '-', color="#2c3e50", label='Association')
        ax2.plot([], [], '-', color="#2e8540", label='IS-A')
        ax2.plot([], [], '-', color="#1E88E5", label='HAS-A')
        ax2.plot([], [], '-', color="#9C27B0", label='Other Hierarchical')
        ax2.legend(loc='upper right', frameon=True, framealpha=0.9)
        
        # Add a color bar for activation level
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, 1))
        sm.set_array([])
        cbar = plt.colorbar(sm, ax=[ax1, ax2], orientation='horizontal', pad=0.01, aspect=40)
        cbar.set_label('Activation Level')
        
        # Add a main title
        fig.suptitle(f"Memory Activation Comparison\nQuery Concepts: {', '.join(query_concepts)}", 
                     fontsize=title_fontsize+2)
        
        # Tight layout and save
        plt.tight_layout(rect=[0, 0, 1, 0.96])  # Make room for the suptitle
        plt.savefig(filename, bbox_inches="tight", facecolor="white", dpi=150)
        plt.close()
        
    def _draw_activation_graph(
        self,
        ax: plt.Axes,
        graph: nx.MultiDiGraph,
        pos: Dict,
        activation: Dict[str, float],
        cmap: LinearSegmentedColormap,
        node_size_factor: float,
        title: str,
        title_fontsize: int,
        highlight_concepts: Set[str]
    ) -> None:
        """Draw a single activation graph on the given axes.
        
        Args:
            ax: Matplotlib axes to draw on
            graph: The NetworkX graph to visualize
            pos: Node positions
            activation: Dictionary mapping concepts to activation levels
            cmap: Colormap for activation visualization
            node_size_factor: Base factor for node size calculation
            title: Title for this visualization
            title_fontsize: Font size for the title
            highlight_concepts: Concepts to highlight as query concepts
        """
        # Normalize activation values to [0, 1] for coloring
        max_activation = max(activation.values()) if activation else 1.0
        
        # Prepare node colors, sizes, and labels
        node_colors = []
        node_sizes = []
        
        for node in graph.nodes():
            activation_level = activation.get(node, 0) / max_activation if max_activation > 0 else 0
            node_colors.append(cmap(activation_level))
            
            # Larger node size for more activated nodes
            base_size = node_size_factor * (0.5 + 0.5 * activation_level)
            # Even larger for highlight concepts
            if node in highlight_concepts:
                base_size *= 1.5
            node_sizes.append(base_size)
        
        # Draw nodes with activation-based coloring and sizing
        nx.draw_networkx_nodes(
            graph, 
            pos,
            ax=ax,
            node_color=node_colors,
            node_size=node_sizes,
            edgecolors='black',
            linewidths=0.5
        )
        
        # Draw different types of edges with distinct styles
        # 1. Association edges (standard style)
        association_edges = []
        for u, v, k, data in graph.edges(keys=True, data=True):
            relation_type = data.get('relation_type', ConceptRelationType.ASSOCIATION)
            if relation_type == ConceptRelationType.ASSOCIATION:
                association_edges.append((u, v))
                
        nx.draw_networkx_edges(
            graph,
            pos,
            ax=ax,
            edgelist=association_edges,
            width=1,
            alpha=0.5,
            edge_color="#2c3e50",  # Dark blue-grey
            arrows=False
        )
        
        # 2. IS-A relationships (green with arrow)
        is_a_edges = []
        for u, v, k, data in graph.edges(keys=True, data=True):
            relation_type = data.get('relation_type', None)
            if relation_type == ConceptRelationType.IS_A:
                is_a_edges.append((u, v))
                
        nx.draw_networkx_edges(
            graph,
            pos,
            ax=ax,
            edgelist=is_a_edges,
            width=1.5,
            alpha=0.7,
            edge_color="#2e8540",  # Green
            arrows=True,
            arrowsize=15,
            connectionstyle="arc3,rad=0.1"
        )
        
        # 3. HAS-A relationships (blue with arrow)
        has_a_edges = []
        for u, v, k, data in graph.edges(keys=True, data=True):
            relation_type = data.get('relation_type', None)
            if relation_type == ConceptRelationType.HAS_A:
                has_a_edges.append((u, v))
                
        nx.draw_networkx_edges(
            graph,
            pos,
            ax=ax,
            edgelist=has_a_edges,
            width=1.5,
            alpha=0.7,
            edge_color="#1E88E5",  # Blue
            arrows=True,
            arrowsize=15,
            connectionstyle="arc3,rad=-0.1"
        )
        
        # 4. Other hierarchical relationships (purple with arrow)
        other_edges = []
        for u, v, k, data in graph.edges(keys=True, data=True):
            relation_type = data.get('relation_type', None)
            if relation_type not in [None, ConceptRelationType.ASSOCIATION, 
                                    ConceptRelationType.IS_A, ConceptRelationType.HAS_A]:
                other_edges.append((u, v))
                
        nx.draw_networkx_edges(
            graph,
            pos,
            ax=ax,
            edgelist=other_edges,
            width=1.5,
            alpha=0.7,
            edge_color="#9C27B0",  # Purple
            arrows=True,
            arrowsize=15,
            connectionstyle="arc3,rad=0.15"
        )
        
        # Draw labels with white background for better readability
        labels = {node: node for node in graph.nodes()}
        label_box_args = dict(
            bbox=dict(facecolor='white', edgecolor='none', alpha=0.7, pad=3),
            horizontalalignment='center',
            verticalalignment='center',
            fontsize=9,
            fontweight='bold'
        )
        
        nx.draw_networkx_labels(
            graph, 
            pos,
            ax=ax,
            labels=labels, 
            **label_box_args
        )
        
        # Add highlighting for query concepts
        for concept in highlight_concepts:
            if concept in pos:
                ax.plot(
                    pos[concept][0], 
                    pos[concept][1], 
                    'o', 
                    markersize=15, 
                    fillstyle='none', 
                    color='red', 
                    mew=2
                )
        
        # Set title and turn off axis
        ax.set_title(title, fontsize=title_fontsize)
        ax.axis('off')


def create_sample_memory_graph() -> HierarchicalMemoryGraph:
    """Create a sample memory graph for visualization demonstration."""
    memory_graph = HierarchicalMemoryGraph()
    
    # Add concepts
    concepts = {
        "animal", "pet", "wild animal", "cat", "dog", "lion", "tiger",
        "fish", "goldfish", "shark", "siamese", "tabby", "german shepherd", "bulldog",
        "domestic", "aquatic", "mammal", "canine", "feline",
        "luna", "lucy", "rex", "fluffy", "food", "pet food", "cat food", "dog food"
    }
    memory_graph.add_concepts(concepts)
    
    # Add hierarchical relationships
    
    # Mammals
    memory_graph.add_hierarchical_relation("mammal", "animal", ConceptRelationType.IS_A)
    
    # Domestic vs Wild
    memory_graph.add_hierarchical_relation("pet", "domestic", ConceptRelationType.IS_A)
    memory_graph.add_hierarchical_relation("domestic", "animal", ConceptRelationType.IS_A)
    memory_graph.add_hierarchical_relation("wild animal", "animal", ConceptRelationType.IS_A)
    
    # Pet types
    memory_graph.add_hierarchical_relation("dog", "pet", ConceptRelationType.IS_A)
    memory_graph.add_hierarchical_relation("cat", "pet", ConceptRelationType.IS_A)
    memory_graph.add_hierarchical_relation("goldfish", "pet", ConceptRelationType.IS_A)
    
    # Cat and dog breeds
    memory_graph.add_hierarchical_relation("siamese", "cat", ConceptRelationType.IS_A)
    memory_graph.add_hierarchical_relation("tabby", "cat", ConceptRelationType.IS_A)
    memory_graph.add_hierarchical_relation("german shepherd", "dog", ConceptRelationType.IS_A)
    memory_graph.add_hierarchical_relation("bulldog", "dog", ConceptRelationType.IS_A)
    
    # Wild animals
    memory_graph.add_hierarchical_relation("lion", "wild animal", ConceptRelationType.IS_A)
    memory_graph.add_hierarchical_relation("tiger", "wild animal", ConceptRelationType.IS_A)
    memory_graph.add_hierarchical_relation("shark", "wild animal", ConceptRelationType.IS_A)
    
    # Taxonomic categories
    memory_graph.add_hierarchical_relation("dog", "canine", ConceptRelationType.IS_A)
    memory_graph.add_hierarchical_relation("canine", "mammal", ConceptRelationType.IS_A)
    memory_graph.add_hierarchical_relation("cat", "feline", ConceptRelationType.IS_A)
    memory_graph.add_hierarchical_relation("feline", "mammal", ConceptRelationType.IS_A)
    memory_graph.add_hierarchical_relation("lion", "feline", ConceptRelationType.IS_A)
    memory_graph.add_hierarchical_relation("tiger", "feline", ConceptRelationType.IS_A)
    
    # Fish
    memory_graph.add_hierarchical_relation("fish", "animal", ConceptRelationType.IS_A)
    memory_graph.add_hierarchical_relation("goldfish", "fish", ConceptRelationType.IS_A)
    memory_graph.add_hierarchical_relation("shark", "fish", ConceptRelationType.IS_A)
    memory_graph.add_hierarchical_relation("fish", "aquatic", ConceptRelationType.IS_A)
    
    # Specific pet instances
    memory_graph.add_hierarchical_relation("luna", "cat", ConceptRelationType.IS_A)
    memory_graph.add_hierarchical_relation("lucy", "cat", ConceptRelationType.IS_A)
    memory_graph.add_hierarchical_relation("rex", "dog", ConceptRelationType.IS_A)
    memory_graph.add_hierarchical_relation("fluffy", "dog", ConceptRelationType.IS_A)
    
    # Food relationships (HAS-A)
    memory_graph.add_hierarchical_relation("pet food", "food", ConceptRelationType.IS_A)
    memory_graph.add_hierarchical_relation("cat food", "pet food", ConceptRelationType.IS_A)
    memory_graph.add_hierarchical_relation("dog food", "pet food", ConceptRelationType.IS_A)
    memory_graph.add_hierarchical_relation("cat", "cat food", ConceptRelationType.HAS_A)
    memory_graph.add_hierarchical_relation("dog", "dog food", ConceptRelationType.HAS_A)
    
    # Add some standard associations too
    for concept1 in ["luna", "lucy", "siamese", "tabby"]:
        for concept2 in ["cat", "feline"]:
            if concept1 != concept2:
                memory_graph._graph.add_edge(
                    concept1, concept2, 
                    key=ConceptRelationType.ASSOCIATION,
                    weight=2, 
                    relation_type=ConceptRelationType.ASSOCIATION
                )
    
    return memory_graph


def main():
    """Generate a visualization comparing traditional and hierarchical memory activation."""
    # Create a sample memory graph
    memory_graph = create_sample_memory_graph()
    
    # Create the visualizer
    visualizer = MemoryVisualizer(memory_graph)
    
    # Generate comparison visualizations for different query scenarios
    
    # Scenario 1: Query for a specific cat name
    visualizer.visualize_activation_comparison(
        query_concepts={"luna"},
        filename="activation_comparison_specific_cat.png"
    )
    print("Generated visualization for 'luna' query")
    
    # Scenario 2: Query about cats in general
    visualizer.visualize_activation_comparison(
        query_concepts={"cat"},
        filename="activation_comparison_general_cat.png"
    )
    print("Generated visualization for 'cat' query")
    
    # Scenario 3: Query about pets (higher-level concept)
    visualizer.visualize_activation_comparison(
        query_concepts={"pet"},
        filename="activation_comparison_pets.png"
    )
    print("Generated visualization for 'pet' query")
    
    # Scenario 4: Query with multiple concepts
    visualizer.visualize_activation_comparison(
        query_concepts={"dog", "food"},
        filename="activation_comparison_multiple_concepts.png"
    )
    print("Generated visualization for 'dog' and 'food' query")
    
    print("All visualizations completed successfully!")


if __name__ == "__main__":
    main()
# memory_store.py

import faiss
import numpy as np
import time
import networkx as nx
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans
from sklearn.preprocessing import normalize
from collections import defaultdict

class MemoryStore:
    def __init__(self, dimension=1536):
        self.dimension = dimension
        self.index = faiss.IndexFlatL2(dimension)
        self.short_term_memory = []  # Short-term memory interactions
        self.long_term_memory = []   # Long-term memory interactions
        self.embeddings = []         # Embeddings for each interaction in short-term memory
        self.timestamps = []         # Timestamps for decay in short-term memory
        self.access_counts = []      # Access counts for reinforcement in short-term memory
        self.concepts_list = []      # Concepts for each interaction in short-term memory
        self.graph = nx.Graph()      # Graph for bidirectional associations
        self.semantic_memory = defaultdict(list)  # Semantic memory clusters
        self.cluster_labels = []     # Labels for each interaction's cluster

    def add_interaction(self, interaction):
        interaction_id = interaction['id']
        prompt = interaction['prompt']
        output = interaction['output']
        embedding = np.array(interaction['embedding']).reshape(1, -1)
        timestamp = interaction.get('timestamp', time.time())  # Use current time if 'timestamp' is missing
        access_count = interaction.get('access_count', 1)
        concepts = set(interaction.get('concepts', []))
        decay_factor = interaction.get('decay_factor', 1.0)

        print(f"Adding new interaction to short-term memory: '{prompt}'")
        # Save the interaction data to short-term memory
        self.short_term_memory.append({
            "id": interaction_id,
            "prompt": prompt,
            "output": output,
            "timestamp": timestamp,
            "access_count": access_count,
            "decay_factor": decay_factor
        })
        self.embeddings.append(embedding)
        self.index.add(embedding)
        self.timestamps.append(timestamp)
        self.access_counts.append(access_count)
        self.concepts_list.append(concepts)

        # Update graph with bidirectional associations
        self.update_graph(concepts)

        print(f"Total interactions stored in short-term memory: {len(self.short_term_memory)}")

    def update_graph(self, concepts):
        # Use the saved concepts to update the graph
        for concept in concepts:
            self.graph.add_node(concept)
        # Add edges between concepts (associations)
        for concept1 in concepts:
            for concept2 in concepts:
                if concept1 != concept2:
                    if self.graph.has_edge(concept1, concept2):
                        self.graph[concept1][concept2]['weight'] += 1
                    else:
                        self.graph.add_edge(concept1, concept2, weight=1)

    def classify_memory(self):
        # Move interactions with access count > 10 to long-term memory
        for idx, access_count in enumerate(self.access_counts):
            if access_count > 10 and self.short_term_memory[idx] not in self.long_term_memory:
                self.long_term_memory.append(self.short_term_memory[idx])
                print(f"Moved interaction {self.short_term_memory[idx]['id']} to long-term memory.")

    def retrieve(self, query_embedding, query_concepts, similarity_threshold=40, exclude_last_n=0):
        if len(self.short_term_memory) == 0:
            print("No interactions available in short-term memory for retrieval.")
            return []

        print("Retrieving relevant interactions from short-term memory...")
        relevant_interactions = []
        current_time = time.time()
        decay_rate = 0.0001  # Adjust decay rate as needed

        # Normalize embeddings for cosine similarity
        normalized_embeddings = [normalize(e) for e in self.embeddings]
        query_embedding_norm = normalize(query_embedding)

        # Track indices of relevant interactions
        relevant_indices = set()

        # Calculate adjusted similarity for each interaction
        for idx in range(len(self.short_term_memory) - exclude_last_n):
            # Cosine similarity
            similarity = cosine_similarity(query_embedding_norm, normalized_embeddings[idx])[0][0] * 100
            # Time-based decay
            time_diff = current_time - self.timestamps[idx]
            decay_factor = self.short_term_memory[idx].get('decay_factor', 1.0) * np.exp(-decay_rate * time_diff)
            self.short_term_memory[idx]['decay_factor'] = decay_factor
            # Reinforcement
            reinforcement_factor = np.log1p(self.access_counts[idx])
            # Adjusted similarity
            adjusted_similarity = similarity * decay_factor * reinforcement_factor
            print(f"Interaction {idx} - Adjusted similarity score: {adjusted_similarity:.2f}%")

            if adjusted_similarity >= similarity_threshold:
                # Mark interaction as relevant
                relevant_indices.add(idx)
                # Update access count and timestamp for relevant interactions
                self.access_counts[idx] += 1
                self.timestamps[idx] = current_time
                self.short_term_memory[idx]['timestamp'] = current_time
                self.short_term_memory[idx]['access_count'] = self.access_counts[idx]
                print(f"[DEBUG] Updated access count for interaction {self.short_term_memory[idx]['id']}: {self.access_counts[idx]}")

                # Move interaction to long-term memory if access count exceeds 10
                if self.access_counts[idx] > 10:
                    self.classify_memory()

                # Increase decay factor for relevant interaction
                self.short_term_memory[idx]['decay_factor'] *= 1.1  # Increase by 10% or adjust as needed

                # Add to the list of relevant interactions
                relevant_interactions.append((adjusted_similarity, self.short_term_memory[idx], self.concepts_list[idx]))
            else:
                print(f"[DEBUG] Interaction {self.short_term_memory[idx]['id']} was not relevant (similarity: {adjusted_similarity:.2f}%).")

        # Decrease decay factor for non-relevant interactions
        for idx in range(len(self.short_term_memory)):
            if idx not in relevant_indices:
                # Apply decay for non-relevant interactions
                self.short_term_memory[idx]['decay_factor'] *= 0.9  # Decrease by 10% or adjust as needed

        # Spreading activation
        activated_concepts = self.spreading_activation(query_concepts)

        # Integrate spreading activation scores
        final_interactions = []
        for score, interaction, concepts in relevant_interactions:
            activation_score = sum([activated_concepts.get(c, 0) for c in concepts])
            total_score = score + activation_score
            interaction['total_score'] = total_score
            final_interactions.append((total_score, interaction))

        # Sort interactions based on total_score
        final_interactions.sort(key=lambda x: x[0], reverse=True)
        final_interactions = [interaction for _, interaction in final_interactions]

        # Retrieve from semantic memory
        semantic_interactions = self.retrieve_from_semantic_memory(query_embedding_norm)
        final_interactions.extend(semantic_interactions)

        print(f"Retrieved {len(final_interactions)} relevant interactions from memory.")
        return final_interactions

    def spreading_activation(self, query_concepts):
        print("Spreading activation for concept associations...")
        activated_nodes = {}
        initial_activation = 1.0
        decay_factor = 0.5  # How much the activation decays each step

        # Initialize activation levels
        for concept in query_concepts:
            activated_nodes[concept] = initial_activation

        # Spread activation over the graph
        for step in range(2):  # Number of steps to spread activation
            new_activated_nodes = {}
            for node in activated_nodes:
                if node in self.graph:  # Check if the node exists in the graph
                    for neighbor in self.graph.neighbors(node):
                        if neighbor not in activated_nodes:
                            weight = self.graph[node][neighbor]['weight']
                            new_activation = activated_nodes[node] * decay_factor * weight
                            new_activated_nodes[neighbor] = new_activated_nodes.get(neighbor, 0) + new_activation
            activated_nodes.update(new_activated_nodes)

        print(f"Concepts activated after spreading: {activated_nodes}")
        return activated_nodes

    def cluster_interactions(self):
        print("Clustering interactions to create hierarchical memory...")
        if len(self.embeddings) < 2:
            print("Not enough interactions to perform clustering.")
            return

        embeddings_matrix = np.vstack([e for e in self.embeddings])
        num_clusters = min(10, len(self.embeddings))  # Adjust number of clusters based on the number of interactions
        kmeans = KMeans(n_clusters=num_clusters, random_state=0).fit(embeddings_matrix)
        self.cluster_labels = kmeans.labels_

        # Build semantic memory clusters
        for idx, label in enumerate(self.cluster_labels):
            self.semantic_memory[label].append((self.embeddings[idx], self.short_term_memory[idx]))

        print(f"Clustering completed. Total clusters formed: {num_clusters}")

    def retrieve_from_semantic_memory(self, query_embedding_norm):
        print("Retrieving interactions from semantic memory...")
        current_time = time.time()
        # Find the cluster closest to the query
        cluster_similarities = {}
        for label, items in self.semantic_memory.items():
            # Calculate centroid of the cluster
            cluster_embeddings = np.vstack([e for e, _ in items])
            centroid = np.mean(cluster_embeddings, axis=0).reshape(1, -1)
            centroid_norm = normalize(centroid)
            similarity = cosine_similarity(query_embedding_norm, centroid_norm)[0][0]
            cluster_similarities[label] = similarity

        # Select the most similar cluster
        if not cluster_similarities:
            return []
        best_cluster_label = max(cluster_similarities, key=cluster_similarities.get)
        print(f"Best matching cluster identified: {best_cluster_label}")

        # Retrieve interactions from the best cluster
        cluster_items = self.semantic_memory[best_cluster_label]
        interactions = [(e, i) for e, i in cluster_items]

        # Sort interactions based on similarity to the query
        interactions.sort(key=lambda x: cosine_similarity(query_embedding_norm, normalize(x[0]))[0][0], reverse=True)
        semantic_interactions = [interaction for _, interaction in interactions[:5]]  # Limit to top 5 interactions

        # Update access count for these retrieved interactions
        for interaction in semantic_interactions:
            interaction_id = interaction['id']
            idx = next((i for i, item in enumerate(self.short_term_memory) if item['id'] == interaction_id), None)
            if idx is not None:
                self.access_counts[idx] += 1
                self.timestamps[idx] = current_time
                self.short_term_memory[idx]['timestamp'] = current_time
                self.short_term_memory[idx]['access_count'] = self.access_counts[idx]
                print(f"[DEBUG] Updated access count for interaction {interaction_id}: {self.access_counts[idx]}")

        print(f"Retrieved {len(semantic_interactions)} interactions from the best matching cluster.")
        return semantic_interactions

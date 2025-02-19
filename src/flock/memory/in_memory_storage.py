# in_memory_storage.py

from .storage import BaseStorage

class InMemoryStorage(BaseStorage):
    def __init__(self):
        self.history = {
            "short_term_memory": [],
            "long_term_memory": []
        }

    def load_history(self):
        print("Loading history from in-memory storage.")
        return self.history.get("short_term_memory", []), self.history.get("long_term_memory", [])

    def save_memory_to_history(self, memory_store):
        print("Saving history to in-memory storage.")
        self.history = {
            "short_term_memory": [],
            "long_term_memory": []
        }

        # Save short-term memory interactions
        for idx in range(len(memory_store.short_term_memory)):
            interaction = {
                'id': memory_store.short_term_memory[idx]['id'],
                'prompt': memory_store.short_term_memory[idx]['prompt'],
                'output': memory_store.short_term_memory[idx]['output'],
                'embedding': memory_store.embeddings[idx].flatten().tolist(),
                'timestamp': memory_store.timestamps[idx],
                'access_count': memory_store.access_counts[idx],
                'concepts': list(memory_store.concepts_list[idx]),
                'decay_factor': memory_store.short_term_memory[idx].get('decay_factor', 1.0)
            }
            self.history["short_term_memory"].append(interaction)

        # Save long-term memory interactions
        for interaction in memory_store.long_term_memory:
            self.history["long_term_memory"].append(interaction)

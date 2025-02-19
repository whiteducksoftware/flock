# json_storage.py

import json
import os

from .storage import BaseStorage

class JSONStorage(BaseStorage):
    def __init__(self, file_path="interaction_history.json"):
        self.file_path = file_path

    def load_history(self):
        if os.path.exists(self.file_path):
            with open(self.file_path, 'r') as f:
                print("Loading existing interaction history from JSON...")
                history = json.load(f)
                return history.get("short_term_memory", []), history.get("long_term_memory", [])
        print("No existing interaction history found in JSON. Starting fresh.")
        return [], []

    def save_memory_to_history(self, memory_store):
        history = {
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
            history["short_term_memory"].append(interaction)

        # Save long-term memory interactions
        for interaction in memory_store.long_term_memory:
            history["long_term_memory"].append(interaction)

        # Save the history to a file
        with open(self.file_path, 'w') as f:
            json.dump(history, f, indent=4)
        print(f"Saved interaction history to JSON. Short-term: {len(history['short_term_memory'])}, Long-term: {len(history['long_term_memory'])}")

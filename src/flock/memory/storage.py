# storage.py

class BaseStorage:
    def load_history(self):
        raise NotImplementedError("The method load_history() must be implemented.")

    def save_memory_to_history(self, memory_store):
        raise NotImplementedError("The method save_memory_to_history() must be implemented.")

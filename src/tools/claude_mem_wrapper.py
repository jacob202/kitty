import json
from pathlib import Path


class ClaudeMemWrapper:
    def __init__(self, memory_file="./data/vector_store/memory.json"):
        self.memory_file = Path(memory_file)
        if not self.memory_file.exists():
            self.memory_file.write_text("{}")

    def remember(self, key, value):
        data = json.loads(self.memory_file.read_text())
        data[key] = value
        self.memory_file.write_text(json.dumps(data, indent=2))

    def recall(self, key):
        data = json.loads(self.memory_file.read_text())
        return data.get(key, "No memory found.")

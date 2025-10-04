"""In-memory hash index mapping keys to file offsets."""
import os
import pickle
from typing import Optional, Dict, Tuple


class Index:
    """In-memory hash index mapping keys to file offsets."""

    def __init__(self, path: str):
        self.path = path
        self.index: Dict[bytes, Tuple[int, int]] = {}
        self.load()

    def put(self, key: bytes, offset: int, length: int):
        """Add or update key in index."""
        self.index[key] = (offset, length)

    def get(self, key: bytes) -> Optional[Tuple[int, int]]:
        """Get offset and length for key."""
        return self.index.get(key)

    def get_range(self, start_key: bytes, end_key: bytes) -> Dict[bytes, Tuple[int, int]]:
        """Get all keys in range [start_key, end_key]."""
        result = {}
        for key, location in self.index.items():
            if start_key <= key <= end_key:
                result[key] = location
        return result

    def delete(self, key: bytes):
        """Remove key from index."""
        self.index.pop(key, None)

    def save(self):
        """Persist index to disk."""
        with open(self.path, 'wb') as f:
            pickle.dump(self.index, f)

    def load(self):
        """Load index from disk."""
        if os.path.exists(self.path):
            with open(self.path, 'rb') as f:
                self.index = pickle.load(f)

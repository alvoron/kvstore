"""Write-Ahead Log implementation for durability and crash recovery."""
import os
import struct
import time
import pickle
from typing import Optional, List, Dict, Any
from ..utils.config import Config


class WAL:
    """Write-Ahead Log for durability and crash recovery."""

    def __init__(self, path: str):
        self.path = path
        self.file = open(path, 'ab', buffering=Config.WAL_BUFFER_SIZE)  # Unbuffered for immediate flush

    def log(self, operation: str, key: bytes, value: Optional[bytes] = None):
        """Log an operation to WAL."""
        entry = {
            'op': operation,
            'key': key,
            'value': value,
            'timestamp': time.time()
        }
        serialized = pickle.dumps(entry)
        length = struct.pack('!I', len(serialized))
        self.file.write(length + serialized)
        os.fsync(self.file.fileno())  # Force write to disk

    def replay(self) -> List[Dict[str, Any]]:
        """Replay WAL entries for crash recovery."""
        if not os.path.exists(self.path) or os.path.getsize(self.path) == 0:
            return []

        entries = []
        with open(self.path, 'rb') as f:
            while True:
                length_bytes = f.read(4)
                if not length_bytes:
                    break
                length = struct.unpack('!I', length_bytes)[0]
                entry_bytes = f.read(length)
                entries.append(pickle.loads(entry_bytes))
        return entries

    def truncate(self):
        """Clear WAL after successful checkpoint."""
        self.file.close()
        self.file = open(self.path, 'wb', buffering=Config.WAL_BUFFER_SIZE)

    def close(self):
        """Close WAL file."""
        self.file.close()

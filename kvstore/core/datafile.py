"""Append-only data file with memory mapping for efficient access."""
import os
import mmap
import struct
from typing import Tuple


class DataFile:
    """Append-only data file with memory mapping for efficient access."""

    def __init__(self, path: str):
        self.path = path
        self.file = open(path, 'a+b')
        self.file.seek(0, 2)  # Seek to end
        self.size = self.file.tell()
        self._mmap = None
        self._update_mmap()

    def _update_mmap(self):
        """Update memory map after file grows."""
        if self._mmap:
            self._mmap.close()
        if self.size > 0:
            self._mmap = mmap.mmap(self.file.fileno(), 0, access=mmap.ACCESS_READ)

    def append(self, key: bytes, value: bytes) -> Tuple[int, int]:
        """
        Append key-value pair to data file.
        Returns (offset, length) for indexing.
        """
        # Format: [key_len(4)][key][value_len(4)][value]
        key_len = struct.pack('!I', len(key))
        value_len = struct.pack('!I', len(value))

        offset = self.size
        data = key_len + key + value_len + value

        self.file.write(data)
        self.file.flush()
        os.fsync(self.file.fileno())

        self.size += len(data)
        self._update_mmap()

        return offset, len(data)

    def read(self, offset: int) -> Tuple[bytes, bytes]:
        """Read key-value pair at given offset."""
        if not self._mmap:
            raise ValueError("Cannot read from empty file")

        # Read key length
        key_len = struct.unpack('!I', self._mmap[offset:offset+4])[0]
        offset += 4

        # Read key
        key = bytes(self._mmap[offset:offset+key_len])
        offset += key_len

        # Read value length
        value_len = struct.unpack('!I', self._mmap[offset:offset+4])[0]
        offset += 4

        # Read value
        value = bytes(self._mmap[offset:offset+value_len])

        return key, value

    def close(self):
        """Close data file and mmap."""
        try:
            if self._mmap:
                self._mmap.close()
        except (ValueError, OSError):
            # mmap already closed or invalid
            pass

        try:
            self.file.close()
        except (ValueError, OSError):
            # file already closed
            pass

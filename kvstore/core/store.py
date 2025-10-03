"""Main KVStore implementation."""
import threading
import time
from pathlib import Path
from typing import Optional

from .wal import WAL
from .datafile import DataFile
from .index import Index
from ..utils.rwlock import RWLock, ReadLock, WriteLock


class KVStore:
    """Core Key/Value store implementation."""
    
    def __init__(self, data_dir: str = './kvstore_data'):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Initialize components
        self.wal = WAL(str(self.data_dir / 'wal.log'))
        self.data_file = DataFile(str(self.data_dir / 'data.db'))
        self.index = Index(str(self.data_dir / 'index.db'))
        
        # Reader-Writer Lock for thread safety (allows concurrent reads)
        self.rwlock = RWLock()
        
        # Separate lock for WAL writes (prevents WAL blocking in read-heavy workloads)
        self.wal_lock = threading.Lock()
        
        # Recover from crash if needed
        self._recover()
        
        # Background checkpoint thread
        self.checkpoint_interval = 10  # seconds
        self.running = True
        self.checkpoint_thread = threading.Thread(target=self._checkpoint_loop, daemon=True)
        self.checkpoint_thread.start()
    
    def _recover(self):
        """Recover from crash by replaying WAL."""
        entries = self.wal.replay()
        for entry in entries:
            if entry['op'] == 'put':
                offset, length = self.data_file.append(entry['key'], entry['value'])
                self.index.put(entry['key'], offset, length)
            elif entry['op'] == 'delete':
                self.index.delete(entry['key'])
        
        if entries:
            self.index.save()
            self.wal.truncate()
    
    def _checkpoint_loop(self):
        """Periodically checkpoint index to disk."""
        while self.running:
            time.sleep(self.checkpoint_interval)
            with WriteLock(self.rwlock):
                self.index.save()
            # Truncate WAL under its own lock after index is saved
            with self.wal_lock:
                self.wal.truncate()
    
    def put(self, key: bytes, value: bytes) -> bool:
        """Store key-value pair."""
        try:
            # Phase 1: Log to WAL under separate lock (doesn't block on readers)
            with self.wal_lock:
                self.wal.log('put', key, value)
            
            # Phase 2: Update data and index under write lock
            with WriteLock(self.rwlock):
                # Append to data file
                offset, length = self.data_file.append(key, value)
                
                # Update index
                self.index.put(key, offset, length)
            
            return True
        except Exception as e:
            print(f"Error in put: {e}")
            return False
    
    def batch_put(self, keys: list[bytes], values: list[bytes]) -> bool:
        """Store multiple key-value pairs in a batch operation."""
        if len(keys) != len(values):
            raise ValueError("Keys and values must have the same length")
        
        try:
            # Phase 1: Log all to WAL under separate lock (doesn't block on readers)
            with self.wal_lock:
                for key, value in zip(keys, values):
                    self.wal.log('put', key, value)
            
            # Phase 2: Update data and index under write lock
            with WriteLock(self.rwlock):
                for key, value in zip(keys, values):
                    # Append to data file
                    offset, length = self.data_file.append(key, value)
                    
                    # Update index
                    self.index.put(key, offset, length)
            
            return True
        except Exception as e:
            print(f"Error in batch_put: {e}")
            return False
    
    def read(self, key: bytes) -> Optional[bytes]:
        """Read value for key."""
        with ReadLock(self.rwlock):
            try:
                # Lookup in index
                location = self.index.get(key)
                if not location:
                    return None
                
                offset, _ = location
                
                # Read from data file
                stored_key, value = self.data_file.read(offset)
                
                # Verify key matches
                if stored_key != key:
                    return None
                
                return value
            except Exception as e:
                print(f"Error in read: {e}")
                return None
    
    def read_key_range(self, start_key: bytes, end_key: bytes) -> dict[bytes, bytes]:
        """Read all key-value pairs within the specified range [start_key, end_key]."""
        with ReadLock(self.rwlock):
            try:
                result = {}
                # Get all keys in range from index
                locations = self.index.get_range(start_key, end_key)
                
                # Read each key-value pair from data file
                for key, (offset, _) in locations.items():
                    stored_key, value = self.data_file.read(offset)
                    if stored_key == key:
                        result[key] = value
                
                return result
            except Exception as e:
                print(f"Error in read_key_range: {e}")
                return {}
    
    def delete(self, key: bytes) -> bool:
        """Delete key from store."""
        try:
            # Check if key exists first (can use read lock for this check)
            with ReadLock(self.rwlock):
                if self.index.get(key) is None:
                    return False
            
            # Phase 1: Log to WAL under separate lock
            with self.wal_lock:
                self.wal.log('delete', key)
            
            # Phase 2: Update index under write lock
            with WriteLock(self.rwlock):
                # Double-check key still exists (could have been deleted by another thread)
                if self.index.get(key) is None:
                    return False
                # Remove from index
                self.index.delete(key)
            
            return True
        except Exception as e:
            print(f"Error in delete: {e}")
            return False
    
    def close(self):
        """Clean shutdown."""
        self.running = False
        self.checkpoint_thread.join()
        self.index.save()
        self.wal.close()
        self.data_file.close()

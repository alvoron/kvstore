"""Main KVStore implementation."""
import threading
import os
import sys
from pathlib import Path
from typing import Optional

from .wal import WAL
from .datafile import DataFile
from .index import Index
from ..utils.rwlock import RWLock, ReadLock, WriteLock
from ..utils.config import Config


class DataDirectoryLockError(Exception):
    """Raised when data directory is already locked by another process."""
    pass


class KVStore:
    """Core Key/Value store implementation."""

    def __init__(self, data_dir: str = None, is_replica: bool = False, checkpoint_interval: int = None):
        self.data_dir = Path(data_dir or Config.DATA_DIR)
        self.data_dir.mkdir(exist_ok=True)
        self.is_replica = is_replica
        
        # Acquire directory lock to prevent multiple processes
        self.lockfile_path = self.data_dir / '.lock'
        self._acquire_lock()

        # Initialize components
        self.wal = WAL(str(self.data_dir / Config.WAL_FILENAME))
        self.data_file = DataFile(str(self.data_dir / Config.DATA_FILENAME))
        self.index = Index(str(self.data_dir / Config.INDEX_FILENAME))

        # Reader-Writer Lock for thread safety (allows concurrent reads)
        self.rwlock = RWLock()

        # Separate lock for WAL writes (prevents WAL blocking in read-heavy workloads)
        self.wal_lock = threading.Lock()

        # Recover from crash if needed
        self._recover()

        # Initialize replication (only if not a replica and replication is enabled)
        self.replicator = None
        if not is_replica and Config.REPLICATION_ENABLED:
            self._init_replication()

        # Background checkpoint thread
        self.checkpoint_interval = checkpoint_interval or Config.CHECKPOINT_INTERVAL
        self.running = True
        self._stop_event = threading.Event()
        self.checkpoint_thread = threading.Thread(target=self._checkpoint_loop, daemon=True)
        self.checkpoint_thread.start()

        # Background compaction thread
        self.compaction_enabled = Config.COMPACTION_ENABLED and not is_replica
        if self.compaction_enabled:
            self.compaction_thread = threading.Thread(target=self._compaction_loop, daemon=True)
            self.compaction_thread.start()

    def _init_replication(self):
        """Initialize replication components."""
        try:
            from ..replication import Replicator, ReplicaManager

            # Create replica manager
            self.replica_manager = ReplicaManager(
                max_failures=Config.REPLICATION_MAX_FAILURES,
                health_check_interval=Config.REPLICATION_HEALTH_CHECK_INTERVAL
            )

            # Add configured replicas
            for host, port in Config.REPLICA_ADDRESSES:
                self.replica_manager.add_replica(host, port)

            # Create replicator
            self.replicator = Replicator(
                replica_manager=self.replica_manager,
                mode=Config.REPLICATION_MODE,
                max_retries=Config.REPLICATION_MAX_RETRIES,
                queue_size=Config.REPLICATION_QUEUE_SIZE
            )

            # Start replication
            self.replicator.start()
            self.replica_manager.start_health_monitoring()

            replica_count = len(Config.REPLICA_ADDRESSES)
            print(f"[KVStore] Replication enabled in {Config.REPLICATION_MODE} mode with {replica_count} replicas")
        except Exception as e:
            print(f"[KVStore] Failed to initialize replication: {e}")
            self.replicator = None

    def _acquire_lock(self):
        """Acquire an exclusive lock on the data directory."""
        try:
            # Try to create lockfile with exclusive creation
            # If file exists, open will fail (on most systems)
            if self.lockfile_path.exists():
                # Check if it's a stale lock (process died)
                try:
                    with open(self.lockfile_path, 'r') as f:
                        pid = int(f.read().strip())

                    # Check if it's our own process (sequential usage in same process is OK)
                    current_pid = os.getpid()
                    if pid == current_pid:
                        # Same process - this is OK, just reuse the lock
                        # (happens when one store is closed and another opens in same process)
                        return

                    # Check if process is still running
                    if self._is_process_running(pid):
                        error_msg = (
                            f"\n{'='*70}\n"
                            f"ERROR: Data directory is already in use!\n"
                            f"{'='*70}\n"
                            f"Directory: {self.data_dir}\n"
                            f"Used by process: {pid}\n"
                            f"\n"
                            f"Each KVStore instance must use a unique data directory.\n"
                            f"{'='*70}\n"
                        )
                        raise DataDirectoryLockError(error_msg)
                    else:
                        # Stale lock, remove it
                        print(f"[KVStore] Removing stale lock file (PID {pid} not running)")
                        self.lockfile_path.unlink()
                except (ValueError, IOError):
                    # Invalid lock file, remove it
                    self.lockfile_path.unlink()

            # Write our PID to the lock file
            with open(self.lockfile_path, 'w') as f:
                f.write(str(os.getpid()))

        except DataDirectoryLockError:
            raise
        except Exception as e:
            print(f"[KVStore] Warning: Could not acquire directory lock: {e}")

    def _is_process_running(self, pid: int) -> bool:
        """Check if a process with given PID is running."""
        try:
            if sys.platform == 'win32':
                # Windows
                import ctypes
                kernel32 = ctypes.windll.kernel32
                PROCESS_QUERY_INFORMATION = 0x0400
                handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, 0, pid)
                if handle:
                    kernel32.CloseHandle(handle)
                    return True
                return False
            else:
                # Unix/Linux/Mac
                os.kill(pid, 0)  # Signal 0 doesn't kill, just checks existence
                return True
        except (OSError, AttributeError):
            return False

    def _release_lock(self):
        """Release the directory lock."""
        try:
            if self.lockfile_path.exists():
                self.lockfile_path.unlink()
        except Exception as e:
            print(f"[KVStore] Warning: Could not release lock: {e}")

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
            # Use Event.wait() instead of time.sleep() so we can interrupt immediately
            if self._stop_event.wait(timeout=self.checkpoint_interval):
                # Stop event was set, exit immediately
                break

            if not self.running:
                break

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

            # Phase 3: Replicate to replicas (if not a replica and replication enabled)
            if self.replicator and not self.is_replica:
                self.replicator.replicate_put(key, value)

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

            # Phase 3: Replicate to replicas (if not a replica and replication enabled)
            if self.replicator and not self.is_replica:
                self.replicator.replicate_batch_put(keys, values)

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

            # Phase 3: Replicate to replicas (if not a replica and replication enabled)
            if self.replicator and not self.is_replica:
                self.replicator.replicate_delete(key)

            return True
        except Exception as e:
            print(f"Error in delete: {e}")
            return False

    def _should_compact(self) -> bool:
        """Check if compaction is needed based on configured thresholds."""
        if self.data_file.size < Config.COMPACTION_MIN_FILE_SIZE:
            return False  # File too small to bother
        
        # Acquire read lock to safely iterate index
        with ReadLock(self.rwlock):
            if not self.index.index:
                return False  # Empty index
            
            total_size = self.data_file.size
            if total_size == 0:
                return False
            
            # Calculate live data size
            live_size = sum(length for offset, length in self.index.index.values())
            
            # Calculate dead space ratio
            dead_ratio = 1 - (live_size / total_size)
            
            return dead_ratio >= Config.COMPACTION_THRESHOLD

    def _compact(self):
        """
        Compact the data file to reclaim space from deleted entries.
        Creates a new file with only active (indexed) entries.
        """
        import time
        
        start_time = time.time()
        print(f"[Compaction] Starting compaction...")
        
        # Get snapshot of current state
        with ReadLock(self.rwlock):
            old_size = self.data_file.size
            entry_count = len(self.index.index)
            index_snapshot = self.index.index.copy()
        
        if not index_snapshot:
            print(f"[Compaction] No entries to compact")
            return
        
        try:
            # Create temporary compacted file
            temp_path = str(self.data_dir / (Config.DATA_FILENAME + '.compact'))
            new_datafile = DataFile(temp_path)
            new_index = {}
            
            # Copy all active entries to new file
            copied = 0
            for key, (old_offset, old_length) in index_snapshot.items():
                try:
                    # Read from old file with read lock
                    with ReadLock(self.rwlock):
                        stored_key, value = self.data_file.read(old_offset)
                    
                    if stored_key == key:
                        # Write to new file (no lock needed - separate file)
                        new_offset, new_length = new_datafile.append(key, value)
                        new_index[key] = (new_offset, new_length)
                        copied += 1
                except Exception as e:
                    print(f"[Compaction] Error copying entry for key {key}: {e}")
                    continue
            
            # Now do atomic swap with write lock
            with WriteLock(self.rwlock):
                # Check for any updates that happened during compaction
                for key, (offset, length) in self.index.index.items():
                    if key not in new_index or self.index.index[key] != index_snapshot.get(key):
                        # New or updated entry - copy from current file
                        try:
                            stored_key, value = self.data_file.read(offset)
                            new_offset, new_length = new_datafile.append(key, value)
                            new_index[key] = (new_offset, new_length)
                        except Exception as e:
                            print(f"[Compaction] Error copying updated entry for key {key}: {e}")
                
                # Close and swap files
                new_datafile.close()
                old_path = self.data_file.path
                self.data_file.close()
                
                # Backup old file
                backup_path = str(self.data_dir / (Config.DATA_FILENAME + '.old'))
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                os.rename(old_path, backup_path)
                
                # Activate new file
                os.rename(temp_path, old_path)
                
                # Reopen and update index
                self.data_file = DataFile(old_path)
                self.index.index = new_index
                self.index.save()
            
            # Print statistics
            new_size = self.data_file.size
            reclaimed = old_size - new_size
            duration = time.time() - start_time
            
            print(f"[Compaction] Completed successfully:")
            print(f"  Duration: {duration:.2f}s")
            print(f"  Old size: {old_size:,} bytes")
            print(f"  New size: {new_size:,} bytes")
            print(f"  Reclaimed: {reclaimed:,} bytes ({reclaimed/old_size*100:.1f}%)")
            print(f"  Entries copied: {copied}/{entry_count}")
            
        except Exception as e:
            print(f"[Compaction] Failed: {e}")
            # Clean up temporary file if it exists
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass

    def _compaction_loop(self):
        """Background thread that periodically checks and performs compaction."""
        print(f"[Compaction] Background compaction enabled (check interval: {Config.COMPACTION_INTERVAL}s, threshold: {Config.COMPACTION_THRESHOLD*100}%)")
        
        while self.running:
            # Wait for interval or stop event
            if self._stop_event.wait(Config.COMPACTION_INTERVAL):
                break  # Stop event set
            
            if not self.running:
                break
            
            try:
                if self._should_compact():
                    self._compact()
            except Exception as e:
                print(f"[Compaction] Error in compaction loop: {e}")

    def __del__(self):
        """Destructor to ensure lock is released even if close() not called."""
        try:
            # Try to release lock if it exists
            if hasattr(self, 'lockfile_path') and hasattr(self, 'running'):
                if self.running:
                    # close() wasn't called, do cleanup
                    self.close()
        except Exception:
            # Ignore errors during cleanup
            pass

    def close(self):
        """Clean shutdown."""
        if not self.running:
            return  # Already closed
            
        self.running = False
        self._stop_event.set()  # Wake up the checkpoint thread immediately
        self.checkpoint_thread.join(timeout=1)  # Wait max 1 second

        # Stop replication if enabled
        if self.replicator:
            self.replicator.stop()
            self.replica_manager.stop_health_monitoring()

        self.index.save()
        self.wal.close()
        self.data_file.close()
        
        # Release directory lock
        self._release_lock()

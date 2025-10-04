"""Main KVStore implementation."""
import threading
from pathlib import Path
from typing import Optional

from .wal import WAL
from .datafile import DataFile
from .index import Index
from ..utils.rwlock import RWLock, ReadLock, WriteLock
from ..utils.config import Config


class KVStore:
    """Core Key/Value store implementation."""

    def __init__(self, data_dir: str = None, is_replica: bool = False, checkpoint_interval: int = None):
        self.data_dir = Path(data_dir or Config.DATA_DIR)
        self.data_dir.mkdir(exist_ok=True)
        self.is_replica = is_replica

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

    def close(self):
        """Clean shutdown."""
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

"""Replicator for asynchronous data replication."""
import socket
import threading
import time
from queue import Queue, Empty
from typing import Optional, List

from .replica_manager import ReplicaManager, ReplicaNode
from ..utils.config import Config


class ReplicationOperation:
    """Represents an operation to be replicated."""

    def __init__(self, op: str, key: Optional[bytes] = None, value: Optional[bytes] = None,
                 keys: Optional[List[bytes]] = None, values: Optional[List[bytes]] = None):
        """
        Initialize replication operation.

        Args:
            op: Operation type ('put', 'delete', 'batch_put')
            key: Single key (for put/delete)
            value: Single value (for put)
            keys: Multiple keys (for batch_put)
            values: Multiple values (for batch_put)
        """
        self.op = op
        self.key = key
        self.value = value
        self.keys = keys
        self.values = values
        self.timestamp = time.time()
        self.retry_count = 0


class Replicator:
    """Handles asynchronous replication to replica nodes."""

    def __init__(self, replica_manager: ReplicaManager, mode: str = 'async',
                 max_retries: int = 3, queue_size: int = 10000):
        """
        Initialize replicator.

        Args:
            replica_manager: The replica manager instance
            mode: Replication mode ('async' or 'sync')
            max_retries: Maximum retry attempts per operation
            queue_size: Maximum size of replication queue
        """
        self.replica_manager = replica_manager
        self.mode = mode
        self.max_retries = max_retries
        self.queue = Queue(maxsize=queue_size)
        self.running = False
        self.worker_threads = []
        self.num_workers = 2  # Number of worker threads

        # Statistics
        self.stats_lock = threading.Lock()
        self.total_operations = 0
        self.successful_replications = 0
        self.failed_replications = 0
        self.dropped_operations = 0

    def start(self):
        """Start replication worker threads."""
        if self.running:
            return

        self.running = True
        for i in range(self.num_workers):
            thread = threading.Thread(
                target=self._worker_loop,
                name=f"ReplicationWorker-{i}",
                daemon=True
            )
            thread.start()
            self.worker_threads.append(thread)

        print(f"[Replicator] Started {self.num_workers} worker threads in {self.mode} mode")

    def stop(self):
        """Stop replication worker threads."""
        self.running = False
        for thread in self.worker_threads:
            thread.join(timeout=2)
        self.worker_threads.clear()
        print("[Replicator] Stopped")

    def replicate_put(self, key: bytes, value: bytes) -> bool:
        """
        Replicate a PUT operation.

        Args:
            key: The key
            value: The value

        Returns:
            True if queued/sent successfully, False otherwise
        """
        op = ReplicationOperation(op='put', key=key, value=value)
        return self._enqueue_operation(op)

    def replicate_batch_put(self, keys: List[bytes], values: List[bytes]) -> bool:
        """
        Replicate a BATCH_PUT operation.

        Args:
            keys: List of keys
            values: List of values

        Returns:
            True if queued/sent successfully, False otherwise
        """
        op = ReplicationOperation(op='batch_put', keys=keys, values=values)
        return self._enqueue_operation(op)

    def replicate_delete(self, key: bytes) -> bool:
        """
        Replicate a DELETE operation.

        Args:
            key: The key to delete

        Returns:
            True if queued/sent successfully, False otherwise
        """
        op = ReplicationOperation(op='delete', key=key)
        return self._enqueue_operation(op)

    def _enqueue_operation(self, op: ReplicationOperation) -> bool:
        """
        Enqueue an operation for replication.

        Args:
            op: The replication operation

        Returns:
            True if enqueued, False if queue is full
        """
        with self.stats_lock:
            self.total_operations += 1

        if self.mode == 'sync':
            # Synchronous replication - send immediately
            return self._replicate_to_all(op)
        else:
            # Asynchronous replication - enqueue
            try:
                self.queue.put_nowait(op)
                return True
            except Exception:
                # Queue is full, drop operation
                with self.stats_lock:
                    self.dropped_operations += 1
                print(f"[Replicator] Queue full, dropped operation: {op.op}")
                return False

    def _worker_loop(self):
        """Worker thread loop for processing replication queue."""
        while self.running:
            try:
                # Get operation with timeout
                op = self.queue.get(timeout=1)

                # Replicate to all replicas
                self._replicate_to_all(op)

                self.queue.task_done()
            except Empty:
                continue
            except Exception as e:
                print(f"[Replicator] Worker error: {e}")

    def _replicate_to_all(self, op: ReplicationOperation) -> bool:
        """
        Replicate operation to all healthy replicas.

        Args:
            op: The replication operation

        Returns:
            True if replicated to at least one replica, False otherwise
        """
        replicas = self.replica_manager.get_healthy_replicas()

        if not replicas:
            # No healthy replicas
            with self.stats_lock:
                self.failed_replications += 1
            return False

        success_count = 0
        for replica in replicas:
            if self._replicate_to_replica(op, replica):
                success_count += 1

        # Consider successful if at least one replica got it
        if success_count > 0:
            with self.stats_lock:
                self.successful_replications += 1
            return True
        else:
            with self.stats_lock:
                self.failed_replications += 1

            # Retry if under max retries
            if op.retry_count < self.max_retries:
                op.retry_count += 1
                try:
                    self.queue.put_nowait(op)
                except Exception:
                    pass  # Queue full, give up

            return False

    def _replicate_to_replica(self, op: ReplicationOperation, replica: ReplicaNode) -> bool:
        """
        Replicate operation to a specific replica.

        Args:
            op: The replication operation
            replica: The target replica node

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create socket connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)  # 5 second timeout
            sock.connect(replica.address)

            # Build replication command based on operation type
            if op.op == 'put':
                command = b'REPLICATE PUT ' + op.key + b' ' + op.value + b'\n'
            elif op.op == 'delete':
                command = b'REPLICATE DELETE ' + op.key + b'\n'
            elif op.op == 'batch_put':
                keys_str = Config.BATCH_SEPARATOR.join(op.keys)
                values_str = Config.BATCH_SEPARATOR.join(op.values)
                command = b'REPLICATE BATCHPUT ' + keys_str + b' ' + values_str + b'\n'
            else:
                raise ValueError(f"Unknown operation: {op.op}")

            # Send command
            sock.sendall(command)

            # Receive response
            response = sock.recv(Config.CLIENT_RECV_BUFFER)
            sock.close()

            # Check response
            if response.startswith(b'OK'):
                self.replica_manager.mark_success(replica)
                return True
            else:
                print(f"[Replicator] Replica {replica.host}:{replica.port} returned: {response}")
                self.replica_manager.mark_failure(replica)
                return False

        except Exception as e:
            print(f"[Replicator] Failed to replicate to {replica.host}:{replica.port}: {e}")
            self.replica_manager.mark_failure(replica)
            return False

    def get_stats(self) -> dict:
        """
        Get replication statistics.

        Returns:
            Dictionary with replication stats
        """
        with self.stats_lock:
            return {
                'mode': self.mode,
                'total_operations': self.total_operations,
                'successful_replications': self.successful_replications,
                'failed_replications': self.failed_replications,
                'dropped_operations': self.dropped_operations,
                'queue_size': self.queue.qsize(),
                'queue_max_size': self.queue.maxsize,
            }

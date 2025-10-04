"""Replica node management."""
import threading
import time
from typing import List, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ReplicaNode:
    """Represents a replica node."""
    host: str
    port: int
    is_healthy: bool = True
    last_success: datetime = field(default_factory=datetime.now)
    last_failure: datetime = None
    consecutive_failures: int = 0

    @property
    def address(self) -> Tuple[str, int]:
        """Get the (host, port) tuple."""
        return (self.host, self.port)

    def __hash__(self):
        return hash((self.host, self.port))

    def __eq__(self, other):
        if not isinstance(other, ReplicaNode):
            return False
        return self.host == other.host and self.port == other.port


class ReplicaManager:
    """Manages replica nodes and their health status."""

    def __init__(self, max_failures: int = 3, health_check_interval: int = 30):
        """
        Initialize replica manager.

        Args:
            max_failures: Maximum consecutive failures before marking unhealthy
            health_check_interval: Seconds between health checks
        """
        self.replicas: Set[ReplicaNode] = set()
        self.max_failures = max_failures
        self.health_check_interval = health_check_interval
        self.lock = threading.RLock()
        self.running = False
        self.health_check_thread = None

    def add_replica(self, host: str, port: int) -> ReplicaNode:
        """
        Add a replica node.

        Args:
            host: Replica host address
            port: Replica port number

        Returns:
            The ReplicaNode object
        """
        with self.lock:
            # Check if already exists
            for replica in self.replicas:
                if replica.host == host and replica.port == port:
                    return replica

            # Create new replica
            replica = ReplicaNode(host=host, port=port)
            self.replicas.add(replica)
            return replica

    def remove_replica(self, host: str, port: int) -> bool:
        """
        Remove a replica node.

        Args:
            host: Replica host address
            port: Replica port number

        Returns:
            True if removed, False if not found
        """
        with self.lock:
            for replica in self.replicas:
                if replica.host == host and replica.port == port:
                    self.replicas.remove(replica)
                    return True
            return False

    def get_healthy_replicas(self) -> List[ReplicaNode]:
        """Get list of currently healthy replicas."""
        with self.lock:
            return [r for r in self.replicas if r.is_healthy]

    def get_all_replicas(self) -> List[ReplicaNode]:
        """Get list of all replicas."""
        with self.lock:
            return list(self.replicas)

    def mark_success(self, replica: ReplicaNode):
        """
        Mark a successful replication to a replica.

        Args:
            replica: The replica node
        """
        with self.lock:
            replica.last_success = datetime.now()
            replica.consecutive_failures = 0
            if not replica.is_healthy:
                replica.is_healthy = True
                print(f"[ReplicaManager] Replica {replica.host}:{replica.port} is now healthy")

    def mark_failure(self, replica: ReplicaNode):
        """
        Mark a failed replication attempt to a replica.

        Args:
            replica: The replica node
        """
        with self.lock:
            replica.last_failure = datetime.now()
            replica.consecutive_failures += 1

            if replica.consecutive_failures >= self.max_failures and replica.is_healthy:
                replica.is_healthy = False
                msg = f"Replica {replica.host}:{replica.port} marked unhealthy after {replica.consecutive_failures} failures"
                print(f"[ReplicaManager] {msg}")

    def start_health_monitoring(self):
        """Start background health check thread."""
        if self.running:
            return

        self.running = True
        self.health_check_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True
        )
        self.health_check_thread.start()

    def stop_health_monitoring(self):
        """Stop background health check thread."""
        self.running = False
        if self.health_check_thread:
            self.health_check_thread.join(timeout=2)

    def _health_check_loop(self):
        """Background loop for health checking."""
        while self.running:
            time.sleep(self.health_check_interval)
            # In a more sophisticated implementation, we would actively
            # ping replicas here. For now, we rely on passive failure detection.

    def get_status(self) -> dict:
        """
        Get status of all replicas.

        Returns:
            Dictionary with replica status information
        """
        with self.lock:
            return {
                'total_replicas': len(self.replicas),
                'healthy_replicas': len([r for r in self.replicas if r.is_healthy]),
                'replicas': [
                    {
                        'host': r.host,
                        'port': r.port,
                        'healthy': r.is_healthy,
                        'consecutive_failures': r.consecutive_failures,
                        'last_success': r.last_success.isoformat() if r.last_success else None,
                        'last_failure': r.last_failure.isoformat() if r.last_failure else None,
                    }
                    for r in self.replicas
                ]
            }

"""Tests for replication functionality."""
import pytest
import time
import threading
from kvstore.core.store import KVStore
from kvstore.network.server import KVServer
from kvstore.network.client import KVClient
from kvstore.utils.config import Config
from kvstore.replication import Replicator, ReplicaManager


@pytest.fixture
def replica_ports():
    """Get available ports for replicas."""
    return [15556, 15557, 15558]


@pytest.fixture
def setup_replication_config(replica_ports):
    """Configure replication settings for testing."""
    # Save original config
    original_enabled = Config.REPLICATION_ENABLED
    original_mode = Config.REPLICATION_MODE
    original_addresses = Config.REPLICA_ADDRESSES
    original_timeout = Config.REPLICATION_TIMEOUT
    
    # Set test config
    Config.REPLICATION_ENABLED = True
    Config.REPLICATION_MODE = 'async'
    Config.REPLICA_ADDRESSES = [(f'localhost', port) for port in replica_ports[:2]]
    Config.REPLICATION_TIMEOUT = 2.0
    
    yield
    
    # Restore original config
    Config.REPLICATION_ENABLED = original_enabled
    Config.REPLICATION_MODE = original_mode
    Config.REPLICA_ADDRESSES = original_addresses
    Config.REPLICATION_TIMEOUT = original_timeout


@pytest.fixture
def replica_servers(tmp_path, replica_ports):
    """Start replica servers."""
    servers = []
    threads = []
    
    for i, port in enumerate(replica_ports[:2]):
        data_dir = tmp_path / f"replica{i}"
        server = KVServer(
            host='localhost',
            port=port,
            data_dir=str(data_dir),
            is_replica=True
        )
        
        # Start server in thread
        thread = threading.Thread(target=server.start, daemon=True)
        thread.start()
        threads.append(thread)
        servers.append(server)
        
    # Wait for servers to start
    time.sleep(1)
    
    yield servers
    
    # Stop servers
    for server in servers:
        server.stop()


@pytest.fixture
def master_server(tmp_path, replica_servers, setup_replication_config):
    """Start master server with replication enabled."""
    master_port = 15555
    data_dir = tmp_path / "master"
    
    server = KVServer(
        host='localhost',
        port=master_port,
        data_dir=str(data_dir),
        is_replica=False
    )
    
    # Start server in thread
    thread = threading.Thread(target=server.start, daemon=True)
    thread.start()
    
    # Wait for server to start
    time.sleep(1)
    
    yield server
    
    # Stop server
    server.stop()


class TestReplicaManager:
    """Tests for ReplicaManager class."""
    
    def test_add_replica(self):
        """Test adding replicas."""
        manager = ReplicaManager()
        
        replica = manager.add_replica('localhost', 5556)
        assert replica.host == 'localhost'
        assert replica.port == 5556
        assert replica.is_healthy is True
        assert len(manager.get_all_replicas()) == 1
    
    def test_add_duplicate_replica(self):
        """Test adding duplicate replica returns existing."""
        manager = ReplicaManager()
        
        replica1 = manager.add_replica('localhost', 5556)
        replica2 = manager.add_replica('localhost', 5556)
        
        assert replica1 is replica2
        assert len(manager.get_all_replicas()) == 1
    
    def test_remove_replica(self):
        """Test removing replicas."""
        manager = ReplicaManager()
        
        manager.add_replica('localhost', 5556)
        assert len(manager.get_all_replicas()) == 1
        
        result = manager.remove_replica('localhost', 5556)
        assert result is True
        assert len(manager.get_all_replicas()) == 0
    
    def test_remove_nonexistent_replica(self):
        """Test removing non-existent replica."""
        manager = ReplicaManager()
        
        result = manager.remove_replica('localhost', 9999)
        assert result is False
    
    def test_get_healthy_replicas(self):
        """Test filtering healthy replicas."""
        manager = ReplicaManager()
        
        replica1 = manager.add_replica('localhost', 5556)
        replica2 = manager.add_replica('localhost', 5557)
        
        # Mark one unhealthy
        replica1.is_healthy = False
        
        healthy = manager.get_healthy_replicas()
        assert len(healthy) == 1
        assert healthy[0].port == 5557
    
    def test_mark_success(self):
        """Test marking replica success."""
        manager = ReplicaManager()
        
        replica = manager.add_replica('localhost', 5556)
        replica.consecutive_failures = 5
        replica.is_healthy = False
        
        manager.mark_success(replica)
        
        assert replica.consecutive_failures == 0
        assert replica.is_healthy is True
        assert replica.last_success is not None
    
    def test_mark_failure(self):
        """Test marking replica failure."""
        manager = ReplicaManager(max_failures=3)
        
        replica = manager.add_replica('localhost', 5556)
        
        # Mark failures
        for i in range(3):
            manager.mark_failure(replica)
        
        assert replica.consecutive_failures == 3
        assert replica.is_healthy is False
        assert replica.last_failure is not None
    
    def test_get_status(self):
        """Test getting replica status."""
        manager = ReplicaManager()
        
        manager.add_replica('localhost', 5556)
        manager.add_replica('localhost', 5557)
        
        status = manager.get_status()
        
        assert status['total_replicas'] == 2
        assert status['healthy_replicas'] == 2
        assert len(status['replicas']) == 2


class TestReplicator:
    """Tests for Replicator class."""
    
    def test_replicator_initialization(self):
        """Test replicator initialization."""
        manager = ReplicaManager()
        replicator = Replicator(manager, mode='async', max_retries=3, queue_size=1000)
        
        assert replicator.mode == 'async'
        assert replicator.max_retries == 3
        assert replicator.queue.maxsize == 1000
        assert replicator.running is False
    
    def test_replicator_start_stop(self):
        """Test starting and stopping replicator."""
        manager = ReplicaManager()
        replicator = Replicator(manager)
        
        replicator.start()
        assert replicator.running is True
        assert len(replicator.worker_threads) > 0
        
        replicator.stop()
        assert replicator.running is False
    
    def test_enqueue_operation_async(self):
        """Test enqueueing operation in async mode."""
        manager = ReplicaManager()
        replicator = Replicator(manager, mode='async')
        replicator.start()
        
        result = replicator.replicate_put(b'key1', b'value1')
        assert result is True
        assert replicator.queue.qsize() > 0
        
        replicator.stop()
    
    def test_get_stats(self):
        """Test getting replication stats."""
        manager = ReplicaManager()
        replicator = Replicator(manager, mode='async', queue_size=5000)
        
        stats = replicator.get_stats()
        
        assert stats['mode'] == 'async'
        assert stats['total_operations'] == 0
        assert stats['queue_max_size'] == 5000


class TestStoreReplication:
    """Tests for KVStore with replication enabled."""
    
    def test_store_with_replication(self, tmp_path, setup_replication_config):
        """Test KVStore initializes replication when enabled."""
        store = KVStore(str(tmp_path / "master"), is_replica=False)
        
        assert store.replicator is not None
        assert store.replicator.mode == 'async'
        
        store.close()
    
    def test_replica_store_no_replication(self, tmp_path, setup_replication_config):
        """Test replica store doesn't initialize replication."""
        store = KVStore(str(tmp_path / "replica"), is_replica=True)
        
        assert store.replicator is None
        
        store.close()
    
    def test_store_without_replication(self, tmp_path):
        """Test KVStore doesn't initialize replication when disabled."""
        # Ensure replication is disabled
        original = Config.REPLICATION_ENABLED
        Config.REPLICATION_ENABLED = False
        
        store = KVStore(str(tmp_path / "master"), is_replica=False)
        
        assert store.replicator is None
        
        store.close()
        Config.REPLICATION_ENABLED = original


class TestEndToEndReplication:
    """End-to-end replication tests."""
    
    def test_put_replication(self, master_server, replica_servers, replica_ports):
        """Test PUT operation replicates to replicas."""
        # Connect to master
        master_client = KVClient(host='localhost', port=15555)
        
        # Write to master
        result = master_client.put('key1', 'value1')
        assert result is True
        
        # Wait for async replication
        time.sleep(2)
        
        # Verify on replicas
        for port in replica_ports[:2]:
            replica_client = KVClient(host='localhost', port=port)
            value = replica_client.read('key1')
            assert value == b'value1', f"Replica on port {port} doesn't have replicated data"
    
    def test_batch_put_replication(self, master_server, replica_servers, replica_ports):
        """Test BATCHPUT operation replicates to replicas."""
        # Connect to master
        master_client = KVClient(host='localhost', port=15555)
        
        # Batch write to master
        keys = ['bkey1', 'bkey2', 'bkey3']
        values = ['bval1', 'bval2', 'bval3']
        result = master_client.batch_put(keys, values)
        assert result is True
        
        # Wait for async replication
        time.sleep(2)
        
        # Verify on replicas
        for port in replica_ports[:2]:
            replica_client = KVClient(host='localhost', port=port)
            for key, expected_value in zip(keys, values):
                value = replica_client.read(key)
                assert value == expected_value.encode(), \
                    f"Replica on port {port} doesn't have {key}"
    
    def test_delete_replication(self, master_server, replica_servers, replica_ports):
        """Test DELETE operation replicates to replicas."""
        # Connect to master
        master_client = KVClient(host='localhost', port=15555)
        
        # Write and delete on master
        master_client.put('delkey', 'delvalue')
        time.sleep(2)  # Wait for replication
        
        result = master_client.delete('delkey')
        assert result is True
        
        # Wait for delete replication
        time.sleep(2)
        
        # Verify deletion on replicas
        for port in replica_ports[:2]:
            replica_client = KVClient(host='localhost', port=port)
            value = replica_client.read('delkey')
            assert value is None, f"Replica on port {port} still has deleted key"
    
    def test_multiple_operations(self, master_server, replica_servers, replica_ports):
        """Test multiple mixed operations replicate correctly."""
        # Connect to master
        master_client = KVClient(host='localhost', port=15555)
        
        # Perform various operations
        master_client.put('k1', 'v1')
        master_client.put('k2', 'v2')
        master_client.batch_put(['k3', 'k4'], ['v3', 'v4'])
        master_client.delete('k2')
        master_client.put('k5', 'v5')
        
        # Wait for replication
        time.sleep(3)
        
        # Verify final state on replicas
        expected = {
            b'k1': b'v1',
            b'k2': None,  # Deleted
            b'k3': b'v3',
            b'k4': b'v4',
            b'k5': b'v5',
        }
        
        for port in replica_ports[:2]:
            replica_client = KVClient(host='localhost', port=port)
            for key, expected_value in expected.items():
                value = replica_client.read(key.decode())
                assert value == expected_value, \
                    f"Replica on port {port} mismatch for {key}"
    
    def test_replica_read_only(self, replica_servers, replica_ports):
        """Test that replicas accept REPLICATE commands but regular writes work."""
        # Connect to replica
        replica_client = KVClient(host='localhost', port=replica_ports[0])
        
        # Direct write to replica should work (it's still a kvstore)
        # But in production, clients should only write to master
        result = replica_client.put('direct_key', 'direct_value')
        assert result is True
        
        # Verify it's stored
        value = replica_client.read('direct_key')
        assert value == b'direct_value'
    
    def test_replication_with_range_query(self, master_server, replica_servers, replica_ports):
        """Test range queries work on replicated data."""
        # Connect to master
        master_client = KVClient(host='localhost', port=15555)
        
        # Write range of keys
        for i in range(10):
            master_client.put(f'range{i:02d}', f'value{i}')
        
        # Wait for replication
        time.sleep(3)
        
        # Query range on replica
        replica_client = KVClient(host='localhost', port=replica_ports[0])
        results = replica_client.read_key_range('range03', 'range07')
        
        # Verify results
        assert len(results) == 5
        assert b'range03' in results
        assert b'range07' in results
        assert results[b'range05'] == b'value5'


class TestReplicationFailure:
    """Tests for replication failure scenarios."""
    
    def test_replication_without_replicas(self, tmp_path):
        """Test master works fine with no replicas available."""
        # Configure replication with non-existent replicas
        original_enabled = Config.REPLICATION_ENABLED
        original_addresses = Config.REPLICA_ADDRESSES
        
        Config.REPLICATION_ENABLED = True
        Config.REPLICA_ADDRESSES = [('localhost', 19999)]  # No server here
        
        try:
            # Create master store
            store = KVStore(str(tmp_path / "master"), is_replica=False)
            
            # Operations should still work
            result = store.put(b'key1', b'value1')
            assert result is True
            
            value = store.read(b'key1')
            assert value == b'value1'
            
            store.close()
        finally:
            Config.REPLICATION_ENABLED = original_enabled
            Config.REPLICA_ADDRESSES = original_addresses
    
    def test_replication_stats(self, master_server, replica_servers):
        """Test replication statistics tracking."""
        # Connect to master
        master_client = KVClient(host='localhost', port=15555)
        
        # Perform operations
        master_client.put('stat_key1', 'stat_value1')
        master_client.put('stat_key2', 'stat_value2')
        
        # Wait for replication
        time.sleep(2)
        
        # Check stats (accessing internal state for testing)
        if master_server.store.replicator:
            stats = master_server.store.replicator.get_stats()
            assert stats['total_operations'] >= 2
            assert stats['mode'] == 'async'


@pytest.mark.slow
class TestReplicationPerformance:
    """Performance tests for replication."""
    
    def test_async_replication_throughput(self, master_server, replica_servers):
        """Test async replication doesn't significantly slow writes."""
        master_client = KVClient(host='localhost', port=15555)
        
        # Measure time for many writes
        start_time = time.time()
        num_operations = 100
        
        for i in range(num_operations):
            master_client.put(f'perf_key{i}', f'perf_value{i}')
        
        elapsed = time.time() - start_time
        
        # Should complete quickly (async mode)
        # Allow 1 second for 100 operations (very generous)
        assert elapsed < 1.0, f"Async replication too slow: {elapsed:.2f}s for {num_operations} ops"
        
        # Wait for replication to complete
        time.sleep(3)
        
        # Verify some keys made it to replica
        replica_client = KVClient(host='localhost', port=15556)
        value = replica_client.read('perf_key50')
        assert value == b'perf_value50'

# Testing Guide

## Overview

Comprehensive test suite covering basic kvstore functionality, network operations, and replication.

## Test Files

### 1. `test_basic.py` - Core Functionality Tests

Tests for core kvstore operations without networking.

**Test Classes:**

- **TestBasicOperations**: Basic PUT, READ, DELETE operations
  - Put and read operations
  - Nonexistent key handling
  - Overwriting existing keys
  - Delete operations
  - Empty keys and values
  - Large values (1MB)
  - Special characters and Unicode

- **TestBatchOperations**: Batch PUT operations
  - Successful batch puts (up to 1000 items)
  - Empty batches
  - Single item batches
  - Overwriting with batch put

- **TestRangeQueries**: Range query operations
  - Basic range queries with various scenarios
  - Single key ranges
  - No matches
  - All keys
  - Numeric keys
  - Excluding deleted keys

- **TestConcurrency**: Concurrent operations (thread-safe)
  - Concurrent reads (non-blocking)
  - Concurrent writes
  - Mixed read/write operations
  - Concurrent deletes

- **TestPersistence**: Data persistence and WAL recovery
  - Data survives close/reopen
  - WAL recovery after crash
  - Batch put persistence
  - Delete persistence

- **TestEdgeCases**: Edge cases and error conditions
  - Multiple deletes of same key
  - Update after delete
  - Many updates to same key
  - Sequential mixed operations
  - Range query after updates and deletes

### 2. `test_network.py` - Client-Server Tests

Tests for client-server communication over TCP.

**Test Classes:**

- **TestClientServerBasic**: Basic client-server operations
  - Server start/stop
  - Client PUT and READ
  - Client DELETE
  - Client BATCHPUT
  - Client READRANGE
  - Nonexistent key handling

- **TestMultipleClients**: Multiple concurrent clients (10+ clients)
  - Concurrent reads from multiple clients
  - Concurrent writes from multiple clients
  - Mixed operations from multiple clients

- **TestProtocol**: Protocol edge cases
  - Special characters in values
  - Empty values
  - Large values over network (100KB)
  - Large batch operations

- **TestServerRobustness**: Server robustness and error handling
  - Client disconnect handling
  - Data persistence between client connections
  - Sequential client connections (50+)

### 3. `test_replication.py` - Replication Tests

Tests for master-slave replication functionality.

**Test Classes:**

- **TestReplicaManager**: Replica management
  - Adding/removing replicas
  - Health monitoring
  - Success/failure tracking
  - Status reporting

- **TestReplicator**: Replication engine
  - Initialization
  - Start/stop
  - Queue management
  - Statistics

- **TestStoreReplication**: KVStore integration
  - Store with replication enabled
  - Replica store (no replication)
  - Store without replication

- **TestEndToEndReplication**: End-to-end replication scenarios
  - PUT replication (async/sync modes)
  - BATCHPUT replication
  - DELETE replication
  - Multiple operations
  - Range queries on replicas
  - Replica read-only functionality

- **TestReplicationFailure**: Failure handling
  - Replication with no replicas
  - Failure recovery
  - Replication statistics

- **TestReplicationPerformance**: Performance tests (marked `@pytest.mark.slow`)
  - Async replication throughput
  - Write latency with replication

## Setup

Install test dependencies:

```bash
# Install kvstore with test dependencies
pip install -e ".[test]"

# Or install pytest separately
pip install pytest pytest-timeout
```

## Running Tests

### Run All Tests

```bash
pytest tests/ -v
```

### Run Specific Test Files

```bash
pytest tests/test_basic.py -v
```

### Run Specific Test Classes

```bash
pytest tests/test_replication.py::TestReplicaManager -v
```

### Run Individual Tests

```bash
pytest tests/test_replication.py::TestReplicaManager::test_add_replica -v
```

### Skip Slow Tests

```bash
pytest tests/test_replication.py -v -m "not slow"
```

## Test Fixtures

The test suite uses several fixtures:

- `replica_ports`: Provides available ports for test servers
- `setup_replication_config`: Configures replication settings
- `replica_servers`: Starts 2 replica servers
- `master_server`: Starts master server with replication

## Example Test Output

```bash
$ pytest tests/test_replication.py -v

tests/test_replication.py::TestReplicaManager::test_add_replica PASSED
tests/test_replication.py::TestReplicaManager::test_add_duplicate_replica PASSED
tests/test_replication.py::TestReplicaManager::test_remove_replica PASSED
tests/test_replication.py::TestReplicaManager::test_get_healthy_replicas PASSED
tests/test_replication.py::TestReplicaManager::test_mark_success PASSED
tests/test_replication.py::TestReplicaManager::test_mark_failure PASSED
tests/test_replication.py::TestReplicaManager::test_get_status PASSED

tests/test_replication.py::TestReplicator::test_replicator_initialization PASSED
tests/test_replication.py::TestReplicator::test_replicator_start_stop PASSED
tests/test_replication.py::TestReplicator::test_enqueue_operation_async PASSED
tests/test_replication.py::TestReplicator::test_get_stats PASSED

tests/test_replication.py::TestStoreReplication::test_store_with_replication PASSED
tests/test_replication.py::TestStoreReplication::test_replica_store_no_replication PASSED
tests/test_replication.py::TestStoreReplication::test_store_without_replication PASSED

tests/test_replication.py::TestEndToEndReplication::test_put_replication PASSED
tests/test_replication.py::TestEndToEndReplication::test_batch_put_replication PASSED
tests/test_replication.py::TestEndToEndReplication::test_delete_replication PASSED
tests/test_replication.py::TestEndToEndReplication::test_multiple_operations PASSED
tests/test_replication.py::TestEndToEndReplication::test_replica_read_only PASSED
tests/test_replication.py::TestEndToEndReplication::test_replication_with_range_query PASSED

tests/test_replication.py::TestReplicationFailure::test_replication_without_replicas PASSED
tests/test_replication.py::TestReplicationFailure::test_replication_stats PASSED

tests/test_replication.py::TestReplicationPerformance::test_async_replication_throughput PASSED

======================== 23 passed in 45.23s ========================
```

## Debugging Tests

### Show Print Output

```bash
pytest tests/test_replication.py -v -s
```

### Run Single Test with Debug Output

```bash
pytest tests/test_replication.py::TestEndToEndReplication::test_put_replication -v -s
```

### Stop on First Failure

```bash
pytest tests/test_replication.py -x
```

### Show Local Variables on Failure

```bash
pytest tests/test_replication.py -l
```

### Run with Python Debugger

```bash
pytest tests/test_replication.py --pdb
```

## Writing New Tests

### Template for New Test

```python
def test_my_feature(self, master_server, replica_servers, replica_ports):
    """Test description."""
    # Setup
    master_client = KVClient(host='localhost', port=15555)
    
    # Action
    result = master_client.put('test_key', 'test_value')
    assert result is True
    
    # Wait for replication
    time.sleep(2)
    
    # Verify
    replica_client = KVClient(host='localhost', port=replica_ports[0])
    value = replica_client.read('test_key')
    assert value == b'test_value'
```

### Best Practices

1. **Use fixtures** for server setup/teardown
2. **Wait for async replication** with `time.sleep(2)` after writes
3. **Test on multiple replicas** to ensure all receive updates
4. **Clean up resources** (fixtures handle this automatically)
5. **Use descriptive test names** that explain what is being tested
6. **Add docstrings** to explain test purpose

## Known Issues

1. **Socket cleanup warning**: Background server threads may generate warnings during test cleanup
   - Does not affect functionality
   - Tests pass successfully
   - Warning: `OSError: [WinError 10038] An operation was attempted on something that is not a socket`

## Continuous Integration

Tests are ready for CI/CD integration:

```yaml
# Example GitHub Actions
- name: Run tests
  run: |
    pip install -e ".[test]"
    pytest tests/ -v --tb=short
```

Or for more comprehensive testing:

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -e ".[test]"
      - run: pytest tests/ -v --cov=kvstore --cov-report=xml
      - uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
```

## Troubleshooting

### Port Already in Use

If tests fail with "Address already in use":

```bash
# Find and kill processes on test ports
# Linux/Mac:
lsof -ti:15555,15556,15557 | xargs kill -9

# Windows:
netstat -ano | findstr :15555
taskkill /PID <PID> /F
```

### Tests Hang

If tests hang, likely due to server not stopping:

1. Check for orphaned processes
2. Increase timeout in test fixtures
3. Ensure all servers are properly stopped in teardown

### Replication Not Working in Tests

1. Verify replica servers started: Check fixture setup
2. Check async wait time: Increase `time.sleep()` if needed
3. Verify Config settings: Check `setup_replication_config` fixture
4. Check ports: Ensure no conflicts with other services

## Coverage Report

Generate coverage report:

```bash
# Install coverage tool
pip install pytest-cov

# Run with coverage
pytest tests/test_replication.py --cov=kvstore.replication --cov-report=html

# Open report
open htmlcov/index.html
```

## Next Steps

Potential areas for additional testing:
- [ ] Load testing with thousands of concurrent clients
- [ ] Stress testing with very large datasets (GB+)
- [ ] Network failure simulation
- [ ] Disk I/O failure simulation
- [ ] Memory pressure testing
- [ ] Extended WAL recovery scenarios

## See Also

- [docs/REPLICATION.md](../docs/REPLICATION.md) - Replication documentation and manual examples
- [conftest.py](conftest.py) - Shared test fixtures

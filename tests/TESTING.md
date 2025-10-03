# Testing Guide

## Setup

Install test dependencies:

```bash
# Install kvstore with test dependencies
pip install -e ".[test]"

# Or install pytest separately
pip install pytest pytest-timeout
```

## Running Tests

### Run All Replication Tests

```bash
# Run all tests with verbose output
pytest tests/test_replication.py -v

# Run with output shown
pytest tests/test_replication.py -v -s

# Run with coverage (if pytest-cov installed)
pytest tests/test_replication.py --cov=kvstore.replication
```

### Run Specific Test Classes

```bash
# Test ReplicaManager functionality
pytest tests/test_replication.py::TestReplicaManager -v

# Test Replicator functionality
pytest tests/test_replication.py::TestReplicator -v

# Test KVStore with replication
pytest tests/test_replication.py::TestStoreReplication -v

# Test end-to-end replication scenarios
pytest tests/test_replication.py::TestEndToEndReplication -v

# Test failure scenarios
pytest tests/test_replication.py::TestReplicationFailure -v

# Test performance (marked as slow)
pytest tests/test_replication.py::TestReplicationPerformance -v
```

### Run Individual Tests

```bash
# Test adding replicas
pytest tests/test_replication.py::TestReplicaManager::test_add_replica -v

# Test PUT replication
pytest tests/test_replication.py::TestEndToEndReplication::test_put_replication -v

# Test BATCHPUT replication
pytest tests/test_replication.py::TestEndToEndReplication::test_batch_put_replication -v

# Test DELETE replication
pytest tests/test_replication.py::TestEndToEndReplication::test_delete_replication -v

# Test range query on replicas
pytest tests/test_replication.py::TestEndToEndReplication::test_replication_with_range_query -v
```

### Skip Slow Tests

```bash
# Skip performance tests (marked with @pytest.mark.slow)
pytest tests/test_replication.py -v -m "not slow"
```

## Test Categories

### 1. Unit Tests

Tests for individual components in isolation:

- **TestReplicaManager**: Tests replica management
  - Adding/removing replicas
  - Health monitoring
  - Success/failure tracking
  - Status reporting

- **TestReplicator**: Tests replication engine
  - Initialization
  - Start/stop
  - Queue management
  - Statistics

- **TestStoreReplication**: Tests KVStore integration
  - Replication initialization
  - Replica mode handling
  - Configuration handling

### 2. Integration Tests

Tests for complete workflows:

- **TestEndToEndReplication**: End-to-end scenarios
  - PUT replication
  - BATCHPUT replication
  - DELETE replication
  - Multiple operations
  - Range queries on replicas
  - Replica read functionality

- **TestReplicationFailure**: Failure scenarios
  - Replication with no replicas
  - Replication statistics

### 3. Performance Tests

Tests marked with `@pytest.mark.slow`:

- **TestReplicationPerformance**: Performance validation
  - Async replication throughput
  - Write latency with replication

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

## Continuous Integration

Add to CI pipeline:

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
      - run: pytest tests/test_replication.py -v
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

## See Also

- [docs/REPLICATION.md](../docs/REPLICATION.md) - Replication documentation and manual examples
- [conftest.py](conftest.py) - Shared test fixtures

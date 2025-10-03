# kvstore

A high-performance, thread-safe key-value store with Write-Ahead Logging (WAL), data replication, and network interface.

## Features

- **Thread-safe operations**: True concurrent reads with exclusive writes using Reader-Writer Lock
- **Two-phase locking**: Separate WAL lock prevents write starvation in read-heavy workloads
- **Write-Ahead Logging (WAL)**: Ensures durability and crash recovery
- **Data replication**: Master-slave replication with async/sync modes for high availability
- **In-memory indexing**: Fast lookups with periodic persistence
- **Background checkpointing**: Automatic index saves every 10 seconds
- **Network protocol**: Simple TCP-based text protocol
- **Batch operations**: Efficient bulk insertions with `batchput`
- **Range queries**: Retrieve multiple key-value pairs with `readrange`
- **Graceful shutdown**: Ctrl+C handling with proper cleanup
- **Concurrent reads**: Multiple clients can read simultaneously without blocking each other
- **Write optimization**: WAL writes don't wait for readers to finish
- **Configurable**: All hardcoded values moved to centralized Config class

## Install and run
From project root
```
pip install -e .
```

Option 1: Run standalone server without replication
```
python -m kvstore.cli.server_cli
```

Option 2: Run server with 2 replicas
```
# Start replicas first
python -m kvstore.cli.server_cli --port 5556 --data-dir ./replica1 --replica
python -m kvstore.cli.server_cli --port 5557 --data-dir ./replica2 --replica

# Start master
python -m kvstore.cli.server_cli --replicas localhost:5556,localhost:5557
```

Run client command
```
python -m kvstore.cli.client_cli put <key> <value>
python -m kvstore.cli.client_cli batchput <key1,key2,...> <val1,val2,...>
python -m kvstore.cli.client_cli read <key>
python -m kvstore.cli.client_cli readrange <start_key> <end_key>
python -m kvstore.cli.client_cli delete <key>
```

## Protocol

**Commands:**
- `PUT <key> <value>` - Store a key-value pair
- `BATCHPUT <key1,key2,...,keyN> <val1,val2,...,valN>` - Store multiple pairs
- `READ <key>` - Retrieve value for key
- `READRANGE <start_key> <end_key>` - Retrieve all keys in range [start, end]
- `DELETE <key>` - Remove key

**Responses:**
- `OK` - Operation successful
- `<value>` - Value for READ command
- set of `<key: value>` - Results for READRANGE
- `NOT_FOUND` - Key not found
- `ERROR: <message>` - Error occurred

## Configuration

All system parameters are centralized in `kvstore/utils/config.py`.
You can customize these values by importing and modifying the Config class before instantiating server/client objects.

See [CONFIGURATION.md](docs/CONFIGURATION.md) for detailed configuration options and examples.

## Replication

The kvstore supports master-slave replication for high availability and data redundancy. Features include:

- **Async/Sync Modes**: Choose between fast async replication or strong consistency with sync mode
- **Automatic Retry**: Failed replications are retried automatically
- **Health Monitoring**: Unhealthy replicas are detected and skipped
- **Simple Setup**: Configure replicas via CLI or Config class

See [REPLICATION.md](docs/REPLICATION.md) for detailed replication setup, configuration, and best practices.

## Kubernetes Deployment

Deploy kvstore on Kubernetes with automatic pod restart and high availability:

**Features:**
- **StatefulSets**: Stable network identities and persistent storage for each pod
- **Automatic Recovery**: Pods automatically restart on failure (~30-60s downtime)
- **Data Persistence**: PersistentVolumes preserve data across pod restarts
- **Service Discovery**: DNS-based pod-to-pod communication for replication
- **Health Monitoring**: Liveness and readiness probes detect failures
- **Manual Master Promotion**: ConfigMap-based master selection

See [KUBERNETES.md](docs/KUBERNETES.md) for complete deployment guide, architecture diagram, failover scenarios, and troubleshooting.

## Architecture

The architecture includes:

- **Core Layer**: KVStore, WAL, DataFile, Index, RWLock
- **Network Layer**: KVServer, KVClient, Protocol, ConnectionHandler
- **Replication Layer**: Replicator, ReplicaManager, ReplicaNode
- **Two-Phase Locking**: Separate WAL lock prevents write starvation

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture documentation, UML diagrams, and sequence diagrams for all operations.

## Testing

Comprehensive test suite with 50+ tests covering:

**Test Coverage:**
- ✅ Core operations (PUT, READ, DELETE, BATCHPUT, READRANGE)
- ✅ Concurrency (concurrent reads, writes, mixed operations)
- ✅ Persistence (WAL recovery, data durability)
- ✅ Network (client-server communication, multiple clients)
- ✅ Replication (master-slave, async/sync modes, failure handling)
- ✅ Edge cases (empty values, special characters, large data)

**Run Tests:**
```bash
# Install test dependencies
pip install -e ".[test]"

# Run all tests
python -m pytest tests/ -v

# Run specific test files
python -m pytest tests/test_basic.py -v        # Core functionality
python -m pytest tests/test_network.py -v      # Client-server
python -m pytest tests/test_replication.py -v  # Replication
```

See [tests/TESTING.md](tests/TESTING.md) for complete testing guide with detailed test coverage and usage examples.




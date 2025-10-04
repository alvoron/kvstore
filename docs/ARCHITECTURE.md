# Architecture Details

## Core Components

1. **KVStore**: Main store orchestrating WAL, DataFile, and Index
2. **WAL (Write-Ahead Log)**: Logs all write operations before applying them
3. **DataFile**: Append-only storage file for key-value pairs
4. **Index**: In-memory hash map for fast key lookups

## Locking Strategy

The system uses a sophisticated **three-phase locking strategy** to optimize performance:

### 1. Reader-Writer Lock (RWLock)
- **Read operations**: Multiple readers can acquire the lock simultaneously
- **Write operations**: Writers get exclusive access (no readers or other writers)
- **Use case**: Protects data file reads/writes and index updates

### 2. Separate WAL Lock
- **Independent locking**: WAL writes use a separate `threading.Lock()`
- **Problem solved**: In read-heavy workloads, writers would wait for all readers to finish before even logging to WAL
- **Benefit**: WAL writes can proceed immediately without waiting for readers

### 3. Async Replication (Non-blocking)
- **After local commit**: Replication happens asynchronously after WAL and index updates
- **Queue-based**: Operations are queued and processed by worker threads
- **Non-blocking**: Client receives response immediately, replication happens in background

### Write Operation Flow (Three-Phase):
```
Phase 1: Acquire wal_lock → Log to WAL → Release wal_lock
Phase 2: Acquire write_lock → Update DataFile & Index → Release write_lock
Phase 3: Enqueue to Replicator → Async replication to replicas
```

### Delete Operation Flow (Three-Phase with Optimization):
```
Phase 1: Acquire read_lock → Check existence → Release read_lock
Phase 2: Acquire wal_lock → Log to WAL → Release wal_lock
Phase 3: Acquire write_lock → Double-check & Update Index → Release write_lock
Phase 4: Enqueue to Replicator → Async replication to replicas
```

**Why this matters:**
- In a read-heavy workload, many readers might be active
- Without separate locks: Writer waits for readers → WAL logging delayed → Other writers blocked
- With separate locks: WAL logging proceeds immediately → Better write throughput
- Async replication: No impact on write latency, eventual consistency across replicas
- Durability preserved: WAL is written before data/index updates
- Delete optimization: Read lock first allows concurrent existence checks

## Network Components

1. **KVServer**: Multi-threaded TCP server handling client connections
2. **KVClient**: Client library for connecting to the server
3. **Protocol**: Message parsing and formatting
4. **ConnectionHandler**: Per-connection request handler

## Architecture Diagram

```mermaid
classDiagram
    %% CLI Layer
    class ClientCLI {
        +main()
        +handle_put(client, key, value)
        +handle_batchput(client, key, value)
        +handle_read(client, key, value)
        +handle_readrange(client, key, value)
        +handle_delete(client, key, value)
    }
    
    class ServerCLI {
        +main()
    }
    
    %% Network Layer
    class KVClient {
        -host: str
        -port: int
        -_send_command(command: bytes) bytes
        +put(key: str, value: str) bool
        +batch_put(keys: list, values: list) bool
        +read(key: str) Optional[str]
        +read_key_range(start_key: str, end_key: str) dict
        +delete(key: str) bool
    }
    
    class KVServer {
        -host: str
        -port: int
        -store: KVStore
        -server_socket: socket
        -protocol: Protocol
        -running: bool
        -is_replica: bool
        -_handle_replicate_put(key, value) bytes
        -_handle_replicate_batchput(key, value) bytes
        -_handle_replicate_delete(key) bytes
        -_handle_put(key, value) bytes
        -_handle_batchput(key, value) bytes
        -_handle_read(key) bytes
        -_handle_readrange(start_key, end_key) bytes
        -_handle_delete(key) bytes
        -_process_message(message: bytes) bytes
        -_handle_client(client_socket, addr)
        +start()
        +stop()
    }
    
    class Protocol {
        +escape(data: bytes) bytes
        +unescape(data: bytes) bytes
        -_parse_replicate_command(message) Tuple
        -_parse_put_command(parts) Tuple
        -_parse_batchput_command(parts) Tuple
        -_parse_readrange_command(parts) Tuple
        -_parse_simple_command(command, parts) Tuple
        +parse_command(message: bytes) Tuple
        +format_response(success: bool, data: bytes) bytes
        +format_not_found() bytes
        +format_error(message: str) bytes
    }
    
    class ConnectionHandler {
        -client_socket: socket
        -addr: tuple
        -message_handler: Callable
        +handle()
    }
    
    %% Core Layer
    class KVStore {
        -data_dir: Path
        -is_replica: bool
        -wal: WAL
        -data_file: DataFile
        -index: Index
        -rwlock: RWLock
        -wal_lock: Lock
        -replicator: Replicator
        -replica_manager: ReplicaManager
        -running: bool
        -checkpoint_thread: Thread
        -_init_replication()
        -_recover()
        -_checkpoint_loop()
        +put(key: bytes, value: bytes) bool
        +batch_put(keys: list, values: list) bool
        +read(key: bytes) Optional[bytes]
        +read_key_range(start_key: bytes, end_key: bytes) dict
        +delete(key: bytes) bool
        +close()
    }
    
    class RWLock {
        -_readers: int
        -_writers: int
        -_read_ready: Condition
        -_write_ready: Condition
        +acquire_read()
        +release_read()
        +acquire_write()
        +release_write()
    }
    
    class WAL {
        -path: str
        -file: File
        +log(op: str, key: bytes, value: bytes)
        +replay() list
        +truncate()
        +close()
    }
    
    class DataFile {
        -path: str
        -file: File
        +append(key: bytes, value: bytes) Tuple[int, int]
        +read(offset: int) Tuple[bytes, bytes]
        +close()
    }
    
    class Index {
        -path: str
        -index: Dict[bytes, Tuple[int, int]]
        +put(key: bytes, offset: int, length: int)
        +get(key: bytes) Optional[Tuple[int, int]]
        +get_range(start_key: bytes, end_key: bytes) Dict
        +delete(key: bytes)
        +save()
        +load()
    }
    
    %% Replication Layer
    class Replicator {
        -replica_manager: ReplicaManager
        -mode: str
        -queue: Queue
        -workers: List[Thread]
        +replicate_put(key, value) bool
        +replicate_batch_put(keys, values) bool
        +replicate_delete(key) bool
        -_enqueue_operation(op) bool
        -_worker_loop()
        -_replicate_to_all(op) bool
    }
    
    class ReplicaManager {
        -replicas: Set[ReplicaNode]
        -max_failures: int
        +add_replica(host, port) ReplicaNode
        +remove_replica(host, port) bool
        +get_healthy_replicas() List
        +get_all_replicas() List
        +mark_success(replica)
        +mark_failure(replica)
    }
    
    class ReplicaNode {
        +host: str
        +port: int
        +is_healthy: bool
        +consecutive_failures: int
        +last_success: datetime
        +last_failure: datetime
    }
    
    %% Relationships
    ClientCLI --> KVClient : uses
    ServerCLI --> KVServer : uses
    
    KVClient --> Protocol : uses
    KVServer --> Protocol : uses
    KVServer --> KVStore : manages
    KVServer --> ConnectionHandler : creates
    ConnectionHandler --> KVServer : calls _process_message
    
    KVStore --> WAL : uses
    KVStore --> DataFile : uses
    KVStore --> Index : uses
    KVStore --> RWLock : uses
    KVStore --> Replicator : uses (if master)
    KVStore --> ReplicaManager : uses (if master)
    
    Replicator --> ReplicaManager : uses
    ReplicaManager --> ReplicaNode : manages
    
    %% Notes
    note for KVStore "Three-phase operations:\n1. wal_lock for WAL writes\n2. rwlock for data/index access\n3. replicator for async replication\nAllows concurrent reads\nBackground checkpoint every 10 seconds"
    note for RWLock "Multiple readers can hold lock simultaneously\nWriters get exclusive access"
    note for WAL "Write-Ahead Log ensures durability\nReplayed on recovery\nHas separate lock for better concurrency"
    note for Index "In-memory hash index\nPeriodically persisted to disk"
    note for Replicator "Async replication to replica nodes\nQueued operations with retry logic\nSeparate worker threads"
```

## Data Flow

**Write Operation (with Replication):**
```
Client → Protocol → Server → KVStore → [Phase 1: WAL] → [Phase 2: DataFile & Index] → [Phase 3: Replicator] → Replicas
```

**Read Operation:**
```
Client → Protocol → Server → KVStore → Index → DataFile → Client
```

**Recovery on Startup:**
```
KVStore → WAL.replay() → Apply operations → Truncate WAL
```

## Write Operation Sequence Diagram

```mermaid
sequenceDiagram
    participant Client as KVClient
    participant Socket as TCP Socket
    participant Server as KVServer
    participant Protocol as Protocol
    participant Store as KVStore
    participant WALLock as wal_lock
    participant WAL as WAL
    participant WriteLock as RWLock (write)
    participant DataFile as DataFile
    participant Index as Index
    participant Replicator as Replicator
    
    Client->>Socket: connect(host, port)
    Client->>Socket: sendall("PUT key value\n")
    
    Socket->>Server: accept connection
    Server->>Protocol: parse_command(message)
    Protocol-->>Server: ("PUT", key, value)
    
    Server->>Store: put(key, value)
    
    Note over Store: PHASE 1: WAL Logging
    Store->>WALLock: acquire()
    activate WALLock
    
    Store->>WAL: log("put", key, value)
    WAL->>WAL: write to wal.log
    WAL-->>Store: success
    
    Store->>WALLock: release()
    deactivate WALLock
    
    Note over Store: PHASE 2: Data & Index Update
    Store->>WriteLock: acquire()
    activate WriteLock
    
    Note over Store: Append to Data File
    Store->>DataFile: append(key, value)
    DataFile->>DataFile: write to data.db
    DataFile-->>Store: (offset, length)
    
    Note over Store: Update In-Memory Index
    Store->>Index: put(key, offset, length)
    Index->>Index: index[key] = (offset, length)
    Index-->>Store: success
    
    Store->>WriteLock: release()
    deactivate WriteLock
    
    Note over Store: PHASE 3: Async Replication
    alt Not Replica and Replication Enabled
        Store->>Replicator: replicate_put(key, value)
        Replicator->>Replicator: enqueue operation
        Replicator-->>Store: queued
    end
    
    Store-->>Server: True
    Server->>Protocol: format_response(True)
    Protocol-->>Server: b"OK"
    
    Server->>Socket: send(b"OK")
    Socket-->>Client: b"OK"
    
    Note over Store: Background checkpoint thread<br/>saves index every 10 seconds
    Note over Replicator: Async worker threads<br/>send REPLICATE PUT<br/>to replica nodes
```

**Key Steps:**

1. **Phase 1 - WAL Lock**: Acquire wal_lock (fast, doesn't wait for readers)
2. **WAL Logging**: Write operation to WAL first (durability guarantee)
3. **Release WAL Lock**: Other writers can now log to WAL
4. **Phase 2 - Write Lock**: Acquire exclusive write lock (waits for readers to finish)
5. **Data Append**: Append key-value to append-only data file
6. **Index Update**: Update in-memory index with offset/length
7. **Release Write Lock**: Readers and other writers can now proceed
8. **Phase 3 - Replication**: Async replication to replicas (non-blocking)
9. **Response**: Return success to client

**Three-Phase Locking Benefits:**
- **Read-heavy optimization**: WAL writes don't wait for readers
- **Better write throughput**: Multiple writers can log to WAL concurrently (sequential, but not blocked by readers)
- **Durability preserved**: WAL is always written before data/index updates
- **Prevents write starvation**: Writers can make progress even with many active readers
- **Async replication**: Replication doesn't block write response to client

**Crash Recovery:**
- If crash occurs after WAL log but before index update
- On restart: WAL is replayed to rebuild index
- Ensures no data loss
- Replicas eventually consistent via async replication

## Read Operation Sequence Diagram

```mermaid
sequenceDiagram
    participant Client as KVClient
    participant Socket as TCP Socket
    participant Server as KVServer
    participant Protocol as Protocol
    participant Store as KVStore
    participant Lock as RWLock (read)
    participant Index as Index
    participant DataFile as DataFile
    
    Client->>Socket: connect(host, port)
    Client->>Socket: sendall("READ key\n")
    
    Socket->>Server: accept connection
    Server->>Protocol: parse_command(message)
    Protocol-->>Server: ("READ", key, None)
    
    Server->>Store: read(key)
    
    Store->>Lock: acquire()
    activate Lock
    
    Note over Store: Lookup in In-Memory Index
    Store->>Index: get(key)
    Index->>Index: lookup index[key]
    
    alt Key Found
        Index-->>Store: (offset, length)
        
        Note over Store: Read from Data File
        Store->>DataFile: read(offset)
        DataFile->>DataFile: seek and read from data.db
        DataFile-->>Store: (stored_key, value)
        
        Note over Store: Verify Key Match
        Store->>Store: verify stored_key == key
        
        Store-->>Server: value
        Server->>Protocol: format_response(True, value)
        Protocol-->>Server: value
        
        Server->>Socket: send(value)
        Socket-->>Client: value
        
    else Key Not Found
        Index-->>Store: None
        
        Store-->>Server: None
        Server->>Protocol: format_not_found()
        Protocol-->>Server: b"NOT_FOUND"
        
        Server->>Socket: send(b"NOT_FOUND")
        Socket-->>Client: b"NOT_FOUND"
    end
    
    Store->>Lock: release()
    deactivate Lock
```

**Key Steps:**

1. **Lock Acquisition**: Acquire read lock (allows concurrent reads - multiple readers simultaneously)
2. **Index Lookup**: Fast O(1) lookup in in-memory hash index
3. **Get Offset**: Retrieve file offset and length for the key
4. **Data Read**: Seek to offset and read from data file
5. **Verification**: Verify stored key matches requested key
6. **Lock Release**: Release read lock
7. **Response**: Return value or NOT_FOUND to client

**Performance Characteristics:**
- **Fast lookups**: O(1) index lookup in memory
- **True concurrent reads**: Multiple readers can hold the lock simultaneously (Reader-Writer Lock)
- **Non-blocking reads**: Read operations don't block each other
- **Single disk seek**: Direct access via offset, no scanning
- **Key verification**: Extra safety check after reading from disk

## Delete Operation Sequence Diagram

```mermaid
sequenceDiagram
    participant Client as KVClient
    participant Socket as TCP Socket
    participant Server as KVServer
    participant Protocol as Protocol
    participant Store as KVStore
    participant ReadLock as RWLock (read)
    participant WALLock as wal_lock
    participant WAL as WAL
    participant WriteLock as RWLock (write)
    participant Index as Index
    participant Replicator as Replicator
    
    Client->>Socket: connect(host, port)
    Client->>Socket: sendall("DELETE key\n")
    
    Socket->>Server: accept connection
    Server->>Protocol: parse_command(message)
    Protocol-->>Server: ("DELETE", key, None)
    
    Server->>Store: delete(key)
    
    Note over Store: PHASE 1: Check Existence
    Store->>ReadLock: acquire()
    activate ReadLock
    
    Store->>Index: get(key)
    Index->>Index: lookup index[key]
    
    alt Key Found
        Index-->>Store: (offset, length)
        
        Store->>ReadLock: release()
        deactivate ReadLock
        
        Note over Store: PHASE 2: WAL Logging
        Store->>WALLock: acquire()
        activate WALLock
        
        Store->>WAL: log("delete", key)
        WAL->>WAL: write to wal.log
        WAL-->>Store: success
        
        Store->>WALLock: release()
        deactivate WALLock
        
        Note over Store: PHASE 3: Index Update
        Store->>WriteLock: acquire()
        activate WriteLock
        
        Note over Store: Double-check key still exists
        Store->>Index: get(key)
        
        alt Key Still Exists
            Index-->>Store: (offset, length)
            
            Store->>Index: delete(key)
            Index->>Index: index.pop(key)
            Index-->>Store: success
            
            Store->>WriteLock: release()
            deactivate WriteLock
            
            Note over Store: PHASE 4: Replication
            alt Not Replica and Replication Enabled
                Store->>Replicator: replicate_delete(key)
                Replicator->>Replicator: enqueue operation
                Replicator-->>Store: queued
            end
            
            Store-->>Server: True
            Server->>Protocol: format_response(True)
            Protocol-->>Server: b"OK"
            
            Server->>Socket: send(b"OK")
            Socket-->>Client: b"OK"
        else Key Was Deleted by Another Thread
            Index-->>Store: None
            
            Store->>WriteLock: release()
            deactivate WriteLock
            
            Store-->>Server: False
            Server->>Protocol: format_not_found()
            Protocol-->>Server: b"NOT_FOUND"
            
            Server->>Socket: send(b"NOT_FOUND")
            Socket-->>Client: b"NOT_FOUND"
        end
        
    else Key Not Found
        Index-->>Store: None
        
        Store->>ReadLock: release()
        deactivate ReadLock
        
        Store-->>Server: False
        Server->>Protocol: format_not_found()
        Protocol-->>Server: b"NOT_FOUND"
        
        Server->>Socket: send(b"NOT_FOUND")
        Socket-->>Client: b"NOT_FOUND"
    end
    
    Note over Store: Data remains in data.db<br/>(logical delete only)
    Note over Replicator: Async worker threads<br/>send REPLICATE DELETE<br/>to replica nodes
```

**Key Steps:**

1. **Phase 1 - Read Lock**: Check if key exists (allows concurrent reads)
2. **Release Read Lock**: Early release for better concurrency
3. **Phase 2 - WAL Lock**: Log delete operation to WAL (doesn't wait for readers)
4. **Release WAL Lock**: Other writers can now log to WAL
5. **Phase 3 - Write Lock**: Acquire exclusive write lock
6. **Double Check**: Verify key still exists (race condition protection)
7. **Index Removal**: Remove key from in-memory index
8. **Release Write Lock**: Readers and other writers can now proceed
9. **Phase 4 - Replication**: Async replication to replicas (if master)
10. **Response**: Return OK or NOT_FOUND to client

**Three-Phase Locking Benefits:**
- **Optimistic existence check**: Read lock first (fast, concurrent)
- **WAL logging without blocking**: Separate lock for durability
- **Race condition safety**: Double-check under write lock
- **Async replication**: Non-blocking replication to replicas

**Important Notes:**
- **Logical Delete**: Data is NOT removed from the data file (append-only)
- **Index Only**: Only the index entry is removed
- **Space Reclamation**: Deleted data remains on disk (could be compacted later)
- **Fast Operation**: No disk I/O needed except WAL log
- **Crash Recovery**: WAL ensures delete is replayed after crash
- **Replication**: Delete propagates to replica nodes asynchronously

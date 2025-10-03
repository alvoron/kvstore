# kvstore

A high-performance, thread-safe key-value store with Write-Ahead Logging (WAL) and network interface.

## Features

- **Thread-safe operations**: True concurrent reads with exclusive writes using Reader-Wr    %% Notes
    note for KVStore "Two-phase locking strategy:\\nwal_lock for WAL writes\\nrwlock for data/index access\\nAllows concurrent reads\\nBackground checkpoint every 10 seconds"
    note for RWLock "Multiple readers can hold lock simultaneously\\nWriters get exclusive access"
    note for WAL "Write-Ahead Log ensures durability\\nReplayed on recovery\\nHas separate lock for better concurrency"
    note for Index "In-memory hash index\\nPeriodically persisted to disk"Lock
- **Two-phase locking**: Separate WAL lock prevents write starvation in read-heavy workloads
- **Write-Ahead Logging (WAL)**: Ensures durability and crash recovery
- **In-memory indexing**: Fast lookups with periodic persistence
- **Background checkpointing**: Automatic index saves every 10 seconds
- **Network protocol**: Simple TCP-based text protocol
- **Batch operations**: Efficient bulk insertions with `batchput`
- **Range queries**: Retrieve multiple key-value pairs with `readrange`
- **Graceful shutdown**: Ctrl+C handling with proper cleanup
- **Concurrent reads**: Multiple clients can read simultaneously without blocking each other
- **Write optimization**: WAL writes don't wait for readers to finish

## Install and run
From project root
```
pip install -e .
```

Run server
```
python -m kvstore.cli.server_cli
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

## Architecture Details

### Core Components

1. **KVStore**: Main store orchestrating WAL, DataFile, and Index
2. **WAL (Write-Ahead Log)**: Logs all write operations before applying them
3. **DataFile**: Append-only storage file for key-value pairs
4. **Index**: In-memory hash map for fast key lookups

### Locking Strategy

The system uses a sophisticated **two-phase locking strategy** to optimize performance:

#### 1. Reader-Writer Lock (RWLock)
- **Read operations**: Multiple readers can acquire the lock simultaneously
- **Write operations**: Writers get exclusive access (no readers or other writers)
- **Use case**: Protects data file reads/writes and index updates

#### 2. Separate WAL Lock
- **Independent locking**: WAL writes use a separate `threading.Lock()`
- **Problem solved**: In read-heavy workloads, writers would wait for all readers to finish before even logging to WAL
- **Benefit**: WAL writes can proceed immediately without waiting for readers

#### Write Operation Flow (Two-Phase):
```
Phase 1: Acquire wal_lock → Log to WAL → Release wal_lock
Phase 2: Acquire write_lock → Update DataFile & Index → Release write_lock
```

**Why this matters:**
- In a read-heavy workload, many readers might be active
- Without separate locks: Writer waits for readers → WAL logging delayed → Other writers blocked
- With separate locks: WAL logging proceeds immediately → Better write throughput
- Durability preserved: WAL is written before data/index updates

### Network Components

1. **KVServer**: Multi-threaded TCP server handling client connections
2. **KVClient**: Client library for connecting to the server
3. **Protocol**: Message parsing and formatting
4. **ConnectionHandler**: Per-connection request handler

### Architecture Diagram

```mermaid
classDiagram
    %% CLI Layer
    class ClientCLI {
        +main()
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
        -_process_message(message: bytes) bytes
        -_handle_client(client_socket, addr)
        +start()
        +stop()
    }
    
    class Protocol {
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
        -wal: WAL
        -data_file: DataFile
        -index: Index
        -rwlock: RWLock
        -wal_lock: Lock
        -running: bool
        -checkpoint_thread: Thread
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
    
    %% Notes
    note for KVStore "Thread-safe with Reader-Writer Lock\nAllows concurrent reads\nBackground checkpoint every 10 seconds"
    note for RWLock "Multiple readers can hold lock simultaneously\nWriters get exclusive access"
    note for WAL "Write-Ahead Log ensures durability\nReplayed on recovery"
    note for Index "In-memory hash index\nPeriodically persisted to disk"
```

### Data Flow

**Write Operation:**
```
Client → Protocol → Server → KVStore → WAL → DataFile → Index
```

**Read Operation:**
```
Client → Protocol → Server → KVStore → Index → DataFile → Client
```

**Recovery on Startup:**
```
KVStore → WAL.replay() → Apply operations → Truncate WAL
```

### Write Operation Sequence Diagram

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
    
    Store-->>Server: True
    Server->>Protocol: format_response(True)
    Protocol-->>Server: b"OK"
    
    Server->>Socket: send(b"OK")
    Socket-->>Client: b"OK"
    
    Note over Store: Background checkpoint thread<br/>saves index every 10 seconds
```

**Key Steps:**

1. **Phase 1 - WAL Lock**: Acquire wal_lock (fast, doesn't wait for readers)
2. **WAL Logging**: Write operation to WAL first (durability guarantee)
3. **Release WAL Lock**: Other writers can now log to WAL
4. **Phase 2 - Write Lock**: Acquire exclusive write lock (waits for readers to finish)
5. **Data Append**: Append key-value to append-only data file
6. **Index Update**: Update in-memory index with offset/length
7. **Release Write Lock**: Readers and other writers can now proceed
8. **Response**: Return success to client

**Two-Phase Locking Benefits:**
- **Read-heavy optimization**: WAL writes don't wait for readers
- **Better write throughput**: Multiple writers can log to WAL concurrently (sequential, but not blocked by readers)
- **Durability preserved**: WAL is always written before data/index updates
- **Prevents write starvation**: Writers can make progress even with many active readers

**Crash Recovery:**
- If crash occurs after WAL log but before index update
- On restart: WAL is replayed to rebuild index
- Ensures no data loss

### Read Operation Sequence Diagram

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

### Delete Operation Sequence Diagram

```mermaid
sequenceDiagram
    participant Client as KVClient
    participant Socket as TCP Socket
    participant Server as KVServer
    participant Protocol as Protocol
    participant Store as KVStore
    participant Lock as RWLock (write)
    participant Index as Index
    participant WAL as WAL
    
    Client->>Socket: connect(host, port)
    Client->>Socket: sendall("DELETE key\n")
    
    Socket->>Server: accept connection
    Server->>Protocol: parse_command(message)
    Protocol-->>Server: ("DELETE", key, None)
    
    Server->>Store: delete(key)
    
    Store->>Lock: acquire()
    activate Lock
    
    Note over Store: Check if Key Exists
    Store->>Index: get(key)
    Index->>Index: lookup index[key]
    
    alt Key Found
        Index-->>Store: (offset, length)
        
        Note over Store: Log to Write-Ahead Log
        Store->>WAL: log("delete", key)
        WAL->>WAL: write to wal.log
        WAL-->>Store: success
        
        Note over Store: Remove from Index
        Store->>Index: delete(key)
        Index->>Index: index.pop(key)
        Index-->>Store: success
        
        Store-->>Server: True
        Server->>Protocol: format_response(True)
        Protocol-->>Server: b"OK"
        
        Server->>Socket: send(b"OK")
        Socket-->>Client: b"OK"
        
    else Key Not Found
        Index-->>Store: None
        
        Store-->>Server: False
        Server->>Protocol: format_not_found()
        Protocol-->>Server: b"NOT_FOUND"
        
        Server->>Socket: send(b"NOT_FOUND")
        Socket-->>Client: b"NOT_FOUND"
    end
    
    Store->>Lock: release()
    deactivate Lock
    
    Note over Store: Data remains in data.db<br/>(logical delete only)
```

**Key Steps:**

1. **Lock Acquisition**: Acquire exclusive write lock for thread safety
2. **Existence Check**: Check if key exists in index
3. **WAL Logging**: Log delete operation to WAL (for crash recovery)
4. **Index Removal**: Remove key from in-memory index
5. **Lock Release**: Release write lock
6. **Response**: Return OK or NOT_FOUND to client

**Important Notes:**
- **Logical Delete**: Data is NOT removed from the data file (append-only)
- **Index Only**: Only the index entry is removed
- **Space Reclamation**: Deleted data remains on disk (could be compacted later)
- **Fast Operation**: No disk I/O needed except WAL log
- **Crash Recovery**: WAL ensures delete is replayed after crash




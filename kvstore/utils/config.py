"""Configuration management."""


class Config:
    """Configuration management."""

    # Server settings
    HOST = '0.0.0.0'
    PORT = 5555
    SERVER_BACKLOG = 128  # Max queued connections
    SERVER_TIMEOUT = 1.0  # Socket timeout in seconds for shutdown responsiveness

    # Client settings
    CLIENT_HOST = 'localhost'
    CLIENT_PORT = 5555
    CLIENT_RECV_BUFFER = 4096  # Socket receive buffer size

    # Storage settings
    DATA_DIR = './kvstore_data'
    WAL_FILENAME = 'wal.log'  # Write-ahead log filename
    DATA_FILENAME = 'data.db'  # Data file filename
    INDEX_FILENAME = 'index.db'  # Index file filename
    CHECKPOINT_INTERVAL = 10  # Seconds between index checkpoints
    MAX_WAL_SIZE = 100 * 1024 * 1024  # 100MB
    WAL_BUFFER_SIZE = 0  # 0 = unbuffered (immediate flush)

    # Network settings
    CONNECTION_RECV_BUFFER = 4096  # Buffer size for connection handler
    MESSAGE_DELIMITER = b'\n'  # Message delimiter in protocol
    BATCH_SEPARATOR = b'||'  # Separator for batch operations

    # Replication settings
    REPLICATION_ENABLED = False  # Enable/disable replication
    REPLICATION_MODE = 'async'  # 'async' or 'sync'
    REPLICA_ADDRESSES = []  # List of (host, port) tuples for replica nodes
    REPLICATION_MAX_RETRIES = 3  # Maximum retry attempts per operation
    REPLICATION_QUEUE_SIZE = 10000  # Maximum size of replication queue
    REPLICATION_MAX_FAILURES = 3  # Max consecutive failures before marking unhealthy
    REPLICATION_HEALTH_CHECK_INTERVAL = 30  # Seconds between health checks
    REPLICATION_TIMEOUT = 5.0  # Socket timeout for replication in seconds

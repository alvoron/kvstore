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
    CHECKPOINT_INTERVAL = 10  # Seconds between index checkpoints
    MAX_WAL_SIZE = 100 * 1024 * 1024  # 100MB
    WAL_BUFFER_SIZE = 0  # 0 = unbuffered (immediate flush)
    
    # Network settings
    CONNECTION_RECV_BUFFER = 4096  # Buffer size for connection handler
    MESSAGE_DELIMITER = b'\n'  # Message delimiter in protocol
    BATCH_SEPARATOR = b'||'  # Separator for batch operations

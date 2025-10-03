"""Configuration management."""


class Config:
    """Configuration management."""
    
    # Server settings
    HOST = '0.0.0.0'
    PORT = 5555
    MAX_CONNECTIONS = 1000
    
    # Storage settings
    DATA_DIR = './data'
    CHECKPOINT_INTERVAL = 10
    MAX_WAL_SIZE = 100 * 1024 * 1024  # 100MB
    
    # Performance tuning
    MMAP_SIZE = 1024 * 1024 * 1024  # 1GB
    INDEX_CACHE_SIZE = 10000
    
    @classmethod
    def from_dict(cls, config_dict: dict):
        """Load config from dictionary."""
        for key, value in config_dict.items():
            if hasattr(cls, key.upper()):
                setattr(cls, key.upper(), value)
        return cls

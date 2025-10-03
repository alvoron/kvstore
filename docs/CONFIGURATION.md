# Configuration Guide

All configurable values in the KV store system have been centralized in `kvstore/utils/config.py`.

## Configuration Parameters

### Server Settings
| Parameter | Default | Description |
|-----------|---------|-------------|
| `HOST` | `'0.0.0.0'` | Server bind address |
| `PORT` | `5555` | Server listen port |
| `SERVER_BACKLOG` | `128` | Maximum queued connections |
| `SERVER_TIMEOUT` | `1.0` | Socket timeout in seconds (for shutdown responsiveness) |

### Client Settings
| Parameter | Default | Description |
|-----------|---------|-------------|
| `CLIENT_HOST` | `'localhost'` | Default server host for client |
| `CLIENT_PORT` | `5555` | Default server port for client |
| `CLIENT_RECV_BUFFER` | `4096` | Socket receive buffer size |

### Storage Settings
| Parameter | Default | Description |
|-----------|---------|-------------|
| `DATA_DIR` | `'./kvstore_data'` | Directory for data files |
| `CHECKPOINT_INTERVAL` | `10` | Seconds between index checkpoints |
| `MAX_WAL_SIZE` | `100 * 1024 * 1024` | Maximum WAL file size (100MB) |
| `WAL_BUFFER_SIZE` | `0` | WAL file buffer size (0 = unbuffered) |

### Network Settings
| Parameter | Default | Description |
|-----------|---------|-------------|
| `CONNECTION_RECV_BUFFER` | `4096` | Buffer size for connection handler |
| `MESSAGE_DELIMITER` | `b'\n'` | Message delimiter in protocol |
| `BATCH_SEPARATOR` | `b'\|\|'` | Separator for batch operations |

## Usage Examples

### Basic Configuration
```python
from kvstore.utils.config import Config
from kvstore.network.server import KVServer

# Customize settings
Config.PORT = 8080
Config.CHECKPOINT_INTERVAL = 30
Config.DATA_DIR = '/var/kvstore/data'

# Create server with custom config
server = KVServer()
server.start()
```

### Production Settings Example
```python
from kvstore.utils.config import Config

# Production configuration
Config.HOST = '0.0.0.0'
Config.PORT = 9000
Config.SERVER_BACKLOG = 512  # Higher for production
Config.CHECKPOINT_INTERVAL = 60  # Less frequent checkpoints
Config.DATA_DIR = '/mnt/ssd/kvstore'
Config.WAL_BUFFER_SIZE = 8192  # Some buffering for better performance
```

### High-Performance Settings
```python
from kvstore.utils.config import Config

# Optimized for high throughput
Config.SERVER_BACKLOG = 1024
Config.CLIENT_RECV_BUFFER = 8192
Config.CONNECTION_RECV_BUFFER = 8192
Config.CHECKPOINT_INTERVAL = 120  # Less frequent checkpoints
```

## Files Modified

The following files now use the Config class:

1. **kvstore/core/store.py**
   - `CHECKPOINT_INTERVAL` for checkpoint thread

2. **kvstore/core/wal.py**
   - `WAL_BUFFER_SIZE` for file buffering

3. **kvstore/network/server.py**
   - `HOST`, `PORT`, `DATA_DIR` for server initialization
   - `SERVER_BACKLOG` for listen queue
   - `SERVER_TIMEOUT` for socket timeout
   - `BATCH_SEPARATOR` for parsing batch operations

4. **kvstore/network/client.py**
   - `CLIENT_HOST`, `CLIENT_PORT` for default connection
   - `CLIENT_RECV_BUFFER` for socket receive
   - `MESSAGE_DELIMITER` for protocol
   - `BATCH_SEPARATOR` for batch operations

5. **kvstore/network/connection.py**
   - `CONNECTION_RECV_BUFFER` for socket receive
   - `MESSAGE_DELIMITER` for protocol parsing

## Benefits

- ✅ **Centralized Configuration**: All settings in one place
- ✅ **Easy Customization**: Change behavior without modifying code
- ✅ **Type Safety**: Config values defined in one class
- ✅ **Documentation**: Clear parameter descriptions
- ✅ **Environment Specific**: Easy to create dev/test/prod configs
- ✅ **No Magic Numbers**: All hardcoded values eliminated

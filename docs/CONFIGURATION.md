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

## Benefits

- ✅ **Centralized Configuration**: All settings in one place
- ✅ **Easy Customization**: Change behavior without modifying code
- ✅ **Type Safety**: Config values defined in one class
- ✅ **Documentation**: Clear parameter descriptions
- ✅ **Environment Specific**: Easy to create dev/test/prod configs
- ✅ **No Magic Numbers**: All hardcoded values eliminated

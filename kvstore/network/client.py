"""Client for connecting to KV store server."""
import socket
from typing import Optional
from ..utils.config import Config


class KVClient:
    """Simple client for KV store."""
    
    def __init__(self, host: str = None, port: int = None):
        self.host = host or Config.CLIENT_HOST
        self.port = port or Config.CLIENT_PORT
    
    def _send_command(self, command: bytes) -> bytes:
        """Send command and receive response."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((self.host, self.port))
            s.sendall(command + Config.MESSAGE_DELIMITER)
            response = s.recv(Config.CLIENT_RECV_BUFFER).strip()
            return response
    
    def put(self, key: str, value: str) -> bool:
        """Put key-value pair."""
        command = f'PUT {key} {value}'.encode()
        response = self._send_command(command)
        return response == b'OK'
    
    def batch_put(self, keys: list[str], values: list[str]) -> bool:
        """Put multiple key-value pairs in a batch."""
        if len(keys) != len(values):
            raise ValueError("Keys and values must have the same length")
        
        # Join keys and values with Config.BATCH_SEPARATOR
        separator = Config.BATCH_SEPARATOR.decode()
        keys_str = separator.join(keys)
        values_str = separator.join(values)
        command = f'BATCHPUT {keys_str} {values_str}'.encode()
        response = self._send_command(command)
        return response == b'OK'
    
    def read(self, key: str) -> Optional[str]:
        """Read value for key."""
        command = f'READ {key}'.encode()
        response = self._send_command(command)
        return response.decode() if response != b'NOT_FOUND' else None
    
    def read_key_range(self, start_key: str, end_key: str) -> dict[str, str]:
        """Read all key-value pairs in the range [start_key, end_key]."""
        command = f'READRANGE {start_key} {end_key}'.encode()
        response = self._send_command(command)
        
        if response == b'NOT_FOUND':
            return {}
        
        # Parse response: key1||value1||key2||value2||...
        parts = response.split(Config.BATCH_SEPARATOR)
        result = {}
        for i in range(0, len(parts), 2):
            if i + 1 < len(parts):
                result[parts[i].decode()] = parts[i + 1].decode()
        return result
    
    def delete(self, key: str) -> bool:
        """Delete key."""
        command = f'DELETE {key}'.encode()
        response = self._send_command(command)
        return response == b'OK'

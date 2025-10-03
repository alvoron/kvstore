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
            
            # Read response until we get MESSAGE_DELIMITER
            buffer = b''
            while Config.MESSAGE_DELIMITER not in buffer:
                chunk = s.recv(Config.CLIENT_RECV_BUFFER)
                if not chunk:
                    break
                buffer += chunk
            
            # Extract the response (everything before the delimiter)
            if Config.MESSAGE_DELIMITER in buffer:
                response, _ = buffer.split(Config.MESSAGE_DELIMITER, 1)
            else:
                response = buffer
            
            return response.strip()
    
    def put(self, key: str, value: str) -> bool:
        """Put key-value pair."""
        from .protocol import Protocol
        # Build command purely with bytes - escape the value bytes
        escaped_value = Protocol.escape(value.encode())
        command = b'PUT ' + key.encode() + b' ' + escaped_value
        response = self._send_command(command)
        return response == b'OK'
    
    def batch_put(self, keys: list[str], values: list[str]) -> bool:
        """Put multiple key-value pairs in a batch."""
        if len(keys) != len(values):
            raise ValueError("Keys and values must have the same length")
        
        from .protocol import Protocol
        # Escape each value before joining - keep as bytes
        escaped_values = [Protocol.escape(v.encode()) for v in values]
        
        # Join keys and values with Config.BATCH_SEPARATOR - all as bytes
        keys_bytes = Config.BATCH_SEPARATOR.join([k.encode() for k in keys])
        values_bytes = Config.BATCH_SEPARATOR.join(escaped_values)
        command = b'BATCHPUT ' + keys_bytes + b' ' + values_bytes
        response = self._send_command(command)
        return response == b'OK'
    
    def read(self, key: str) -> Optional[str]:
        """Read value for key."""
        from .protocol import Protocol
        command = f'READ {key}'.encode()
        response = self._send_command(command)
        if response == b'NOT_FOUND':
            return None
        # Unescape the response value
        return Protocol.unescape(response).decode()
    
    def read_key_range(self, start_key: str, end_key: str) -> dict[str, str]:
        """Read all key-value pairs in the range [start_key, end_key]."""
        from .protocol import Protocol
        command = f'READRANGE {start_key} {end_key}'.encode()
        response = self._send_command(command)
        
        if response == b'NOT_FOUND':
            return {}
        
        # Parse response: key1||value1||key2||value2||...
        parts = response.split(Config.BATCH_SEPARATOR)
        result = {}
        for i in range(0, len(parts), 2):
            if i + 1 < len(parts):
                key = parts[i].decode()
                value = Protocol.unescape(parts[i + 1]).decode()
                result[key] = value
        return result
    
    def delete(self, key: str) -> bool:
        """Delete key."""
        command = f'DELETE {key}'.encode()
        response = self._send_command(command)
        return response == b'OK'

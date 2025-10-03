"""Network server for KV store."""
import socket
import threading
from typing import Optional

from ..core.store import KVStore
from .protocol import Protocol
from .connection import ConnectionHandler
from ..utils.config import Config


class KVServer:
    """Network server for KV store using simple text protocol."""
    
    def __init__(self, host: str = None, port: int = None, data_dir: str = None, is_replica: bool = False):
        self.host = host or Config.HOST
        self.port = port or Config.PORT
        self.is_replica = is_replica
        self.store = KVStore(data_dir or Config.DATA_DIR, is_replica=is_replica)
        self.server_socket = None
        self.protocol = Protocol()
        self.running = False
    
    def _process_message(self, message: bytes) -> bytes:
        """Process client message."""
        try:
            command, key, value = self.protocol.parse_command(message)
            
            # Handle REPLICATE commands (only accepted on replica nodes)
            if command.startswith('REPLICATE_'):
                if not self.is_replica:
                    return self.protocol.format_error('REPLICATE commands only accepted on replica nodes')
                
                if command == 'REPLICATE_PUT':
                    success = self.store.put(key, value)
                    return self.protocol.format_response(success)
                
                elif command == 'REPLICATE_BATCHPUT':
                    keys = key.split(Config.BATCH_SEPARATOR)
                    values = value.split(Config.BATCH_SEPARATOR)
                    if len(keys) != len(values):
                        return self.protocol.format_error('Keys and values count mismatch')
                    # Unescape each value
                    unescaped_values = [self.protocol.unescape(v) for v in values]
                    success = self.store.batch_put(keys, unescaped_values)
                    return self.protocol.format_response(success)
                
                elif command == 'REPLICATE_DELETE':
                    success = self.store.delete(key)
                    return self.protocol.format_response(success)
            
            if command == 'PUT':
                success = self.store.put(key, value)
                return self.protocol.format_response(success)
            
            elif command == 'BATCHPUT':
                # Parse keys and values separated by Config.BATCH_SEPARATOR
                keys = key.split(Config.BATCH_SEPARATOR)
                values = value.split(Config.BATCH_SEPARATOR)
                if len(keys) != len(values):
                    return self.protocol.format_error('Keys and values count mismatch')
                # Unescape each value
                unescaped_values = [self.protocol.unescape(v) for v in values]
                success = self.store.batch_put(keys, unescaped_values)
                return self.protocol.format_response(success)
            
            elif command == 'READ':
                result = self.store.read(key)
                if result is not None:
                    # Escape the value before sending
                    escaped_result = self.protocol.escape(result)
                    return self.protocol.format_response(True, escaped_result)
                return self.protocol.format_not_found()
            
            elif command == 'READRANGE':
                # value contains end_key for READRANGE
                start_key = key
                end_key = value
                results = self.store.read_key_range(start_key, end_key)
                if results:
                    # Format: key1||value1||key2||value2||...
                    pairs = []
                    for k, v in sorted(results.items()):
                        # Escape each value before sending
                        pairs.extend([k, self.protocol.escape(v)])
                    response = Config.BATCH_SEPARATOR.join(pairs)
                    return self.protocol.format_response(True, response)
                return self.protocol.format_not_found()
            
            elif command == 'DELETE':
                success = self.store.delete(key)
                if success:
                    return self.protocol.format_response(True)
                return self.protocol.format_not_found()
        
        except ValueError as e:
            return self.protocol.format_error(str(e))
        except Exception as e:
            return self.protocol.format_error(f'Internal error: {str(e)}')
    
    def _handle_client(self, client_socket: socket.socket, addr):
        """Handle individual client connection."""
        handler = ConnectionHandler(client_socket, addr, self._process_message)
        handler.handle()
    
    def start(self):
        """Start the server."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Set timeout to allow periodic checking for shutdown
        self.server_socket.settimeout(Config.SERVER_TIMEOUT)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(Config.SERVER_BACKLOG)
        
        self.running = True
        print(f"KV Store server listening on {self.host}:{self.port}")
        print("Press Ctrl+C to stop the server")
        
        try:
            while self.running:
                try:
                    client_socket, addr = self.server_socket.accept()
                    # Handle each client in a separate thread
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, addr),
                        daemon=True
                    )
                    client_thread.start()
                except socket.timeout:
                    # Timeout allows us to check self.running flag
                    continue
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the server."""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        self.store.close()
        print("Server stopped.")

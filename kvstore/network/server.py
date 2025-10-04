"""Network server for KV store."""
import socket
import threading

from ..core.store import KVStore
from .protocol import Protocol
from .connection import ConnectionHandler
from ..utils.config import Config


class KVServer:
    """Network server for KV store using simple text protocol."""

    def __init__(self, host: str = None, port: int = None, data_dir: str = None, is_replica: bool = False, checkpoint_interval: int = None):
        self.host = host or Config.HOST
        self.port = port or Config.PORT
        self.is_replica = is_replica
        self.store = KVStore(data_dir or Config.DATA_DIR, is_replica=is_replica, checkpoint_interval=checkpoint_interval)
        self.server_socket = None
        self.protocol = Protocol()
        self.running = False

    def _handle_replicate_put(self, key: bytes, value: bytes) -> bytes:
        """Handle REPLICATE_PUT command."""
        success = self.store.put(key, value)
        return self.protocol.format_response(success)

    def _handle_replicate_batchput(self, key: bytes, value: bytes) -> bytes:
        """Handle REPLICATE_BATCHPUT command."""
        keys = key.split(Config.BATCH_SEPARATOR)
        values = value.split(Config.BATCH_SEPARATOR)
        if len(keys) != len(values):
            return self.protocol.format_error('Keys and values count mismatch')
        unescaped_values = [self.protocol.unescape(v) for v in values]
        success = self.store.batch_put(keys, unescaped_values)
        return self.protocol.format_response(success)

    def _handle_replicate_delete(self, key: bytes) -> bytes:
        """Handle REPLICATE_DELETE command."""
        success = self.store.delete(key)
        return self.protocol.format_response(success)

    def _handle_put(self, key: bytes, value: bytes) -> bytes:
        """Handle PUT command."""
        success = self.store.put(key, value)
        return self.protocol.format_response(success)

    def _handle_batchput(self, key: bytes, value: bytes) -> bytes:
        """Handle BATCHPUT command."""
        keys = key.split(Config.BATCH_SEPARATOR)
        values = value.split(Config.BATCH_SEPARATOR)
        if len(keys) != len(values):
            return self.protocol.format_error('Keys and values count mismatch')
        unescaped_values = [self.protocol.unescape(v) for v in values]
        success = self.store.batch_put(keys, unescaped_values)
        return self.protocol.format_response(success)

    def _handle_read(self, key: bytes) -> bytes:
        """Handle READ command."""
        result = self.store.read(key)
        if result is not None:
            escaped_result = self.protocol.escape(result)
            return self.protocol.format_response(True, escaped_result)
        return self.protocol.format_not_found()

    def _handle_readrange(self, start_key: bytes, end_key: bytes) -> bytes:
        """Handle READRANGE command."""
        results = self.store.read_key_range(start_key, end_key)
        if results:
            pairs = []
            for k, v in sorted(results.items()):
                pairs.extend([k, self.protocol.escape(v)])
            response = Config.BATCH_SEPARATOR.join(pairs)
            return self.protocol.format_response(True, response)
        return self.protocol.format_not_found()

    def _handle_delete(self, key: bytes) -> bytes:
        """Handle DELETE command."""
        success = self.store.delete(key)
        if success:
            return self.protocol.format_response(True)
        return self.protocol.format_not_found()

    def _process_message(self, message: bytes) -> bytes:
        """Process client message."""
        try:
            command, key, value = self.protocol.parse_command(message)

            # Handle REPLICATE commands (only on replica nodes)
            if command.startswith('REPLICATE_'):
                if not self.is_replica:
                    return self.protocol.format_error('REPLICATE commands only accepted on replica nodes')

                replicate_handlers = {
                    'REPLICATE_PUT': lambda: self._handle_replicate_put(key, value),
                    'REPLICATE_BATCHPUT': lambda: self._handle_replicate_batchput(key, value),
                    'REPLICATE_DELETE': lambda: self._handle_replicate_delete(key),
                }
                handler = replicate_handlers.get(command)
                if handler:
                    return handler()

            # Handle regular commands
            command_handlers = {
                'PUT': lambda: self._handle_put(key, value),
                'BATCHPUT': lambda: self._handle_batchput(key, value),
                'READ': lambda: self._handle_read(key),
                'READRANGE': lambda: self._handle_readrange(key, value),
                'DELETE': lambda: self._handle_delete(key),
            }

            handler = command_handlers.get(command)
            if handler:
                return handler()

            return self.protocol.format_error(f'Unknown command: {command}')

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
        try:
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
                    except OSError:
                        # Socket was closed, exit loop
                        break
            except KeyboardInterrupt:
                print("\nShutting down...")
        except Exception as e:
            print(f"Error starting server: {e}")
        finally:
            self.stop()

    def stop(self):
        """Stop the server."""
        self.running = False
        if self.server_socket:
            try:
                # Shutdown the socket to unblock accept()
                self.server_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                # Socket might already be closed or not connected
                pass
            try:
                self.server_socket.close()
            except OSError:
                pass
        self.store.close()
        print("Server stopped.")

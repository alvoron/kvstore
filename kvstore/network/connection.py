"""Connection handler for individual clients."""
import socket
from typing import Callable
from .protocol import Protocol
from ..utils.config import Config


class ConnectionHandler:
    """Handles individual client connections."""
    
    def __init__(self, client_socket: socket.socket, addr, message_processor: Callable):
        self.socket = client_socket
        self.addr = addr
        self.process_message = message_processor
        self.buffer = b''
    
    def handle(self):
        """Handle client connection."""
        try:
            with self.socket:
                while True:
                    chunk = self.socket.recv(Config.CONNECTION_RECV_BUFFER)
                    if not chunk:
                        break
                    
                    self.buffer += chunk
                    
                    # Process complete messages (newline-delimited)
                    while Config.MESSAGE_DELIMITER in self.buffer:
                        message, self.buffer = self.buffer.split(Config.MESSAGE_DELIMITER, 1)
                        response = self.process_message(message)
                        if response is None:
                            print(f"WARNING: process_message returned None for message: {message[:50]}")
                            response = b'ERROR: Internal server error'
                        self.socket.sendall(response + Config.MESSAGE_DELIMITER)
        except Exception as e:
            import traceback
            print(f"Error handling client {self.addr}: {e}")
            print(f"Traceback: {traceback.format_exc()}")

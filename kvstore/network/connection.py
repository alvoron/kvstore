"""Connection handler for individual clients."""
import socket
from typing import Callable
from .protocol import Protocol


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
                    chunk = self.socket.recv(4096)
                    if not chunk:
                        break
                    
                    self.buffer += chunk
                    
                    # Process complete messages (newline-delimited)
                    while b'\n' in self.buffer:
                        message, self.buffer = self.buffer.split(b'\n', 1)
                        response = self.process_message(message)
                        self.socket.sendall(response + b'\n')
        except Exception as e:
            print(f"Error handling client {self.addr}: {e}")

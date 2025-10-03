"""Protocol parsing and formatting."""
from typing import Tuple, Optional, List


class Protocol:
    """Simple text-based protocol handler."""
    
    @staticmethod
    def escape(data: bytes) -> bytes:
        """Escape special characters in data."""
        return data.replace(b'\\', b'\\\\').replace(b'\n', b'\\n').replace(b'\r', b'\\r').replace(b'\t', b'\\t')
    
    @staticmethod
    def unescape(data: bytes) -> bytes:
        """Unescape special characters in data."""
        return data.replace(b'\\t', b'\t').replace(b'\\r', b'\r').replace(b'\\n', b'\n').replace(b'\\\\', b'\\')
    
    @staticmethod
    def parse_command(message: bytes) -> Tuple[str, Optional[bytes], Optional[bytes]]:
        """
        Parse protocol message.
        Returns (command, key, value)
        For BATCHPUT: returns (command, keys_joined, values_joined) where parts are separated by ||
        For REPLICATE: returns ('REPLICATE_<subcommand>', key, value) - handles master-to-replica commands
        """
        parts = message.split(b' ', 2)
        command = parts[0].upper().decode('utf-8')
        
        # Handle REPLICATE commands (master-to-replica communication)
        if command == 'REPLICATE':
            if len(parts) < 2:
                raise ValueError('REPLICATE requires subcommand')
            subparts = message.split(b' ', 3)
            subcommand = subparts[1].upper().decode('utf-8')
            
            if subcommand == 'PUT':
                if len(subparts) != 4:
                    raise ValueError('REPLICATE PUT requires key and value')
                return f'REPLICATE_{subcommand}', subparts[2], subparts[3]
            
            elif subcommand == 'BATCHPUT':
                if len(subparts) != 4:
                    raise ValueError('REPLICATE BATCHPUT requires keys and values')
                return f'REPLICATE_{subcommand}', subparts[2], subparts[3]
            
            elif subcommand == 'DELETE':
                if len(subparts) != 3:
                    raise ValueError('REPLICATE DELETE requires key')
                return f'REPLICATE_{subcommand}', subparts[2], None
            
            else:
                raise ValueError(f'Unknown REPLICATE subcommand: {subcommand}')
        
        if command == 'PUT':
            if len(parts) < 2:
                raise ValueError('PUT requires key')
            # Handle empty value case - if only 2 parts, value is empty
            key = parts[1]
            value = parts[2] if len(parts) == 3 else b''
            return command, key, Protocol.unescape(value)
        
        elif command == 'BATCHPUT':
            if len(parts) != 3:
                raise ValueError('BATCHPUT requires keys and values')
            # Format: BATCHPUT key1||key2||key3 val1||val2||val3
            return command, parts[1], parts[2]
        
        elif command == 'READRANGE':
            if len(parts) != 3:
                raise ValueError('READRANGE requires start_key and end_key')
            # Format: READRANGE start_key end_key
            return command, parts[1], parts[2]
        
        elif command in ('READ', 'DELETE'):
            if len(parts) != 2:
                raise ValueError(f'{command} requires key')
            return command, parts[1], None
        
        else:
            raise ValueError(f'Unknown command: {command}')
    
    @staticmethod
    def format_response(success: bool, data: Optional[bytes] = None) -> bytes:
        """Format response message."""
        if data is not None:
            return data
        return b'OK' if success else b'ERROR'
    
    @staticmethod
    def format_not_found() -> bytes:
        """Format NOT_FOUND response."""
        return b'NOT_FOUND'
    
    @staticmethod
    def format_error(message: str) -> bytes:
        """Format error message."""
        return f'ERROR: {message}'.encode()

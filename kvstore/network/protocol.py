"""Protocol parsing and formatting."""
from typing import Tuple, Optional


class Protocol:
    """Simple text-based protocol handler."""

    @staticmethod
    def escape(data: bytes) -> bytes:
        """Escape special characters in data."""
        return data.replace(b'\\', b'\\\\').replace(b'\n', b'\\n').replace(b'\r', b'\\r').replace(b'\t', b'\\t')

    @staticmethod
    def unescape(data: bytes) -> bytes:
        """Unescape special characters in data."""
        # Use placeholder to avoid double-unescaping
        # First replace \\\\ with a placeholder that won't appear in data
        data = data.replace(b'\\\\', b'\x00')  # NULL byte as placeholder
        data = data.replace(b'\\n', b'\n')
        data = data.replace(b'\\r', b'\r')
        data = data.replace(b'\\t', b'\t')
        data = data.replace(b'\x00', b'\\')  # Restore backslashes
        return data

    @staticmethod
    def _parse_replicate_command(message: bytes) -> Tuple[str, Optional[bytes], Optional[bytes]]:
        """Parse REPLICATE command from master to replica."""
        subparts = message.split(b' ', 3)
        if len(subparts) < 2:
            raise ValueError('REPLICATE requires subcommand')

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

    @staticmethod
    def _parse_put_command(parts: list) -> Tuple[str, bytes, bytes]:
        """Parse PUT command."""
        if len(parts) < 2:
            raise ValueError('PUT requires key')
        key = parts[1]
        value = parts[2] if len(parts) == 3 else b''
        return 'PUT', key, Protocol.unescape(value)

    @staticmethod
    def _parse_batchput_command(parts: list) -> Tuple[str, bytes, bytes]:
        """Parse BATCHPUT command."""
        if len(parts) != 3:
            raise ValueError('BATCHPUT requires keys and values')
        return 'BATCHPUT', parts[1], parts[2]

    @staticmethod
    def _parse_readrange_command(parts: list) -> Tuple[str, bytes, bytes]:
        """Parse READRANGE command."""
        if len(parts) != 3:
            raise ValueError('READRANGE requires start_key and end_key')
        return 'READRANGE', parts[1], parts[2]

    @staticmethod
    def _parse_simple_command(command: str, parts: list) -> Tuple[str, bytes, None]:
        """Parse READ or DELETE command."""
        if len(parts) != 2:
            raise ValueError(f'{command} requires key')
        return command, parts[1], None

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

        # Dispatch to specific parsers
        if command == 'REPLICATE':
            return Protocol._parse_replicate_command(message)
        elif command == 'PUT':
            return Protocol._parse_put_command(parts)
        elif command == 'BATCHPUT':
            return Protocol._parse_batchput_command(parts)
        elif command == 'READRANGE':
            return Protocol._parse_readrange_command(parts)
        elif command in ('READ', 'DELETE'):
            return Protocol._parse_simple_command(command, parts)
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

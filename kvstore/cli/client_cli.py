"""Client CLI."""
import argparse
import sys
from kvstore.network.client import KVClient, KVClientError
from kvstore.utils.config import Config


def handle_put(client, key, value):
    """Handle PUT command."""
    if not value:
        print("Error: PUT requires a value")
        return 1
    result = client.put(key, value)
    print("OK" if result else "ERROR")
    return 0


def handle_batchput(client, key, value):
    """Handle BATCHPUT command."""
    if not value:
        print("Error: BATCHPUT requires values")
        return 1
    keys = key.split(',')
    values = value.split(',')
    if len(keys) != len(values):
        print("Error: Number of keys and values must match")
        return 1
    result = client.batch_put(keys, values)
    print("OK" if result else "ERROR")
    return 0


def handle_read(client, key, value):
    """Handle READ command."""
    result = client.read(key)
    print(result if result else "NOT_FOUND")
    return 0


def handle_readrange(client, key, value):
    """Handle READRANGE command."""
    if not value:
        print("Error: READRANGE requires end_key")
        return 1
    results = client.read_key_range(key, value)
    if results:
        for k, v in sorted(results.items()):
            print(f"{k}: {v}")
    else:
        print("NOT_FOUND")
    return 0


def handle_delete(client, key, value):
    """Handle DELETE command."""
    result = client.delete(key)
    print("OK" if result else "NOT_FOUND")
    return 0


def main():
    """Main entry point for client CLI."""
    parser = argparse.ArgumentParser(description='KVStore Client')
    parser.add_argument('--host', default=Config.CLIENT_HOST, help=f'Server host (default: {Config.CLIENT_HOST})')
    parser.add_argument('--port', type=int, default=Config.CLIENT_PORT, help=f'Server port (default: {Config.CLIENT_PORT})')
    parser.add_argument('command', choices=['put', 'read', 'delete', 'batchput', 'readrange'],
                        help='Command to execute')
    parser.add_argument('key',
                        help='Key (or comma-separated keys for batchput, or start_key for readrange)')
    parser.add_argument('value', nargs='?',
                        help='Value (for PUT) or comma-separated values (for BATCHPUT) or end_key (for READRANGE)')
    args = parser.parse_args()

    client = KVClient(args.host, args.port)

    handlers = {
        'put': handle_put,
        'batchput': handle_batchput,
        'read': handle_read,
        'readrange': handle_readrange,
        'delete': handle_delete,
    }

    handler = handlers.get(args.command)
    if handler:
        try:
            return handler(client, args.key, args.value)
        except KVClientError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    return 0


if __name__ == '__main__':
    exit(main())

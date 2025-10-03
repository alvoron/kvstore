"""Client CLI."""
import argparse
from kvstore.network.client import KVClient


def main():
    """Main entry point for client CLI."""
    parser = argparse.ArgumentParser(description='KVStore Client')
    parser.add_argument('--host', default='localhost', help='Server host')
    parser.add_argument('--port', type=int, default=5555, help='Server port')
    parser.add_argument('command', choices=['put', 'read', 'delete', 'batchput', 'readrange'], help='Command to execute')
    parser.add_argument('key', help='Key (or comma-separated keys for batchput, or start_key for readrange)')
    parser.add_argument('value', nargs='?', help='Value (for PUT) or comma-separated values (for BATCHPUT) or end_key (for READRANGE)')
    args = parser.parse_args()
    
    client = KVClient(args.host, args.port)
    
    if args.command == 'put':
        if not args.value:
            print("Error: PUT requires a value")
            return 1
        result = client.put(args.key, args.value)
        print("OK" if result else "ERROR")
    
    elif args.command == 'batchput':
        if not args.value:
            print("Error: BATCHPUT requires values")
            return 1
        keys = args.key.split(',')
        values = args.value.split(',')
        if len(keys) != len(values):
            print("Error: Number of keys and values must match")
            return 1
        result = client.batch_put(keys, values)
        print("OK" if result else "ERROR")
    
    elif args.command == 'read':
        result = client.read(args.key)
        print(result if result else "NOT_FOUND")
    
    elif args.command == 'readrange':
        if not args.value:
            print("Error: READRANGE requires end_key")
            return 1
        results = client.read_key_range(args.key, args.value)
        if results:
            for key, value in sorted(results.items()):
                print(f"{key}: {value}")
        else:
            print("NOT_FOUND")
    
    elif args.command == 'delete':
        result = client.delete(args.key)
        print("OK" if result else "NOT_FOUND")
    
    return 0


if __name__ == '__main__':
    exit(main())

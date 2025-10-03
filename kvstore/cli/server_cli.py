"""Server CLI."""
import argparse
from kvstore.network.server import KVServer


def main():
    """Main entry point for server CLI."""
    parser = argparse.ArgumentParser(description='KVStore Server')
    parser.add_argument('--host', default='0.0.0.0', help='Server host')
    parser.add_argument('--port', type=int, default=5555, help='Server port')
    parser.add_argument('--data-dir', default='./kvstore_data', help='Data directory')
    args = parser.parse_args()
    
    server = KVServer(args.host, args.port, args.data_dir)
    server.start()


if __name__ == '__main__':
    main()

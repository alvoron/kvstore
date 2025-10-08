"""Server CLI."""
import argparse
import sys
from kvstore.network.server import KVServer
from kvstore.core.store import DataDirectoryLockError
from kvstore.utils.config import Config


def parse_replica_addresses(replicas_arg: str) -> list[tuple[str, int]]:
    """
    Parse comma-separated replica addresses.

    Args:
        replicas_arg: Comma-separated list of host:port addresses

    Returns:
        List of (host, port) tuples
    """
    replica_addresses = []
    for addr in replicas_arg.split(','):
        addr = addr.strip()
        if ':' in addr:
            host, port = addr.split(':', 1)
            try:
                replica_addresses.append((host, int(port)))
            except ValueError:
                print(f"Warning: Invalid port number in '{addr}' (expected host:port)", file=sys.stderr)
        else:
            print(f"Warning: Invalid replica address format: '{addr}' (expected host:port)", file=sys.stderr)
    
    return replica_addresses


def main():
    """Main entry point for server CLI."""
    parser = argparse.ArgumentParser(description='KVStore Server')
    parser.add_argument('--host', default=Config.HOST, help=f'Server host (default: {Config.HOST})')
    parser.add_argument('--port', type=int, default=Config.PORT, help=f'Server port (default: {Config.PORT})')
    parser.add_argument('--data-dir', default=Config.DATA_DIR, help=f'Data directory (default: {Config.DATA_DIR})')
    parser.add_argument('--replica', action='store_true', help='Run as replica node (accepts REPLICATE commands)')
    parser.add_argument('--replicas', help='Comma-separated list of replica addresses (host:port,host:port,...)')
    parser.add_argument('--replication-mode', choices=['async', 'sync'], default=Config.REPLICATION_MODE,
                        help=f'Replication mode: async (default) or sync')
    args = parser.parse_args()

    # Configure replication if replicas are specified
    if args.replicas and not args.replica:
        Config.REPLICATION_ENABLED = True
        Config.REPLICATION_MODE = args.replication_mode
        Config.REPLICA_ADDRESSES = parse_replica_addresses(args.replicas)
        
        replica_count = len(Config.REPLICA_ADDRESSES)
        print(f"Replication enabled with {replica_count} replica(s) in {args.replication_mode} mode")

    try:
        server = KVServer(args.host, args.port, args.data_dir, is_replica=args.replica)
        
        node_type = "replica" if args.replica else "master"
        print(f"Starting {node_type} node on {args.host}:{args.port}")

        server.start()
    except DataDirectoryLockError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nShutdown requested... exiting")
        sys.exit(0)
    except Exception as e:
        print(f"Error starting server: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

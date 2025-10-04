"""
Network protocol tests for kvstore client and server.

Tests cover:
- Client-server communication
- Protocol parsing and formatting
- Connection handling
- Error responses
- Multiple concurrent clients
"""
import time
import socket
import threading
from kvstore.network import KVServer, KVClient


class TestClientServerBasic:
    """Test basic client-server operations."""

    def test_server_starts_and_stops(self, tmp_path):
        """Test that server can start and stop cleanly."""
        server = KVServer(host="localhost", port=0, data_dir=str(tmp_path))

        # Start server in background
        server_thread = threading.Thread(target=server.start, daemon=True)
        server_thread.start()

        time.sleep(0.1)  # Give server time to start

        assert server.running

        server.stop()
        time.sleep(0.1)

        assert not server.running

    def test_client_put_and_read(self, tmp_path):
        """Test basic client PUT and READ operations."""
        # Start server
        server = KVServer(host="localhost", port=0, data_dir=str(tmp_path))

        server_thread = threading.Thread(target=server.start, daemon=True)
        server_thread.start()
        time.sleep(0.1)

        actual_port = server.server_socket.getsockname()[1]

        try:
            # Use client
            client = KVClient(host="localhost", port=actual_port)

            assert client.put("key1", "value1")
            assert client.read("key1") == "value1"

        finally:
            server.stop()

    def test_client_delete(self, tmp_path):
        """Test client DELETE operation."""
        server = KVServer(host="localhost", port=0, data_dir=str(tmp_path))

        server_thread = threading.Thread(target=server.start, daemon=True)
        server_thread.start()
        time.sleep(0.1)

        actual_port = server.server_socket.getsockname()[1]

        try:
            client = KVClient(host="localhost", port=actual_port)

            client.put("key1", "value1")
            assert client.delete("key1")
            assert client.read("key1") is None

        finally:
            server.stop()

    def test_client_batch_put(self, tmp_path):
        """Test client BATCHPUT operation."""
        server = KVServer(host="localhost", port=0, data_dir=str(tmp_path))

        server_thread = threading.Thread(target=server.start, daemon=True)
        server_thread.start()
        time.sleep(0.1)

        actual_port = server.server_socket.getsockname()[1]

        try:
            client = KVClient(host="localhost", port=actual_port)

            keys = ["key1", "key2", "key3"]
            values = ["val1", "val2", "val3"]

            assert client.batch_put(keys, values)

            for key, expected_value in zip(keys, values):
                assert client.read(key) == expected_value

        finally:
            server.stop()

    def test_client_read_range(self, tmp_path):
        """Test client READRANGE operation."""
        server = KVServer(host="localhost", port=0, data_dir=str(tmp_path))

        server_thread = threading.Thread(target=server.start, daemon=True)
        server_thread.start()
        time.sleep(0.1)

        actual_port = server.server_socket.getsockname()[1]

        try:
            client = KVClient(host="localhost", port=actual_port)

            # Put some data
            client.put("a", "val_a")
            client.put("b", "val_b")
            client.put("c", "val_c")
            client.put("d", "val_d")

            result = client.read_key_range("b", "c")

            assert result == {"b": "val_b", "c": "val_c"}

        finally:
            server.stop()

    def test_read_nonexistent_key(self, tmp_path):
        """Test reading a key that doesn't exist returns None."""
        server = KVServer(host="localhost", port=0, data_dir=str(tmp_path))

        server_thread = threading.Thread(target=server.start, daemon=True)
        server_thread.start()
        time.sleep(0.1)

        actual_port = server.server_socket.getsockname()[1]

        try:
            client = KVClient(host="localhost", port=actual_port)

            result = client.read("nonexistent_key")
            assert result is None

        finally:
            server.stop()

    def test_delete_nonexistent_key(self, tmp_path):
        """Test deleting a nonexistent key returns False."""
        server = KVServer(host="localhost", port=0, data_dir=str(tmp_path))

        server_thread = threading.Thread(target=server.start, daemon=True)
        server_thread.start()
        time.sleep(0.1)

        actual_port = server.server_socket.getsockname()[1]

        try:
            client = KVClient(host="localhost", port=actual_port)

            result = client.delete("nonexistent_key")
            assert not result

        finally:
            server.stop()


class TestMultipleClients:
    """Test multiple concurrent clients."""

    def test_multiple_clients_concurrent_reads(self, tmp_path):
        """Test multiple clients reading concurrently."""
        server = KVServer(host="localhost", port=0, data_dir=str(tmp_path))

        server_thread = threading.Thread(target=server.start, daemon=True)
        server_thread.start()
        time.sleep(0.1)

        actual_port = server.server_socket.getsockname()[1]

        try:
            # Setup data
            setup_client = KVClient(host="localhost", port=actual_port)
            setup_client.put("shared_key", "shared_value")

            results = []
            errors = []

            def read_from_client():
                try:
                    client = KVClient(host="localhost", port=actual_port)
                    value = client.read("shared_key")
                    results.append(value)
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=read_from_client) for _ in range(10)]

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0
            assert all(v == "shared_value" for v in results)

        finally:
            server.stop()

    def test_multiple_clients_concurrent_writes(self, tmp_path):
        """Test multiple clients writing concurrently."""
        server = KVServer(host="localhost", port=0, data_dir=str(tmp_path))

        server_thread = threading.Thread(target=server.start, daemon=True)
        server_thread.start()
        time.sleep(0.1)

        actual_port = server.server_socket.getsockname()[1]

        try:
            errors = []

            def write_from_client(client_id):
                try:
                    client = KVClient(host="localhost", port=actual_port)
                    key = f"key_{client_id}"
                    value = f"value_{client_id}"
                    client.put(key, value)
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=write_from_client, args=(i,)) for i in range(10)]

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0

            # Verify all writes succeeded
            verify_client = KVClient(host="localhost", port=actual_port)
            for i in range(10):
                key = f"key_{i}"
                expected = f"value_{i}"
                assert verify_client.read(key) == expected

        finally:
            server.stop()

    def test_multiple_clients_mixed_operations(self, tmp_path):
        """Test multiple clients performing mixed operations."""
        server = KVServer(host="localhost", port=0, data_dir=str(tmp_path))

        server_thread = threading.Thread(target=server.start, daemon=True)
        server_thread.start()
        time.sleep(0.1)

        actual_port = server.server_socket.getsockname()[1]

        try:
            # Setup some initial data
            setup_client = KVClient(host="localhost", port=actual_port)
            for i in range(5):
                setup_client.put(f"key{i}", f"val{i}")

            errors = []

            def client_worker(worker_id):
                try:
                    client = KVClient(host="localhost", port=actual_port)

                    if worker_id % 3 == 0:
                        # Reader
                        client.read(f"key{worker_id % 5}")
                    elif worker_id % 3 == 1:
                        # Writer
                        client.put(f"new_key_{worker_id}", f"new_val_{worker_id}")
                    else:
                        # Deleter
                        client.delete(f"key{worker_id % 5}")
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=client_worker, args=(i,)) for i in range(20)]

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0

        finally:
            server.stop()


class TestProtocol:
    """Test protocol edge cases."""

    def test_special_characters_in_values(self, tmp_path):
        """Test values with special characters."""
        server = KVServer(host="localhost", port=0, data_dir=str(tmp_path))

        server_thread = threading.Thread(target=server.start, daemon=True)
        server_thread.start()
        time.sleep(0.1)

        actual_port = server.server_socket.getsockname()[1]

        try:
            client = KVClient(host="localhost", port=actual_port)

            special_values = [
                "value with spaces",
                "value\nwith\nnewlines",
                "value\twith\ttabs",
                "value:with:colons",
                "value,with,commas",
                "Hello 世界 🌍",
            ]

            for i, value in enumerate(special_values):
                key = f"key{i}"
                assert client.put(key, value)
                assert client.read(key) == value

        finally:
            server.stop()

    def test_empty_value(self, tmp_path):
        """Test storing and retrieving empty values."""
        server = KVServer(host="localhost", port=0, data_dir=str(tmp_path))

        server_thread = threading.Thread(target=server.start, daemon=True)
        server_thread.start()
        time.sleep(0.1)

        actual_port = server.server_socket.getsockname()[1]

        try:
            client = KVClient(host="localhost", port=actual_port)

            assert client.put("empty_key", "")
            assert client.read("empty_key") == ""

        finally:
            server.stop()

    def test_large_value(self, tmp_path):
        """Test storing and retrieving large values."""
        server = KVServer(host="localhost", port=0, data_dir=str(tmp_path))

        server_thread = threading.Thread(target=server.start, daemon=True)
        server_thread.start()
        time.sleep(0.1)

        actual_port = server.server_socket.getsockname()[1]

        try:
            client = KVClient(host="localhost", port=actual_port)

            large_value = "x" * 100000  # 100KB

            assert client.put("large_key", large_value)
            assert client.read("large_key") == large_value

        finally:
            server.stop()

    def test_batch_put_large_batch(self, tmp_path):
        """Test batch put with many items."""
        server = KVServer(host="localhost", port=0, data_dir=str(tmp_path))

        server_thread = threading.Thread(target=server.start, daemon=True)
        server_thread.start()
        time.sleep(0.1)

        actual_port = server.server_socket.getsockname()[1]

        try:
            client = KVClient(host="localhost", port=actual_port)

            keys = [f"key{i}" for i in range(100)]
            values = [f"val{i}" for i in range(100)]

            assert client.batch_put(keys, values)

            # Verify random samples
            for i in [0, 25, 50, 75, 99]:
                assert client.read(keys[i]) == values[i]

        finally:
            server.stop()


class TestServerRobustness:
    """Test server robustness and error handling."""

    def test_server_handles_client_disconnect(self, tmp_path):
        """Test that server continues running after client disconnect."""
        server = KVServer(host="localhost", port=0, data_dir=str(tmp_path))

        server_thread = threading.Thread(target=server.start, daemon=True)
        server_thread.start()
        time.sleep(0.1)

        actual_port = server.server_socket.getsockname()[1]

        try:
            # Connect and disconnect abruptly
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(("localhost", actual_port))
            sock.close()

            time.sleep(0.1)

            # Server should still be running
            assert server.running

            # New client should be able to connect
            client = KVClient(host="localhost", port=actual_port)
            assert client.put("key", "value")

        finally:
            server.stop()

    def test_server_data_persists_between_clients(self, tmp_path):
        """Test that data persists between different client connections."""
        server = KVServer(host="localhost", port=0, data_dir=str(tmp_path))

        server_thread = threading.Thread(target=server.start, daemon=True)
        server_thread.start()
        time.sleep(0.1)

        actual_port = server.server_socket.getsockname()[1]

        try:
            # First client writes data
            client1 = KVClient(host="localhost", port=actual_port)
            client1.put("persistent_key", "persistent_value")

            # Second client reads data
            client2 = KVClient(host="localhost", port=actual_port)
            assert client2.read("persistent_key") == "persistent_value"

        finally:
            server.stop()

    def test_sequential_client_connections(self, tmp_path):
        """Test many sequential client connections."""
        server = KVServer(host="localhost", port=0, data_dir=str(tmp_path))

        server_thread = threading.Thread(target=server.start, daemon=True)
        server_thread.start()
        time.sleep(0.1)

        actual_port = server.server_socket.getsockname()[1]

        try:
            # Make many sequential connections
            for i in range(50):
                client = KVClient(host="localhost", port=actual_port)
                client.put(f"key{i}", f"value{i}")

            # Verify all data
            verify_client = KVClient(host="localhost", port=actual_port)
            for i in range(50):
                assert verify_client.read(f"key{i}") == f"value{i}"

        finally:
            server.stop()

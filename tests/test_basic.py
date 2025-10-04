"""
Basic functionality tests for kvstore.

Tests cover:
- PUT/READ operations
- DELETE operations
- Batch operations
- Range queries
- Error handling
- Concurrency
"""
import time
import threading
from kvstore import KVStore


class TestBasicOperations:
    """Test basic PUT, READ, DELETE operations."""

    def test_put_and_read(self, temp_store):
        """Test basic put and read operations."""
        assert temp_store.put(b"key1", b"value1")
        assert temp_store.read(b"key1") == b"value1"

    def test_read_nonexistent_key(self, temp_store):
        """Test reading a key that doesn't exist."""
        assert temp_store.read(b"nonexistent") is None

    def test_put_overwrites_existing_key(self, temp_store):
        """Test that putting to an existing key overwrites the value."""
        temp_store.put(b"key1", b"value1")
        temp_store.put(b"key1", b"value2")
        assert temp_store.read(b"key1") == b"value2"

    def test_delete_existing_key(self, temp_store):
        """Test deleting an existing key."""
        temp_store.put(b"key1", b"value1")
        assert temp_store.delete(b"key1")
        assert temp_store.read(b"key1") is None

    def test_delete_nonexistent_key(self, temp_store):
        """Test deleting a key that doesn't exist."""
        assert not temp_store.delete(b"nonexistent")

    def test_empty_key(self, temp_store):
        """Test operations with empty key."""
        assert temp_store.put(b"", b"empty_key_value")
        assert temp_store.read(b"") == b"empty_key_value"

    def test_empty_value(self, temp_store):
        """Test storing empty value."""
        assert temp_store.put(b"key1", b"")
        assert temp_store.read(b"key1") == b""

    def test_large_value(self, temp_store):
        """Test storing and retrieving large values."""
        large_value = b"x" * 1000000  # 1MB
        assert temp_store.put(b"large", large_value)
        assert temp_store.read(b"large") == large_value

    def test_special_characters_in_key(self, temp_store):
        """Test keys with special characters."""
        special_keys = [
            b"key:with:colons",
            b"key\nwith\nnewlines",
            b"key\twith\ttabs",
            b"key with spaces",
            b"key@#$%^&*()",
        ]
        for key in special_keys:
            assert temp_store.put(key, b"value")
            assert temp_store.read(key) == b"value"

    def test_unicode_values(self, temp_store):
        """Test storing unicode values as bytes."""
        unicode_value = "Hello 世界 🌍".encode('utf-8')
        assert temp_store.put(b"unicode", unicode_value)
        assert temp_store.read(b"unicode") == unicode_value


class TestBatchOperations:
    """Test batch put operations."""

    def test_batch_put_success(self, temp_store):
        """Test successful batch put operation."""
        keys = [b"key1", b"key2", b"key3"]
        values = [b"val1", b"val2", b"val3"]

        assert temp_store.batch_put(keys, values)

        for key, expected_value in zip(keys, values):
            assert temp_store.read(key) == expected_value

    def test_batch_put_empty_lists(self, temp_store):
        """Test batch put with empty lists."""
        assert temp_store.batch_put([], [])

    def test_batch_put_single_item(self, temp_store):
        """Test batch put with single item."""
        assert temp_store.batch_put([b"key1"], [b"val1"])
        assert temp_store.read(b"key1") == b"val1"

    def test_batch_put_large_batch(self, temp_store):
        """Test batch put with many items."""
        keys = [f"key{i}".encode() for i in range(1000)]
        values = [f"val{i}".encode() for i in range(1000)]

        assert temp_store.batch_put(keys, values)

        # Verify random samples
        for i in [0, 100, 500, 999]:
            assert temp_store.read(keys[i]) == values[i]

    def test_batch_put_overwrites(self, temp_store):
        """Test that batch put can overwrite existing keys."""
        temp_store.put(b"key1", b"old_value")

        assert temp_store.batch_put([b"key1", b"key2"], [b"new_value", b"val2"])

        assert temp_store.read(b"key1") == b"new_value"
        assert temp_store.read(b"key2") == b"val2"


class TestRangeQueries:
    """Test range query operations."""

    def test_read_key_range_basic(self, temp_store):
        """Test basic range query."""
        # Insert keys in order
        temp_store.put(b"a", b"val_a")
        temp_store.put(b"b", b"val_b")
        temp_store.put(b"c", b"val_c")
        temp_store.put(b"d", b"val_d")

        result = temp_store.read_key_range(b"b", b"c")

        assert result == {b"b": b"val_b", b"c": b"val_c"}

    def test_read_key_range_single_key(self, temp_store):
        """Test range query with start == end."""
        temp_store.put(b"key", b"value")

        result = temp_store.read_key_range(b"key", b"key")

        assert result == {b"key": b"value"}

    def test_read_key_range_no_matches(self, temp_store):
        """Test range query with no matching keys."""
        temp_store.put(b"a", b"val_a")
        temp_store.put(b"z", b"val_z")

        result = temp_store.read_key_range(b"m", b"n")

        assert result == {}

    def test_read_key_range_all_keys(self, temp_store):
        """Test range query that spans all keys."""
        temp_store.put(b"key1", b"val1")
        temp_store.put(b"key2", b"val2")
        temp_store.put(b"key3", b"val3")

        # Using min/max possible byte values
        result = temp_store.read_key_range(b"\x00", b"\xff" * 10)

        assert len(result) == 3

    def test_read_key_range_numeric_keys(self, temp_store):
        """Test range query with numeric string keys."""
        for i in range(10):
            temp_store.put(f"{i:03d}".encode(), f"val{i}".encode())

        result = temp_store.read_key_range(b"003", b"007")

        assert len(result) == 5
        assert b"003" in result
        assert b"007" in result

    def test_read_key_range_excludes_deleted(self, temp_store):
        """Test that range query excludes deleted keys."""
        temp_store.put(b"a", b"val_a")
        temp_store.put(b"b", b"val_b")
        temp_store.put(b"c", b"val_c")

        temp_store.delete(b"b")

        result = temp_store.read_key_range(b"a", b"c")

        assert b"b" not in result
        assert result == {b"a": b"val_a", b"c": b"val_c"}


class TestConcurrency:
    """Test concurrent operations."""

    def _read_value(self, store, key, results, errors):
        """Helper for reading a value in concurrent tests."""
        try:
            value = store.read(key)
            results.append(value)
        except Exception as e:
            errors.append(e)

    def _write_value(self, store, key, value, errors):
        """Helper for writing a value in concurrent tests."""
        try:
            store.put(key, value)
        except Exception as e:
            errors.append(e)

    def _delete_value(self, store, key, results, errors):
        """Helper for deleting a value in concurrent tests."""
        try:
            result = store.delete(key)
            results.append(result)
        except Exception as e:
            errors.append(e)

    def test_concurrent_reads(self, temp_store):
        """Test multiple concurrent reads."""
        temp_store.put(b"key1", b"value1")

        results = []
        errors = []

        threads = [
            threading.Thread(target=self._read_value, args=(temp_store, b"key1", results, errors))
            for _ in range(10)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert all(v == b"value1" for v in results)

    def test_concurrent_writes(self, temp_store):
        """Test multiple concurrent writes."""
        errors = []

        threads = [
            threading.Thread(
                target=self._write_value,
                args=(temp_store, f"key{i}".encode(), f"value{i}".encode(), errors)
            )
            for i in range(10)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

        # Verify all writes succeeded
        for i in range(10):
            key = f"key{i}".encode()
            expected_value = f"value{i}".encode()
            assert temp_store.read(key) == expected_value

    def test_concurrent_read_write(self, temp_store):
        """Test concurrent reads and writes."""
        temp_store.put(b"counter", b"0")

        errors = []
        reads = []

        # Writer updates counter multiple times
        def writer_task():
            for i in range(5):
                self._write_value(temp_store, b"counter", str(i).encode(), errors)
                time.sleep(0.001)

        # Readers read counter multiple times
        def reader_task():
            for _ in range(10):
                self._read_value(temp_store, b"counter", reads, errors)
                time.sleep(0.001)

        writer_thread = threading.Thread(target=writer_task)
        reader_threads = [threading.Thread(target=reader_task) for _ in range(3)]

        writer_thread.start()
        for t in reader_threads:
            t.start()

        writer_thread.join()
        for t in reader_threads:
            t.join()

        assert len(errors) == 0
        assert len(reads) > 0  # Got some reads

    def test_concurrent_deletes(self, temp_store):
        """Test concurrent deletes don't cause errors."""
        # Setup keys
        for i in range(10):
            temp_store.put(f"key{i}".encode(), f"value{i}".encode())

        errors = []
        results = []

        threads = [
            threading.Thread(
                target=self._delete_value,
                args=(temp_store, f"key{i}".encode(), results, errors)
            )
            for i in range(10)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

        # All keys should be deleted
        for i in range(10):
            assert temp_store.read(f"key{i}".encode()) is None


class TestPersistence:
    """Test data persistence and recovery."""

    def test_data_survives_close_and_reopen(self, tmp_path):
        """Test that data persists after closing and reopening store."""
        # Create store and add data
        store1 = KVStore(str(tmp_path))
        store1.put(b"key1", b"value1")
        store1.put(b"key2", b"value2")
        store1.close()

        # Reopen store
        store2 = KVStore(str(tmp_path))

        # Verify data is still there
        assert store2.read(b"key1") == b"value1"
        assert store2.read(b"key2") == b"value2"

        store2.close()

    def test_wal_recovery(self, tmp_path):
        """Test that WAL is replayed on recovery."""
        # Create store and add data
        store1 = KVStore(str(tmp_path))
        store1.put(b"key1", b"value1")

        # Simulate crash (don't close properly - just delete reference)
        # This leaves WAL with entries that haven't been checkpointed
        del store1

        # Reopen - should replay WAL
        store2 = KVStore(str(tmp_path))

        # Verify data was recovered
        assert store2.read(b"key1") == b"value1"

        store2.close()

    def test_batch_put_persistence(self, tmp_path):
        """Test that batch operations persist correctly."""
        store1 = KVStore(str(tmp_path))

        keys = [f"key{i}".encode() for i in range(100)]
        values = [f"val{i}".encode() for i in range(100)]
        store1.batch_put(keys, values)

        store1.close()

        store2 = KVStore(str(tmp_path))

        # Verify all keys
        for key, expected_value in zip(keys, values):
            assert store2.read(key) == expected_value

        store2.close()

    def test_delete_persistence(self, tmp_path):
        """Test that deletes persist correctly."""
        store1 = KVStore(str(tmp_path))

        store1.put(b"key1", b"value1")
        store1.put(b"key2", b"value2")
        store1.delete(b"key1")

        store1.close()

        store2 = KVStore(str(tmp_path))

        # Verify delete persisted
        assert store2.read(b"key1") is None
        assert store2.read(b"key2") == b"value2"

        store2.close()


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_multiple_deletes_same_key(self, temp_store):
        """Test deleting the same key multiple times."""
        temp_store.put(b"key1", b"value1")

        assert temp_store.delete(b"key1")  # First delete succeeds
        assert not temp_store.delete(b"key1")  # Second delete fails (key not found)
        assert not temp_store.delete(b"key1")  # Third delete fails

    def test_update_after_delete(self, temp_store):
        """Test updating a key after it's been deleted."""
        temp_store.put(b"key1", b"value1")
        temp_store.delete(b"key1")

        assert temp_store.put(b"key1", b"new_value")
        assert temp_store.read(b"key1") == b"new_value"

    def test_many_updates_same_key(self, temp_store):
        """Test many updates to the same key."""
        for i in range(100):
            temp_store.put(b"key", f"value{i}".encode())

        assert temp_store.read(b"key") == b"value99"

    def test_sequential_operations(self, temp_store):
        """Test a sequence of mixed operations."""
        # Put some data
        temp_store.put(b"a", b"1")
        temp_store.put(b"b", b"2")
        temp_store.put(b"c", b"3")

        # Update some
        temp_store.put(b"a", b"10")

        # Delete some
        temp_store.delete(b"b")

        # Batch put
        temp_store.batch_put([b"d", b"e"], [b"4", b"5"])

        # Verify final state
        assert temp_store.read(b"a") == b"10"
        assert temp_store.read(b"b") is None
        assert temp_store.read(b"c") == b"3"
        assert temp_store.read(b"d") == b"4"
        assert temp_store.read(b"e") == b"5"

    def test_range_query_after_updates_and_deletes(self, temp_store):
        """Test range query reflects updates and deletes."""
        # Initial data
        for i in range(10):
            temp_store.put(f"key{i:02d}".encode(), f"val{i}".encode())

        # Update some
        temp_store.put(b"key05", b"updated")

        # Delete some
        temp_store.delete(b"key03")
        temp_store.delete(b"key07")

        result = temp_store.read_key_range(b"key00", b"key09")

        assert len(result) == 8  # 10 - 2 deleted
        assert result[b"key05"] == b"updated"
        assert b"key03" not in result
        assert b"key07" not in result

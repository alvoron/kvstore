"""Tests for background compaction functionality."""
import pytest
import time
import shutil
from pathlib import Path
from kvstore.core.store import KVStore
from kvstore.utils.config import Config


class TestCompaction:
    """Test compaction functionality."""

    @pytest.fixture
    def temp_store(self, tmp_path):
        """Create a temporary store for testing."""
        # Save original config
        original_enabled = Config.COMPACTION_ENABLED
        original_threshold = Config.COMPACTION_THRESHOLD
        original_min_size = Config.COMPACTION_MIN_FILE_SIZE
        
        # Configure for testing
        Config.COMPACTION_ENABLED = False  # Manual control in tests
        Config.COMPACTION_THRESHOLD = 0.3  # 30%
        Config.COMPACTION_MIN_FILE_SIZE = 100  # Low threshold for testing
        
        store = KVStore(data_dir=str(tmp_path / 'test_data'))
        
        yield store
        
        # Cleanup
        store.close()
        
        # Restore config
        Config.COMPACTION_ENABLED = original_enabled
        Config.COMPACTION_THRESHOLD = original_threshold
        Config.COMPACTION_MIN_FILE_SIZE = original_min_size

    def test_should_compact_empty_file(self, temp_store):
        """Test that empty file doesn't need compaction."""
        assert not temp_store._should_compact()

    def test_should_compact_small_file(self, temp_store):
        """Test that small files below threshold don't need compaction."""
        # Insert a small amount of data
        temp_store.put(b'key1', b'value1')
        
        # File too small (< COMPACTION_MIN_FILE_SIZE)
        assert temp_store.data_file.size < Config.COMPACTION_MIN_FILE_SIZE
        assert not temp_store._should_compact()

    def test_should_compact_no_deletions(self, temp_store):
        """Test that file with no deletions doesn't need compaction."""
        # Insert enough data to exceed min size
        for i in range(100):
            key = f'key_{i:03d}'.encode()
            value = f'value_{i:03d}_' + ('x' * 100)
            temp_store.put(key, value.encode())
        
        # No deletions, so no dead space
        assert not temp_store._should_compact()

    def test_should_compact_with_deletions(self, temp_store):
        """Test that file with sufficient deletions needs compaction."""
        # Insert data
        for i in range(100):
            key = f'key_{i:03d}'.encode()
            value = f'value_{i:03d}_' + ('x' * 100)
            temp_store.put(key, value.encode())
        
        # Delete half (50% dead space)
        for i in range(0, 100, 2):
            key = f'key_{i:03d}'.encode()
            temp_store.delete(key)
        
        # Should need compaction (50% > 30% threshold)
        assert temp_store._should_compact()

    def test_compact_basic(self, temp_store):
        """Test basic compaction functionality."""
        # Insert 100 entries
        for i in range(100):
            key = f'key_{i:03d}'.encode()
            value = f'value_{i:03d}_' + ('x' * 100)
            temp_store.put(key, value.encode())
        
        size_before = temp_store.data_file.size
        entries_before = len(temp_store.index.index)
        
        # Delete 50 entries
        for i in range(0, 100, 2):
            key = f'key_{i:03d}'.encode()
            temp_store.delete(key)
        
        entries_after_delete = len(temp_store.index.index)
        assert entries_after_delete == 50
        
        # File size unchanged (append-only)
        assert temp_store.data_file.size == size_before
        
        # Compact
        temp_store._compact()
        
        # Check results
        size_after = temp_store.data_file.size
        entries_after_compact = len(temp_store.index.index)
        
        # File should be smaller
        assert size_after < size_before
        
        # Should have reclaimed ~50% space
        reclaimed_ratio = (size_before - size_after) / size_before
        assert 0.4 < reclaimed_ratio < 0.6  # Around 50%
        
        # Entry count unchanged
        assert entries_after_compact == 50

    def test_compact_data_integrity(self, temp_store):
        """Test that compaction preserves data integrity."""
        # Insert 100 entries
        test_data = {}
        for i in range(100):
            key = f'key_{i:03d}'.encode()
            value = f'value_{i:03d}_' + ('x' * 100)
            test_data[key] = value.encode()
            temp_store.put(key, value.encode())
        
        # Delete even-numbered keys
        for i in range(0, 100, 2):
            key = f'key_{i:03d}'.encode()
            temp_store.delete(key)
            del test_data[key]
        
        # Compact
        temp_store._compact()
        
        # Verify all remaining keys readable
        for key, expected_value in test_data.items():
            actual_value = temp_store.read(key)
            assert actual_value == expected_value, f"Data mismatch for {key}"
        
        # Verify deleted keys are still deleted
        for i in range(0, 100, 2):
            key = f'key_{i:03d}'.encode()
            assert temp_store.read(key) is None, f"Deleted key {key} still readable"

    def test_compact_with_overwrites(self, temp_store):
        """Test compaction with overwritten values."""
        # Insert, overwrite, then delete some keys
        for i in range(50):
            key = f'key_{i:02d}'.encode()
            temp_store.put(key, b'original_value')
        
        # Overwrite all
        for i in range(50):
            key = f'key_{i:02d}'.encode()
            temp_store.put(key, b'updated_value_' + (b'x' * 100))
        
        # Delete half
        for i in range(0, 50, 2):
            key = f'key_{i:02d}'.encode()
            temp_store.delete(key)
        
        # Should have lots of dead space (originals + deleted updates)
        assert temp_store._should_compact()
        
        # Compact
        temp_store._compact()
        
        # Verify remaining keys have updated values
        for i in range(1, 50, 2):
            key = f'key_{i:02d}'.encode()
            value = temp_store.read(key)
            assert value is not None
            assert value.startswith(b'updated_value_')

    def test_compact_empty_after_all_deletions(self, temp_store):
        """Test compaction when all entries are deleted."""
        # Insert entries
        for i in range(50):
            key = f'key_{i:02d}'.encode()
            value = b'value_' + (b'x' * 100)
            temp_store.put(key, value)
        
        size_with_data = temp_store.data_file.size
        assert size_with_data > 0
        
        # Delete all
        for i in range(50):
            key = f'key_{i:02d}'.encode()
            temp_store.delete(key)
        
        # File still has data (append-only)
        assert temp_store.data_file.size == size_with_data
        
        # Compaction with no entries should be a no-op
        temp_store._compact()
        
        # File size unchanged when no entries to compact
        assert temp_store.data_file.size == size_with_data
        assert len(temp_store.index.index) == 0

    def test_compact_concurrent_reads(self, temp_store):
        """Test that reads work during compaction."""
        import threading
        
        # Insert data
        for i in range(100):
            key = f'key_{i:03d}'.encode()
            value = f'value_{i:03d}'.encode()
            temp_store.put(key, value)
        
        # Delete half
        for i in range(0, 100, 2):
            key = f'key_{i:03d}'.encode()
            temp_store.delete(key)
        
        read_errors = []
        
        def concurrent_reads():
            """Perform reads during compaction."""
            for _ in range(50):
                for i in range(1, 100, 2):  # Read odd keys
                    key = f'key_{i:03d}'.encode()
                    try:
                        value = temp_store.read(key)
                        if value is None:
                            read_errors.append(f"Key {key} not found")
                    except Exception as e:
                        read_errors.append(f"Read error: {e}")
                time.sleep(0.001)
        
        # Start reader thread
        reader = threading.Thread(target=concurrent_reads)
        reader.start()
        
        # Compact while reading
        temp_store._compact()
        
        # Wait for reader
        reader.join(timeout=5)
        
        # No read errors should occur
        assert len(read_errors) == 0, f"Read errors: {read_errors[:5]}"

    def test_compact_concurrent_writes(self, temp_store):
        """Test that writes work during compaction."""
        import threading
        
        # Insert initial data
        for i in range(50):
            key = f'key_{i:03d}'.encode()
            value = f'value_{i:03d}'.encode()
            temp_store.put(key, value)
        
        # Delete half
        for i in range(0, 50, 2):
            key = f'key_{i:03d}'.encode()
            temp_store.delete(key)
        
        write_errors = []
        
        def concurrent_writes():
            """Perform writes during compaction."""
            for i in range(100, 150):
                key = f'key_{i:03d}'.encode()
                value = f'value_{i:03d}'.encode()
                try:
                    temp_store.put(key, value)
                except Exception as e:
                    write_errors.append(f"Write error: {e}")
                time.sleep(0.001)
        
        # Start writer thread
        writer = threading.Thread(target=concurrent_writes)
        writer.start()
        
        # Give writer time to start
        time.sleep(0.01)
        
        # Compact while writing
        temp_store._compact()
        
        # Wait for writer
        writer.join(timeout=5)
        
        # No write errors should occur
        assert len(write_errors) == 0, f"Write errors: {write_errors[:5]}"
        
        # Verify new writes are present
        for i in range(100, 150):
            key = f'key_{i:03d}'.encode()
            value = temp_store.read(key)
            assert value is not None, f"Concurrent write {key} not found"

    def test_background_compaction_disabled_by_default_on_replicas(self, tmp_path):
        """Test that compaction is disabled on replica nodes."""
        Config.COMPACTION_ENABLED = True
        store = KVStore(data_dir=str(tmp_path / 'replica_data'), is_replica=True)
        
        try:
            # Compaction should be disabled
            assert not store.compaction_enabled
        finally:
            store.close()

import pytest
from kvstore import KVStore, KVServer


@pytest.fixture
def temp_store(tmp_path):
    """Temporary KVStore instance with fast checkpoint for testing."""
    store = KVStore(str(tmp_path), checkpoint_interval=1)  # 1 second for tests instead of 10
    yield store
    store.close()


@pytest.fixture
def running_server(tmp_path):
    """Running test server with fast checkpoint for testing."""
    server = KVServer(port=0, data_dir=str(tmp_path), checkpoint_interval=1)  # 1 second for tests
    # Start in thread
    yield server
    server.stop()

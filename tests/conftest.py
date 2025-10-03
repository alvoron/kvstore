import pytest
from kvstore import KVStore, KVServer

@pytest.fixture
def temp_store(tmp_path):
    """Temporary KVStore instance."""
    store = KVStore(str(tmp_path))
    yield store
    store.close()

@pytest.fixture
def running_server(tmp_path):
    """Running test server."""
    server = KVServer(port=0, data_dir=str(tmp_path))
    # Start in thread
    yield server
    server.stop()

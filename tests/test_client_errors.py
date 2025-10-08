"""Tests for client error handling."""
import pytest
from kvstore.network.client import KVClient, KVClientError


class TestClientErrors:
    """Test client error handling."""

    def test_connection_refused(self):
        """Test that connection refused raises KVClientError."""
        client = KVClient(host='localhost', port=59999)  # Port unlikely to be in use
        
        with pytest.raises(KVClientError) as exc_info:
            client.put('key', 'value')
        
        assert "Cannot connect to server" in str(exc_info.value)
        assert "59999" in str(exc_info.value)

    def test_invalid_hostname(self):
        """Test that invalid hostname raises KVClientError."""
        client = KVClient(host='this-hostname-definitely-does-not-exist-12345')
        
        with pytest.raises(KVClientError) as exc_info:
            client.read('key')
        
        assert "Cannot resolve hostname" in str(exc_info.value)

    def test_connection_refused_on_read(self):
        """Test that connection errors occur on read operations too."""
        client = KVClient(host='localhost', port=59998)
        
        with pytest.raises(KVClientError) as exc_info:
            client.read('key')
        
        assert "Cannot connect to server" in str(exc_info.value)

    def test_connection_refused_on_delete(self):
        """Test that connection errors occur on delete operations too."""
        client = KVClient(host='localhost', port=59997)
        
        with pytest.raises(KVClientError) as exc_info:
            client.delete('key')
        
        assert "Cannot connect to server" in str(exc_info.value)

    def test_connection_refused_on_batch_put(self):
        """Test that connection errors occur on batch_put operations too."""
        client = KVClient(host='localhost', port=59996)
        
        with pytest.raises(KVClientError) as exc_info:
            client.batch_put(['key1', 'key2'], ['val1', 'val2'])
        
        assert "Cannot connect to server" in str(exc_info.value)

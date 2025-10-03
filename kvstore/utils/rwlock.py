"""Reader-Writer Lock implementation for concurrent reads and exclusive writes."""
import threading


class RWLock:
    """
    Reader-Writer Lock implementation.
    
    Allows:
    - Multiple readers to hold the lock simultaneously
    - Only one writer to hold the lock at a time
    - Writers have exclusive access (no readers or other writers)
    
    Priority: Readers have priority to prevent writer starvation in read-heavy workloads.
    """
    
    def __init__(self):
        self._readers = 0  # Number of active readers
        self._writers = 0  # Number of active writers (0 or 1)
        self._read_ready = threading.Condition(threading.Lock())
        self._write_ready = threading.Condition(threading.Lock())
    
    def acquire_read(self):
        """Acquire read lock. Multiple readers can hold this simultaneously."""
        with self._read_ready:
            # Wait while there's an active writer
            while self._writers > 0:
                self._read_ready.wait()
            self._readers += 1
    
    def release_read(self):
        """Release read lock."""
        with self._read_ready:
            self._readers -= 1
            # If no more readers, notify waiting writers
            if self._readers == 0:
                self._read_ready.notify_all()
    
    def acquire_write(self):
        """Acquire write lock. Only one writer can hold this, and no readers."""
        with self._write_ready:
            self._writers += 1
        
        # Wait for all readers to finish
        with self._read_ready:
            while self._readers > 0:
                self._read_ready.wait()
    
    def release_write(self):
        """Release write lock."""
        with self._write_ready:
            self._writers -= 1
        
        # Notify waiting readers
        with self._read_ready:
            self._read_ready.notify_all()


class ReadLock:
    """Context manager for read locks."""
    
    def __init__(self, rwlock: RWLock):
        self.rwlock = rwlock
    
    def __enter__(self):
        self.rwlock.acquire_read()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.rwlock.release_read()
        return False


class WriteLock:
    """Context manager for write locks."""
    
    def __init__(self, rwlock: RWLock):
        self.rwlock = rwlock
    
    def __enter__(self):
        self.rwlock.acquire_write()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.rwlock.release_write()
        return False

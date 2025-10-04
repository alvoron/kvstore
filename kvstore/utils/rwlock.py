"""Reader-Writer Lock implementation for concurrent reads and exclusive writes."""
import threading


class RWLock:
    """
    Reader-Writer Lock implementation.

    Allows:
    - Multiple readers to hold the lock simultaneously
    - Only one writer to hold the lock at a time
    - Writers have exclusive access (no readers or other writers)

    This is a fair implementation that prevents starvation for both readers and writers.
    """

    def __init__(self):
        self._readers = 0  # Number of active readers
        self._writer = False  # Whether a writer is active
        self._lock = threading.Lock()
        self._readers_ok = threading.Condition(self._lock)
        self._writers_ok = threading.Condition(self._lock)

    def acquire_read(self):
        """Acquire read lock. Multiple readers can hold this simultaneously."""
        with self._lock:
            # Wait while there's an active writer
            while self._writer:
                self._readers_ok.wait()
            self._readers += 1

    def release_read(self):
        """Release read lock."""
        with self._lock:
            self._readers -= 1
            # If no more readers, notify a waiting writer
            if self._readers == 0:
                self._writers_ok.notify()

    def acquire_write(self):
        """Acquire write lock. Only one writer can hold this, and no readers."""
        with self._lock:
            # Wait while there are active readers or an active writer
            while self._readers > 0 or self._writer:
                self._writers_ok.wait()
            self._writer = True

    def release_write(self):
        """Release write lock."""
        with self._lock:
            self._writer = False
            # Notify waiting writers first (FIFO fairness)
            self._writers_ok.notify()
            # Then notify all waiting readers
            self._readers_ok.notify_all()


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

"""Test to demonstrate writer-preferring behavior preventing writer starvation."""
import threading
import time
from kvstore.utils.rwlock import RWLock, ReadLock, WriteLock


def continuous_readers(rwlock, duration, results):
    """Simulate continuous stream of readers."""
    start = time.time()
    count = 0
    while time.time() - start < duration:
        with ReadLock(rwlock):
            count += 1
            time.sleep(0.001)  # Small read operation
    results['readers'] = count


def writer_attempts(rwlock, results):
    """Writer tries to acquire lock."""
    time.sleep(0.1)  # Let readers start first
    
    write_times = []
    for i in range(3):
        start = time.time()
        with WriteLock(rwlock):
            elapsed = time.time() - start
            write_times.append(elapsed)
            print(f"Writer {i+1} acquired lock after {elapsed:.3f}s")
            time.sleep(0.01)  # Quick write
    
    results['writer_times'] = write_times
    results['max_wait'] = max(write_times)


def main():
    """Test that writers don't starve with continuous readers."""
    print("Testing writer-preferring RWLock...")
    print("=" * 60)
    
    rwlock = RWLock()
    results = {}
    
    # Start continuous readers
    reader_threads = []
    for i in range(3):
        t = threading.Thread(target=continuous_readers, args=(rwlock, 2.0, results))
        t.start()
        reader_threads.append(t)
    
    # Start writer (will try to write while readers are active)
    writer_thread = threading.Thread(target=writer_attempts, args=(rwlock, results))
    writer_thread.start()
    
    # Wait for all threads
    writer_thread.join()
    for t in reader_threads:
        t.join()
    
    print("=" * 60)
    print(f"Total reader operations: {results.get('readers', 0)}")
    print(f"Writer max wait time: {results.get('max_wait', 0):.3f}s")
    print()
    
    if results.get('max_wait', float('inf')) < 0.5:
        print("✅ SUCCESS: Writer acquired lock quickly despite reader stream")
        print("   Writer-preferring lock prevents starvation!")
    else:
        print("❌ FAIL: Writer waited too long")
        print("   Writer may be starving!")


if __name__ == '__main__':
    main()

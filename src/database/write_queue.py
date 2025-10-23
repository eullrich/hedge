"""SQLite write queue for serializing database writes across threads.

This solves the classic SQLite concurrency problem: WAL mode handles concurrent
reads beautifully, but writes still need to be serialized. Instead of locking
in ThreadPoolExecutor workers, we pipe all writes through a single dedicated
writer thread that owns the DB connection.

Benefits:
- Eliminates "database is locked" errors
- Workers submit writes and move on (non-blocking)
- Can achieve 500-2k writes/sec depending on batch size
- Reads can still happen concurrently in worker threads
"""
import queue
import threading
import sqlite3
from typing import Optional, Callable, Any, Tuple
from datetime import datetime


class WriteJob:
    """A write job to be executed by the writer thread."""

    def __init__(
        self,
        sql: str,
        params: Tuple = (),
        callback: Optional[Callable] = None,
        many: bool = False
    ):
        """
        Initialize write job.

        Args:
            sql: SQL statement to execute
            params: Parameters for the SQL statement (or list of tuples for executemany)
            callback: Optional callback(cursor) after execution
            many: If True, use executemany() for batch inserts
        """
        self.sql = sql
        self.params = params
        self.callback = callback
        self.many = many
        self.submitted_at = datetime.now()


class SQLiteWriteQueue:
    """
    Thread-safe write queue for SQLite.

    Usage:
        # Start the queue
        write_queue = SQLiteWriteQueue('path/to/db.sqlite')
        write_queue.start()

        # Submit writes from any thread
        write_queue.submit('INSERT INTO table VALUES (?, ?)', (1, 2))

        # Batch writes for better performance
        write_queue.submit_many('INSERT INTO table VALUES (?, ?)', [(1, 2), (3, 4)])

        # Shutdown cleanly
        write_queue.shutdown()
    """

    def __init__(self, db_path: str, max_queue_size: int = 10000):
        """
        Initialize write queue.

        Args:
            db_path: Path to SQLite database
            max_queue_size: Maximum queue depth (blocks submissions if exceeded)
        """
        self.db_path = db_path
        self.write_queue = queue.Queue(maxsize=max_queue_size)
        self.writer_thread: Optional[threading.Thread] = None
        self.running = False
        self.stats = {
            'writes_executed': 0,
            'writes_failed': 0,
            'batches_executed': 0,
        }

    def start(self):
        """Start the writer thread."""
        if self.running:
            return

        self.running = True
        self.writer_thread = threading.Thread(
            target=self._writer_loop,
            daemon=True,
            name='SQLiteWriter'
        )
        self.writer_thread.start()
        print(f"✅ SQLite write queue started for {self.db_path}")

    def _writer_loop(self):
        """Main loop for the writer thread - owns the DB connection."""
        # Create dedicated connection for this thread
        conn = sqlite3.connect(
            self.db_path,
            isolation_level=None,  # Autocommit mode for faster writes
            timeout=60,
            check_same_thread=False
        )

        # Optimize for write performance
        conn.execute('PRAGMA journal_mode=WAL;')
        conn.execute('PRAGMA synchronous=NORMAL;')
        conn.execute('PRAGMA temp_store=MEMORY;')
        conn.execute('PRAGMA busy_timeout=60000;')

        print("📝 SQLite writer thread ready")

        while self.running:
            try:
                # Block with timeout so we can check self.running periodically
                try:
                    job = self.write_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                if job is None:  # Shutdown sentinel
                    break

                # Execute the write
                try:
                    if job.many:
                        cursor = conn.executemany(job.sql, job.params)
                        self.stats['batches_executed'] += 1
                        self.stats['writes_executed'] += len(job.params)
                    else:
                        cursor = conn.execute(job.sql, job.params)
                        self.stats['writes_executed'] += 1

                    # Call callback if provided
                    if job.callback:
                        job.callback(cursor)

                except Exception as e:
                    self.stats['writes_failed'] += 1
                    print(f"❌ SQLite write error: {e}")
                    print(f"   SQL: {job.sql[:100]}")

                finally:
                    self.write_queue.task_done()

            except Exception as e:
                print(f"❌ Writer loop error: {e}")

        conn.close()
        print("📝 SQLite writer thread stopped")

    def submit(
        self,
        sql: str,
        params: Tuple = (),
        callback: Optional[Callable] = None
    ) -> WriteJob:
        """
        Submit a single write job.

        Args:
            sql: SQL statement
            params: Parameters tuple
            callback: Optional callback(cursor) after execution

        Returns:
            The submitted WriteJob
        """
        job = WriteJob(sql, params, callback, many=False)
        self.write_queue.put(job)
        return job

    def submit_many(
        self,
        sql: str,
        params_list: list,
        callback: Optional[Callable] = None
    ) -> WriteJob:
        """
        Submit a batch write job using executemany().

        Args:
            sql: SQL statement with placeholders
            params_list: List of parameter tuples
            callback: Optional callback(cursor) after execution

        Returns:
            The submitted WriteJob
        """
        job = WriteJob(sql, params_list, callback, many=True)
        self.write_queue.put(job)
        return job

    def wait(self, timeout: Optional[float] = None):
        """
        Wait for all queued writes to complete.

        Args:
            timeout: Max seconds to wait (None = infinite)
        """
        if timeout:
            import time
            start = time.time()
            while not self.write_queue.empty():
                if time.time() - start > timeout:
                    break
                time.sleep(0.1)
        else:
            self.write_queue.join()

    def shutdown(self, wait: bool = True):
        """
        Shutdown the writer thread.

        Args:
            wait: If True, wait for queue to empty before stopping
        """
        if not self.running:
            return

        if wait:
            print("⏳ Waiting for write queue to drain...")
            self.wait()

        self.running = False
        self.write_queue.put(None)  # Sentinel to stop loop

        if self.writer_thread:
            self.writer_thread.join(timeout=5.0)

        print(f"✅ SQLite write queue stopped")
        print(f"   Stats: {self.stats['writes_executed']} writes, "
              f"{self.stats['batches_executed']} batches, "
              f"{self.stats['writes_failed']} failed")

    def get_queue_depth(self) -> int:
        """Get current queue depth."""
        return self.write_queue.qsize()

    def get_stats(self) -> dict:
        """Get queue statistics."""
        return {
            **self.stats,
            'queue_depth': self.get_queue_depth(),
            'running': self.running
        }


# Global write queue instance (singleton pattern)
_global_write_queue: Optional[SQLiteWriteQueue] = None


def get_write_queue(db_path: str = None) -> SQLiteWriteQueue:
    """
    Get or create the global write queue.

    Args:
        db_path: Database path (required on first call)

    Returns:
        The global write queue instance
    """
    global _global_write_queue

    if _global_write_queue is None:
        if db_path is None:
            raise ValueError("db_path required for first call to get_write_queue()")
        _global_write_queue = SQLiteWriteQueue(db_path)
        _global_write_queue.start()

    return _global_write_queue

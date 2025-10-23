"""Simple rate limiter for API clients."""
import time
from threading import Lock
from typing import Optional


class AdaptiveRateLimiter:
    """Rate limiter with adaptive backoff."""

    def __init__(self, max_calls: int = 45, period: int = 60, verbose: bool = False):
        """
        Initialize rate limiter.

        Args:
            max_calls: Maximum number of calls allowed
            period: Time period in seconds
            verbose: Enable verbose logging
        """
        self.max_calls = max_calls
        self.period = period
        self.verbose = verbose
        self.calls = []
        self.lock = Lock()
        self._backoff_until = 0

    def wait_if_needed(self):
        """Wait if rate limit would be exceeded."""
        with self.lock:
            now = time.time()

            # Check if we're in backoff period
            if now < self._backoff_until:
                sleep_time = self._backoff_until - now
                if self.verbose:
                    print(f"Rate limiter: Backing off for {sleep_time:.2f}s")
                time.sleep(sleep_time)
                now = time.time()

            # Remove old calls outside the period
            self.calls = [t for t in self.calls if now - t < self.period]

            # If we've hit the limit, wait
            if len(self.calls) >= self.max_calls:
                sleep_time = self.period - (now - self.calls[0])
                if self.verbose:
                    print(f"Rate limiter: Waiting {sleep_time:.2f}s")
                time.sleep(sleep_time)
                now = time.time()
                self.calls = [t for t in self.calls if now - t < self.period]

            # Record this call
            self.calls.append(now)

    def on_rate_limit_hit(self, retry_after: Optional[int] = None):
        """Handle rate limit being hit."""
        with self.lock:
            backoff = retry_after if retry_after else 60
            self._backoff_until = time.time() + backoff
            if self.verbose:
                print(f"Rate limit hit! Backing off for {backoff}s")

    def on_success(self):
        """Handle successful API call."""
        pass  # No action needed for successful calls

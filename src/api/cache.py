"""Cache manager for API responses."""
import json
import os
import time
from pathlib import Path
from typing import Optional, Any
import hashlib


class CacheManager:
    """Manages caching of API responses to disk."""

    def __init__(self, cache_dir: str = "data/cache", expiry_seconds: int = 3600):
        """
        Initialize cache manager.

        Args:
            cache_dir: Directory to store cache files
            expiry_seconds: Time in seconds before cache expires
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.expiry_seconds = expiry_seconds

    def _get_cache_key(self, url: str, params: Optional[dict] = None) -> str:
        """Generate a unique cache key from URL and parameters."""
        key_str = url
        if params:
            # Sort params for consistent hashing
            key_str += json.dumps(params, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """Get the file path for a cache key."""
        return self.cache_dir / f"{cache_key}.json"

    def get(self, url: str, params: Optional[dict] = None) -> Optional[Any]:
        """
        Retrieve cached response if available and not expired.

        Args:
            url: API endpoint URL
            params: Request parameters

        Returns:
            Cached response data or None if not found/expired
        """
        cache_key = self._get_cache_key(url, params)
        cache_path = self._get_cache_path(cache_key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, 'r') as f:
                cached_data = json.load(f)

            # Check expiry
            timestamp = cached_data.get('timestamp', 0)
            if time.time() - timestamp > self.expiry_seconds:
                # Cache expired, remove it
                cache_path.unlink()
                return None

            return cached_data.get('data')
        except (json.JSONDecodeError, KeyError):
            # Corrupted cache, remove it
            cache_path.unlink()
            return None

    def set(self, url: str, data: Any, params: Optional[dict] = None) -> None:
        """
        Cache response data.

        Args:
            url: API endpoint URL
            data: Response data to cache
            params: Request parameters
        """
        cache_key = self._get_cache_key(url, params)
        cache_path = self._get_cache_path(cache_key)

        cached_data = {
            'timestamp': time.time(),
            'url': url,
            'params': params,
            'data': data
        }

        with open(cache_path, 'w') as f:
            json.dump(cached_data, f)

    def clear(self) -> None:
        """Clear all cached data."""
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()

    def clear_expired(self) -> int:
        """
        Remove expired cache entries.

        Returns:
            Number of entries removed
        """
        removed = 0
        current_time = time.time()

        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, 'r') as f:
                    cached_data = json.load(f)

                timestamp = cached_data.get('timestamp', 0)
                if current_time - timestamp > self.expiry_seconds:
                    cache_file.unlink()
                    removed += 1
            except (json.JSONDecodeError, KeyError):
                # Corrupted cache, remove it
                cache_file.unlink()
                removed += 1

        return removed

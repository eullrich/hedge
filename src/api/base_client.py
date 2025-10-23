"""Base API client with common functionality."""
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import requests

from ..utils.rate_limiter import AdaptiveRateLimiter
from ..utils.exceptions import (
    APIConnectionException,
    APIResponseException,
    RateLimitException
)
from ..api.cache import CacheManager


class BaseAPIClient(ABC):
    """Base class for API clients with rate limiting, caching, and retry logic."""

    def __init__(
        self,
        base_url: str,
        rate_limit_calls: int = 45,
        rate_limit_period: int = 60,
        cache_expiry: int = 3600,
        max_retries: int = 3,
        timeout: int = 30,
        verbose: bool = False
    ):
        """
        Initialize base API client.

        Args:
            base_url: Base URL for API requests
            rate_limit_calls: Max calls per period
            rate_limit_period: Period in seconds
            cache_expiry: Cache expiry in seconds
            max_retries: Maximum number of retries on failure
            timeout: Request timeout in seconds
            verbose: Whether to print rate limit messages
        """
        self.base_url = base_url
        self.max_retries = max_retries
        self.timeout = timeout

        self.rate_limiter = AdaptiveRateLimiter(
            max_calls=rate_limit_calls,
            period=rate_limit_period,
            verbose=verbose
        )
        self.cache = CacheManager(expiry_seconds=cache_expiry)
        self.session = requests.Session()

        # Allow subclasses to set custom headers
        self._configure_session()

    @abstractmethod
    def _configure_session(self) -> None:
        """Configure session headers and other settings. Override in subclass."""
        pass

    def _build_url(self, endpoint: str) -> str:
        """
        Build full URL from endpoint.

        Args:
            endpoint: API endpoint

        Returns:
            Full URL
        """
        if endpoint.startswith('http'):
            return endpoint
        return f"{self.base_url}{endpoint}"

    def _get_cache_key(self, url: str, params: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate cache key from URL and parameters.

        Args:
            url: Request URL
            params: Request parameters

        Returns:
            Cache key string
        """
        if params:
            param_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
            return f"{url}?{param_str}"
        return url

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        use_cache: bool = True,
        use_rate_limit: bool = True
    ) -> Any:
        """
        Make API request with rate limiting, caching, and retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            params: Query parameters
            json: JSON body for POST requests
            use_cache: Whether to use cached responses
            use_rate_limit: Whether to apply rate limiting

        Returns:
            JSON response data

        Raises:
            APIConnectionException: On connection errors
            APIResponseException: On HTTP errors
            RateLimitException: On rate limit errors
        """
        url = self._build_url(endpoint)

        # Check cache first (only for GET requests)
        if use_cache and method.upper() == 'GET':
            cache_key = self._get_cache_key(url, params)
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        # Apply rate limiting
        if use_rate_limit:
            self.rate_limiter.wait_if_needed()

        # Retry loop with exponential backoff
        for attempt in range(self.max_retries):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json,
                    timeout=self.timeout
                )

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = float(response.headers.get('Retry-After', 15 * (2 ** attempt)))
                    self.rate_limiter.on_rate_limit_hit(retry_after)

                    if attempt == self.max_retries - 1:
                        raise RateLimitException(
                            f"Rate limit exceeded after {self.max_retries} retries",
                            retry_after=retry_after
                        )
                    continue

                # Raise for other HTTP errors
                response.raise_for_status()

                # Parse response
                data = response.json()

                # Cache response (only for GET requests)
                if use_cache and method.upper() == 'GET':
                    cache_key = self._get_cache_key(url, params)
                    self.cache.set(cache_key, data)

                # Reset backoff on success
                self.rate_limiter.on_success()

                return data

            except requests.exceptions.Timeout as e:
                if attempt == self.max_retries - 1:
                    raise APIConnectionException(f"Request timeout: {str(e)}")
                time.sleep(2 ** attempt)  # Exponential backoff

            except requests.exceptions.ConnectionError as e:
                if attempt == self.max_retries - 1:
                    raise APIConnectionException(f"Connection error: {str(e)}")
                time.sleep(2 ** attempt)

            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code

                # Already handled 429 above
                if status_code == 429:
                    continue

                # Retry on server errors (500, 502, 503, 504) with exponential backoff
                if status_code >= 500 and attempt < self.max_retries - 1:
                    backoff = 2 ** attempt  # 1s, 2s, 4s...
                    print(f"⚠️ Server error {status_code}, retrying in {backoff}s (attempt {attempt + 1}/{self.max_retries})")
                    time.sleep(backoff)
                    continue

                # Don't retry on client errors (4xx) or final attempt
                raise APIResponseException(
                    f"HTTP error: {str(e)}",
                    status_code=status_code
                )

            except requests.exceptions.JSONDecodeError as e:
                raise APIResponseException(f"Invalid JSON response: {str(e)}")

        raise APIConnectionException(f"Failed after {self.max_retries} retries")

    def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
    ) -> Any:
        """
        Make GET request.

        Args:
            endpoint: API endpoint
            params: Query parameters
            use_cache: Whether to use cache

        Returns:
            JSON response data
        """
        return self._request('GET', endpoint, params=params, use_cache=use_cache)

    def post(
        self,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        use_cache: bool = False
    ) -> Any:
        """
        Make POST request.

        Args:
            endpoint: API endpoint
            json: JSON body
            params: Query parameters
            use_cache: Whether to cache response (default: False)

        Returns:
            JSON response data
        """
        return self._request('POST', endpoint, params=params, json=json, use_cache=use_cache)

    def clear_cache(self) -> None:
        """Clear the API cache."""
        self.cache.clear()

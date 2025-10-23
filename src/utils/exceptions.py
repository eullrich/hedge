"""Custom exceptions for the application."""


class APIException(Exception):
    """Base exception for API errors."""
    pass


class APIConnectionException(APIException):
    """Exception for connection errors."""
    pass


class APIResponseException(APIException):
    """Exception for invalid API responses."""
    pass


class RateLimitException(APIException):
    """Exception for rate limit errors."""
    pass


class DataFetchException(Exception):
    """Exception for data fetching errors."""
    pass

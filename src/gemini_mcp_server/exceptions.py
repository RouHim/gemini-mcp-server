"""Custom exceptions for the Gemini MCP server."""


class GeminiMCPError(Exception):
    """Base exception for all Gemini MCP server errors."""

    def __init__(self, message: str, error_code: str | None = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class RateLimitError(GeminiMCPError):
    """Raised when API rate limits are exceeded."""

    def __init__(
        self, message: str = "Rate limit exceeded", retry_after: float | None = None
    ):
        super().__init__(message, "RATE_LIMIT_EXCEEDED")
        self.retry_after = retry_after


class QuotaExceededError(GeminiMCPError):
    """Raised when API quota is exceeded."""

    def __init__(self, message: str = "API quota exceeded"):
        super().__init__(message, "QUOTA_EXCEEDED")


class ContentPolicyError(GeminiMCPError):
    """Raised when content violates API policies."""

    def __init__(self, message: str, policy_type: str | None = None):
        super().__init__(message, "CONTENT_POLICY_VIOLATION")
        self.policy_type = policy_type


class AuthenticationError(GeminiMCPError):
    """Raised when API authentication fails."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, "AUTHENTICATION_FAILED")


class NetworkError(GeminiMCPError):
    """Raised when network operations fail."""

    def __init__(self, message: str):
        super().__init__(message, "NETWORK_ERROR")


class ValidationError(GeminiMCPError):
    """Raised when input validation fails."""

    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR")


class ModelError(GeminiMCPError):
    """Raised when model operations fail."""

    def __init__(self, message: str):
        super().__init__(message, "MODEL_ERROR")


class CircuitBreakerOpenError(GeminiMCPError):
    """Raised when circuit breaker is open."""

    def __init__(
        self, message: str = "Circuit breaker is open, service temporarily unavailable"
    ):
        super().__init__(message, "CIRCUIT_BREAKER_OPEN")

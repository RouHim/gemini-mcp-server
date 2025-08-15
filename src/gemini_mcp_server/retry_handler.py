"""Retry mechanisms and error handling for Gemini API calls."""

import asyncio
import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from google.api_core import exceptions as google_exceptions
from tenacity import (
    RetryError,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .exceptions import (
    AuthenticationError,
    CircuitBreakerOpenError,
    ContentPolicyError,
    ModelError,
    NetworkError,
    QuotaExceededError,
    RateLimitError,
)

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class CircuitBreaker:
    """Circuit breaker pattern implementation for handling repeated failures."""

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        expected_exception: type = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def can_proceed(self) -> bool:
        """Check if the circuit breaker allows the operation to proceed."""
        if self.state == "CLOSED":
            return True

        if self.state == "OPEN":
            if (
                self.last_failure_time
                and time.time() - self.last_failure_time >= self.timeout
            ):
                self.state = "HALF_OPEN"
                return True
            return False

        # HALF_OPEN state
        return True

    def on_success(self) -> None:
        """Called when operation succeeds."""
        self.failure_count = 0
        self.state = "CLOSED"

    def on_failure(self, exception: Exception) -> None:
        """Called when operation fails."""
        if isinstance(exception, self.expected_exception):
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.warning(
                    f"Circuit breaker opened after {self.failure_count} failures"
                )


# Global circuit breaker for Gemini API calls
gemini_circuit_breaker = CircuitBreaker(
    failure_threshold=3,
    timeout=300.0,
    expected_exception=Exception,  # 5 minutes
)


def map_google_exception(exception: Exception) -> Exception:
    """Map Google API exceptions to our custom exception types."""
    if isinstance(exception, google_exceptions.ResourceExhausted):
        return QuotaExceededError(str(exception))
    elif isinstance(exception, google_exceptions.TooManyRequests):
        return RateLimitError(str(exception))
    elif isinstance(
        exception,
        google_exceptions.Unauthenticated | google_exceptions.PermissionDenied,
    ):
        return AuthenticationError(str(exception))
    elif isinstance(exception, google_exceptions.InvalidArgument):
        if "content policy" in str(exception).lower():
            return ContentPolicyError(str(exception))
        return ModelError(str(exception))
    elif isinstance(
        exception,
        google_exceptions.DeadlineExceeded | google_exceptions.ServiceUnavailable,
    ):
        return NetworkError(str(exception))
    elif isinstance(exception, google_exceptions.GoogleAPIError):
        return ModelError(str(exception))
    else:
        return exception


def circuit_breaker_check(func: Callable[..., Any]) -> Any:
    """Decorator to check circuit breaker before function execution."""

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not gemini_circuit_breaker.can_proceed():
            raise CircuitBreakerOpenError()

        try:
            result = await func(*args, **kwargs)
            gemini_circuit_breaker.on_success()
            return result
        except Exception as e:
            mapped_exception = map_google_exception(e)
            gemini_circuit_breaker.on_failure(mapped_exception)
            raise mapped_exception

    return wrapper


def retry_on_failure(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: int = 2,
) -> Any:
    """Decorator for retrying failed operations with exponential backoff."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(
                multiplier=base_delay, max=max_delay, exp_base=exponential_base
            ),
            retry=retry_if_exception_type(
                (
                    NetworkError,
                    ModelError,
                    RateLimitError,
                )
            ),
            before_sleep=before_sleep_log(logger, logging.WARNING),
        )
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except RetryError as e:
                # If all retries failed, raise the last exception
                if e.last_attempt and e.last_attempt.exception():
                    exc = e.last_attempt.exception()
                    if exc:
                        raise exc
                raise

        return wrapper

    return decorator


async def handle_rate_limit(exception: RateLimitError, attempt: int = 1) -> None:
    """Handle rate limit errors with appropriate backoff."""
    base_delay = 2.0
    max_delay = 300.0  # 5 minutes max

    if hasattr(exception, "retry_after") and exception.retry_after:
        delay = min(exception.retry_after, max_delay)
    else:
        delay = min(base_delay * (2**attempt), max_delay)

    logger.warning(f"Rate limited, waiting {delay} seconds before retry")
    await asyncio.sleep(delay)


def get_user_friendly_error_message(exception: Exception) -> str:
    """Convert exceptions to user-friendly error messages."""
    if isinstance(exception, RateLimitError):
        return (
            "Rate limit exceeded. Please wait a moment before making another request."
        )

    elif isinstance(exception, QuotaExceededError):
        return (
            "API quota exceeded. Please try again later or check your API usage limits."
        )

    elif isinstance(exception, ContentPolicyError):
        return "Content violates platform policies. Please modify your request and try again."

    elif isinstance(exception, AuthenticationError):
        return "Authentication failed. Please check your API key configuration."

    elif isinstance(exception, NetworkError):
        return "Network error occurred. Please check your connection and try again."

    elif isinstance(exception, CircuitBreakerOpenError):
        return "Service temporarily unavailable due to repeated failures. Please try again later."

    elif isinstance(exception, ModelError):
        return f"Model error: {exception!s}"

    else:
        return f"An unexpected error occurred: {exception!s}"


def create_structured_error_response(exception: Exception) -> dict[str, Any]:
    """Create a structured error response for MCP clients."""
    return {
        "error": True,
        "error_code": getattr(exception, "error_code", "UNKNOWN_ERROR"),
        "message": get_user_friendly_error_message(exception),
        "details": str(exception) if logger.isEnabledFor(logging.DEBUG) else None,
        "timestamp": time.time(),
    }

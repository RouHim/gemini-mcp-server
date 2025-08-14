import asyncio
import time
from typing import Optional


class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, max_calls: int, time_window: int):
        """
        Initialize rate limiter.

        Args:
            max_calls: Maximum number of calls allowed
            time_window: Time window in seconds
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        """
        Acquire permission to make a call.

        Returns:
            True if call is allowed, False if rate limited
        """
        async with self._lock:
            now = time.time()

            # Remove old calls outside the time window
            self.calls = [
                call_time
                for call_time in self.calls
                if now - call_time < self.time_window
            ]

            # Check if we can make a new call
            if len(self.calls) < self.max_calls:
                self.calls.append(now)
                return True

            return False

    async def wait_time(self) -> Optional[float]:
        """
        Get the time to wait before next call is allowed.

        Returns:
            Seconds to wait, or None if call can be made immediately
        """
        async with self._lock:
            now = time.time()

            # Remove old calls
            self.calls = [
                call_time
                for call_time in self.calls
                if now - call_time < self.time_window
            ]

            if len(self.calls) < self.max_calls:
                return None

            # Return time until oldest call expires
            oldest_call = min(self.calls)
            return self.time_window - (now - oldest_call)

    def get_remaining_calls(self) -> int:
        """Get number of remaining calls in current window."""
        now = time.time()
        recent_calls = [
            call_time for call_time in self.calls if now - call_time < self.time_window
        ]
        return max(0, self.max_calls - len(recent_calls))

import pytest
import asyncio
from unittest.mock import Mock, patch
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from gemini_mcp_server.rate_limiter import RateLimiter


class TestRateLimiter:
    """Test cases for the RateLimiter class."""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_allows_initial_calls(self):
        """Test that initial calls are allowed within limit."""
        limiter = RateLimiter(max_calls=3, time_window=60)
        
        # First three calls should be allowed
        assert await limiter.acquire() is True
        assert await limiter.acquire() is True
        assert await limiter.acquire() is True
        
        # Fourth call should be denied
        assert await limiter.acquire() is False
    
    @pytest.mark.asyncio
    async def test_rate_limiter_remaining_calls(self):
        """Test remaining calls counter."""
        limiter = RateLimiter(max_calls=3, time_window=60)
        
        assert limiter.get_remaining_calls() == 3
        await limiter.acquire()
        assert limiter.get_remaining_calls() == 2
        await limiter.acquire()
        assert limiter.get_remaining_calls() == 1
        await limiter.acquire()
        assert limiter.get_remaining_calls() == 0
    
    @pytest.mark.asyncio
    async def test_rate_limiter_wait_time(self):
        """Test wait time calculation."""
        limiter = RateLimiter(max_calls=1, time_window=1)
        
        # No wait time initially
        wait_time = await limiter.wait_time()
        assert wait_time is None
        
        # After one call, should have wait time
        await limiter.acquire()
        wait_time = await limiter.wait_time()
        assert wait_time is not None
        assert wait_time <= 1.0
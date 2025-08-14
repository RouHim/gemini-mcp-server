import pytest
import asyncio
import time
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
    
    @pytest.mark.asyncio
    async def test_rate_limiter_time_window_reset(self):
        """Test that calls reset after time window."""
        limiter = RateLimiter(max_calls=2, time_window=0.1)  # Very short window
        
        # Use up all calls
        assert await limiter.acquire() is True
        assert await limiter.acquire() is True
        assert await limiter.acquire() is False
        
        # Wait for window to reset
        await asyncio.sleep(0.2)
        
        # Should be able to make calls again
        assert await limiter.acquire() is True
        assert limiter.get_remaining_calls() == 1
    
    @pytest.mark.asyncio
    async def test_can_make_call(self):
        """Test can_make_call method."""
        limiter = RateLimiter(max_calls=2, time_window=60)
        
        assert limiter.can_make_call() is True
        await limiter.acquire()
        assert limiter.can_make_call() is True
        await limiter.acquire()
        assert limiter.can_make_call() is False
    
    @pytest.mark.asyncio
    async def test_record_call(self):
        """Test record_call method."""
        limiter = RateLimiter(max_calls=3, time_window=60)
        
        # Record calls without going through acquire
        limiter.record_call()
        assert limiter.get_remaining_calls() == 2
        
        limiter.record_call()
        assert limiter.get_remaining_calls() == 1
        
        limiter.record_call()
        assert limiter.get_remaining_calls() == 0
        assert limiter.can_make_call() is False
    
    @pytest.mark.asyncio
    async def test_time_until_next_call(self):
        """Test time_until_next_call method."""
        limiter = RateLimiter(max_calls=1, time_window=1)
        
        # No wait time initially
        assert limiter.time_until_next_call() == 0
        
        # After using up quota, should have wait time
        await limiter.acquire()
        wait_time = limiter.time_until_next_call()
        assert wait_time > 0
        assert wait_time <= 1.0
    
    @pytest.mark.asyncio
    async def test_reset_calls(self):
        """Test manual reset of call history."""
        limiter = RateLimiter(max_calls=2, time_window=60)
        
        # Use up calls
        await limiter.acquire()
        await limiter.acquire()
        assert limiter.can_make_call() is False
        
        # Reset should restore full quota
        limiter.reset()
        assert limiter.can_make_call() is True
        assert limiter.get_remaining_calls() == 2
    
    @pytest.mark.asyncio
    async def test_concurrent_access(self):
        """Test thread safety of rate limiter."""
        limiter = RateLimiter(max_calls=5, time_window=60)
        
        async def make_call():
            return await limiter.acquire()
        
        # Make concurrent calls
        tasks = [make_call() for _ in range(10)]
        results = await asyncio.gather(*tasks)
        
        # Only first 5 should succeed
        successful_calls = sum(results)
        assert successful_calls == 5
        assert limiter.get_remaining_calls() == 0
    
    @pytest.mark.asyncio
    async def test_zero_max_calls(self):
        """Test rate limiter with zero max calls."""
        limiter = RateLimiter(max_calls=0, time_window=60)
        
        # All calls should be denied
        assert await limiter.acquire() is False
        assert limiter.can_make_call() is False
        assert limiter.get_remaining_calls() == 0
    
    @pytest.mark.asyncio
    async def test_very_large_time_window(self):
        """Test rate limiter with very large time window."""
        limiter = RateLimiter(max_calls=1, time_window=3600)  # 1 hour
        
        await limiter.acquire()
        
        # Should have long wait time
        wait_time = limiter.time_until_next_call()
        assert wait_time > 3500  # Should be close to full hour
    
    def test_initialization_parameters(self):
        """Test rate limiter initialization with various parameters."""
        # Normal case
        limiter = RateLimiter(max_calls=10, time_window=60)
        assert limiter.max_calls == 10
        assert limiter.time_window == 60
        
        # Edge cases
        limiter_zero = RateLimiter(max_calls=0, time_window=1)
        assert limiter_zero.max_calls == 0
        
        limiter_large = RateLimiter(max_calls=1000, time_window=86400)
        assert limiter_large.max_calls == 1000
    
    @pytest.mark.asyncio
    async def test_get_statistics(self):
        """Test getting rate limiter statistics."""
        limiter = RateLimiter(max_calls=5, time_window=60)
        
        # Make some calls
        await limiter.acquire()
        await limiter.acquire()
        await limiter.acquire()
        
        stats = limiter.get_statistics()
        
        assert stats["max_calls"] == 5
        assert stats["time_window"] == 60
        assert stats["calls_made"] == 3
        assert stats["remaining_calls"] == 2
        assert "time_until_reset" in stats
        assert stats["time_until_reset"] <= 60
    
    @pytest.mark.asyncio
    async def test_acquire_with_wait(self):
        """Test acquire with wait functionality."""
        limiter = RateLimiter(max_calls=1, time_window=0.1)
        
        # First call succeeds immediately
        start_time = time.time()
        result = await limiter.acquire(wait=False)
        end_time = time.time()
        
        assert result is True
        assert (end_time - start_time) < 0.01  # Should be immediate
        
        # Second call should wait if wait=True
        start_time = time.time()
        result = await limiter.acquire(wait=True)
        end_time = time.time()
        
        assert result is True
        assert (end_time - start_time) >= 0.09  # Should have waited
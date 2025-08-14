"""Tests for the retry handler module."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os
from datetime import datetime

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from gemini_mcp_server.retry_handler import RetryHandler, retry_on_error
from gemini_mcp_server.exceptions import (
    RateLimitError,
    QuotaExceededError,
    NetworkError,
    CircuitBreakerOpenError,
    AuthenticationError,
    ValidationError
)


class TestRetryHandler:
    """Test cases for the RetryHandler class."""
    
    @pytest.fixture
    def retry_handler(self):
        """Create retry handler for testing."""
        return RetryHandler(
            max_retries=3,
            base_delay=0.1,  # Short delay for testing
            max_delay=1.0,
            exponential_base=2
        )
    
    @pytest.mark.asyncio
    async def test_successful_execution_no_retry(self, retry_handler):
        """Test successful execution without retries."""
        async def success_func():
            return "success"
        
        result = await retry_handler.execute_with_retry(success_func)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_retry_on_rate_limit_error(self, retry_handler):
        """Test retry behavior on rate limit error."""
        call_count = 0
        
        async def rate_limited_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RateLimitError("Rate limit exceeded")
            return "success after retries"
        
        result = await retry_handler.execute_with_retry(rate_limited_func)
        assert result == "success after retries"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_on_network_error(self, retry_handler):
        """Test retry behavior on network error."""
        call_count = 0
        
        async def network_error_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise NetworkError("Network connection failed")
            return "success after network retry"
        
        result = await retry_handler.execute_with_retry(network_error_func)
        assert result == "success after network retry"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_no_retry_on_authentication_error(self, retry_handler):
        """Test that authentication errors are not retried."""
        call_count = 0
        
        async def auth_error_func():
            nonlocal call_count
            call_count += 1
            raise AuthenticationError("Invalid API key")
        
        with pytest.raises(AuthenticationError):
            await retry_handler.execute_with_retry(auth_error_func)
        
        # Should only be called once (no retries)
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_no_retry_on_validation_error(self, retry_handler):
        """Test that validation errors are not retried."""
        call_count = 0
        
        async def validation_error_func():
            nonlocal call_count
            call_count += 1
            raise ValidationError("Invalid input")
        
        with pytest.raises(ValidationError):
            await retry_handler.execute_with_retry(validation_error_func)
        
        # Should only be called once (no retries)
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, retry_handler):
        """Test behavior when max retries are exceeded."""
        call_count = 0
        
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise RateLimitError("Persistent rate limit")
        
        with pytest.raises(RateLimitError):
            await retry_handler.execute_with_retry(always_fails)
        
        # Should be called max_retries + 1 times (initial + retries)
        assert call_count == retry_handler.max_retries + 1
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_delay(self, retry_handler):
        """Test exponential backoff delay calculation."""
        delays = []
        original_sleep = asyncio.sleep
        
        async def mock_sleep(delay):
            delays.append(delay)
        
        with patch('asyncio.sleep', side_effect=mock_sleep):
            call_count = 0
            
            async def failing_func():
                nonlocal call_count
                call_count += 1
                if call_count <= 3:
                    raise NetworkError("Network error")
                return "success"
            
            await retry_handler.execute_with_retry(failing_func)
        
        # Should have delays for each retry
        assert len(delays) == 3
        
        # Delays should increase exponentially
        assert delays[0] == 0.1  # base_delay
        assert delays[1] == 0.2  # base_delay * 2
        assert delays[2] == 0.4  # base_delay * 4
    
    @pytest.mark.asyncio
    async def test_max_delay_cap(self):
        """Test that delay is capped at max_delay."""
        handler = RetryHandler(
            max_retries=5,
            base_delay=1.0,
            max_delay=2.0,
            exponential_base=2
        )
        
        delays = []
        
        async def mock_sleep(delay):
            delays.append(delay)
        
        with patch('asyncio.sleep', side_effect=mock_sleep):
            call_count = 0
            
            async def failing_func():
                nonlocal call_count
                call_count += 1
                if call_count <= 5:
                    raise NetworkError("Network error")
                return "success"
            
            await handler.execute_with_retry(failing_func)
        
        # All delays should be capped at max_delay
        for delay in delays[2:]:  # After first few exponential increases
            assert delay <= 2.0
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_behavior(self, retry_handler):
        """Test circuit breaker integration."""
        call_count = 0
        
        async def circuit_breaker_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise NetworkError("Network error")
            elif call_count == 2:
                raise CircuitBreakerOpenError("Circuit breaker open")
            return "success"
        
        # Circuit breaker errors should not be retried
        with pytest.raises(CircuitBreakerOpenError):
            await retry_handler.execute_with_retry(circuit_breaker_func)
        
        # Should be called twice (once for network error, once for circuit breaker)
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_function_with_arguments(self, retry_handler):
        """Test retry handler with function arguments."""
        call_count = 0
        
        async def func_with_args(arg1, arg2, kwarg1=None):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RateLimitError("Rate limit")
            return f"{arg1}-{arg2}-{kwarg1}"
        
        result = await retry_handler.execute_with_retry(
            func_with_args, "test1", "test2", kwarg1="test3"
        )
        
        assert result == "test1-test2-test3"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_quota_exceeded_handling(self, retry_handler):
        """Test handling of quota exceeded errors."""
        call_count = 0
        
        async def quota_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise QuotaExceededError("Quota exceeded")
            return "success after quota retry"
        
        result = await retry_handler.execute_with_retry(quota_func)
        assert result == "success after quota retry"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_mixed_error_types(self, retry_handler):
        """Test handling of mixed retryable and non-retryable errors."""
        call_count = 0
        
        async def mixed_errors_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise NetworkError("Network error")
            elif call_count == 2:
                raise AuthenticationError("Auth error")  # Should not retry
            return "should not reach here"
        
        with pytest.raises(AuthenticationError):
            await retry_handler.execute_with_retry(mixed_errors_func)
        
        # Should stop retrying after auth error
        assert call_count == 2
    
    def test_get_retry_statistics(self, retry_handler):
        """Test getting retry statistics."""
        # Initially no statistics
        stats = retry_handler.get_statistics()
        assert stats["total_executions"] == 0
        assert stats["total_retries"] == 0
        assert stats["success_rate"] == 0.0
    
    @pytest.mark.asyncio
    async def test_statistics_tracking(self, retry_handler):
        """Test that statistics are properly tracked."""
        # Successful execution
        async def success_func():
            return "success"
        
        await retry_handler.execute_with_retry(success_func)
        
        # Failed execution with retries
        call_count = 0
        
        async def retry_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise NetworkError("Network error")
            return "success"
        
        await retry_handler.execute_with_retry(retry_func)
        
        stats = retry_handler.get_statistics()
        assert stats["total_executions"] == 2
        assert stats["total_retries"] == 2  # 2 retries in second execution
        assert stats["success_rate"] == 100.0  # Both eventually succeeded
    
    @pytest.mark.asyncio
    async def test_custom_retry_condition(self):
        """Test custom retry condition function."""
        def custom_should_retry(exception):
            # Only retry on specific message
            return isinstance(exception, NetworkError) and "retry_me" in str(exception)
        
        handler = RetryHandler(
            max_retries=2,
            base_delay=0.1,
            should_retry_func=custom_should_retry
        )
        
        call_count = 0
        
        async def custom_retry_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise NetworkError("retry_me please")
            elif call_count == 2:
                raise NetworkError("do not retry")
            return "success"
        
        with pytest.raises(NetworkError, match="do not retry"):
            await handler.execute_with_retry(custom_retry_func)
        
        # Should retry once, then fail on second error
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_context_manager_usage(self, retry_handler):
        """Test using retry handler as context manager."""
        call_count = 0
        
        async def context_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise NetworkError("Network error")
            return "context success"
        
        async with retry_handler:
            result = await retry_handler.execute_with_retry(context_func)
        
        assert result == "context success"
        assert call_count == 2


class TestRetryDecorator:
    """Test cases for the retry decorator."""
    
    @pytest.mark.asyncio
    async def test_retry_decorator_success(self):
        """Test retry decorator on successful function."""
        call_count = 0
        
        @retry_on_error(max_retries=2, base_delay=0.1)
        async def decorated_success():
            nonlocal call_count
            call_count += 1
            return "decorated success"
        
        result = await decorated_success()
        assert result == "decorated success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_decorator_with_retries(self):
        """Test retry decorator with retries."""
        call_count = 0
        
        @retry_on_error(max_retries=2, base_delay=0.1)
        async def decorated_retry():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RateLimitError("Rate limit")
            return "decorated retry success"
        
        result = await decorated_retry()
        assert result == "decorated retry success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_decorator_max_retries(self):
        """Test retry decorator respects max retries."""
        call_count = 0
        
        @retry_on_error(max_retries=2, base_delay=0.1)
        async def decorated_fail():
            nonlocal call_count
            call_count += 1
            raise NetworkError("Persistent error")
        
        with pytest.raises(NetworkError):
            await decorated_fail()
        
        # Should be called 3 times (initial + 2 retries)
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_decorator_with_arguments(self):
        """Test retry decorator preserves function arguments."""
        call_count = 0
        
        @retry_on_error(max_retries=1, base_delay=0.1)
        async def decorated_with_args(arg1, arg2, kwarg1=None):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise NetworkError("Network error")
            return f"{arg1}-{arg2}-{kwarg1}"
        
        result = await decorated_with_args("a", "b", kwarg1="c")
        assert result == "a-b-c"
        assert call_count == 2
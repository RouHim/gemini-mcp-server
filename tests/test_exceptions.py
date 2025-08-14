"""Tests for exceptions module."""

import pytest
from src.gemini_mcp_server.exceptions import (
    GeminiMCPError,
    RateLimitError,
    QuotaExceededError,
    ContentPolicyError,
    AuthenticationError,
    NetworkError,
    ValidationError,
    ModelError,
    CircuitBreakerOpenError
)


def test_base_exception():
    """Test base exception class."""
    error = GeminiMCPError("test message", "TEST_CODE")
    assert str(error) == "test message"
    assert error.message == "test message"
    assert error.error_code == "TEST_CODE"


def test_rate_limit_error():
    """Test rate limit error."""
    error = RateLimitError("rate limited", retry_after=30.0)
    assert error.error_code == "RATE_LIMIT_EXCEEDED"
    assert error.retry_after == 30.0


def test_quota_exceeded_error():
    """Test quota exceeded error."""
    error = QuotaExceededError()
    assert error.error_code == "QUOTA_EXCEEDED"
    assert "quota exceeded" in str(error).lower()


def test_content_policy_error():
    """Test content policy error."""
    error = ContentPolicyError("content violation", "HARASSMENT")
    assert error.error_code == "CONTENT_POLICY_VIOLATION"
    assert error.policy_type == "HARASSMENT"


def test_authentication_error():
    """Test authentication error."""
    error = AuthenticationError()
    assert error.error_code == "AUTHENTICATION_FAILED"
    assert "authentication failed" in str(error).lower()


def test_network_error():
    """Test network error."""
    error = NetworkError("connection timeout")
    assert error.error_code == "NETWORK_ERROR"
    assert "connection timeout" in str(error)


def test_validation_error():
    """Test validation error."""
    error = ValidationError("invalid input")
    assert error.error_code == "VALIDATION_ERROR"
    assert "invalid input" in str(error)


def test_model_error():
    """Test model error."""
    error = ModelError("model failure")
    assert error.error_code == "MODEL_ERROR"
    assert "model failure" in str(error)


def test_circuit_breaker_open_error():
    """Test circuit breaker open error."""
    error = CircuitBreakerOpenError()
    assert error.error_code == "CIRCUIT_BREAKER_OPEN"
    assert "circuit breaker" in str(error).lower()
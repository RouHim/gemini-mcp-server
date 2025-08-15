"""Test fixtures and configurations."""

import asyncio
import os
import tempfile
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

try:
    import pytest
except ImportError:
    pytest = None

from src.gemini_mcp_server.exceptions import (
    AuthenticationError,
    CircuitBreakerOpenError,
    ContentPolicyError,
    ModelError,
    NetworkError,
    QuotaExceededError,
    RateLimitError,
    ValidationError,
)
from src.gemini_mcp_server.gemini_client import GeminiImageClient
from src.gemini_mcp_server.image_parameters import (
    AspectRatio,
    ImageGenerationParameters,
    ImageQuality,
    ImageStyle,
    SafetyLevel,
)
from src.gemini_mcp_server.rate_limiter import RateLimiter


# Test data fixtures
def sample_image_params() -> ImageGenerationParameters:
    """Create sample image generation parameters."""
    return ImageGenerationParameters(
        prompt="A beautiful mountain landscape",
        style=ImageStyle.PHOTOGRAPHIC,
        aspect_ratio=AspectRatio.LANDSCAPE_16_9,
        quality=ImageQuality.STANDARD,
        safety_level=SafetyLevel.MODERATE,
        temperature=0.7,
    )


def sample_generation_record() -> dict[str, Any]:
    """Create sample generation record."""
    return {
        "id": "test-123",
        "timestamp": datetime.now(),
        "prompt": "Test prompt",
        "style": "photographic",
        "aspect_ratio": "16:9",
        "quality": "standard",
        "safety_level": "moderate",
        "temperature": 0.7,
        "status": "completed",
        "success": True,
        "file_path": "/tmp/test.png",
        "error_message": None,
        "retry_count": 0,
        "processing_time": 2.5,
    }


def mock_generated_image_data() -> bytes:
    """Create mock image data."""
    # Simple PNG header for testing
    return b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"


# Mock fixtures
def mock_genai():
    """Mock Google Generative AI."""
    with patch("src.gemini_mcp_server.gemini_client.genai") as mock:
        # Mock configure
        mock.configure = MagicMock()

        # Mock model
        mock_model = MagicMock()
        mock.GenerativeModel.return_value = mock_model

        # Mock response
        mock_response = MagicMock()
        mock_response.parts = [MagicMock()]
        mock_response.parts[0].data = b"fake_image_data"
        mock_model.generate_content = AsyncMock(return_value=mock_response)

        return mock


def mock_google_api_error():
    """Mock Google API errors."""
    with patch("src.gemini_mcp_server.retry_handler.GoogleAPIError") as mock_error:
        return mock_error


def mock_aiohttp_session():
    """Mock aiohttp session."""
    with patch("aiohttp.ClientSession") as mock_session:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read.return_value = b"fake_image_data"
        mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
        return mock_session


# Database fixtures
def temp_db():
    """Create temporary database for testing."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    return tmp.name


def temp_images_dir():
    """Create temporary directory for test images."""
    return tempfile.mkdtemp()


# Component fixtures
def rate_limiter():
    """Create rate limiter for testing."""
    return RateLimiter(max_calls=10, time_window=60)


async def gemini_client():
    """Create Gemini client for testing."""
    with mock_genai():
        client = GeminiImageClient("fake-api-key")
        await client.initialize()
        return client


# Exception fixtures
def sample_exceptions():
    """Create sample exceptions for testing."""
    return {
        "rate_limit": RateLimitError("Rate limit exceeded"),
        "quota_exceeded": QuotaExceededError("Quota exceeded"),
        "content_policy": ContentPolicyError("Content policy violation"),
        "authentication": AuthenticationError("Invalid API key"),
        "network": NetworkError("Network connection failed"),
        "validation": ValidationError("Invalid input"),
        "model": ModelError("Model error occurred"),
        "circuit_breaker": CircuitBreakerOpenError("Circuit breaker open"),
    }


# Environment fixtures
def mock_env_vars():
    """Mock environment variables."""
    env_vars = {
        "GEMINI_API_KEY": "test-api-key",
        "GEMINI_MODEL": "gemini-pro-vision",
        "MAX_QUEUE_SIZE": "100",
        "MAX_RETRIES": "3",
        "RATE_LIMIT_CALLS": "15",
        "RATE_LIMIT_WINDOW": "60",
    }

    with patch.dict(os.environ, env_vars):
        return env_vars


# File I/O mocks
def mock_file_operations():
    """Mock file operations."""
    with (
        patch("builtins.open", create=True) as mock_open,
        patch("os.makedirs") as mock_makedirs,
        patch("os.path.exists") as mock_exists,
        patch("os.unlink") as mock_unlink,
    ):
        mock_exists.return_value = True
        return {
            "open": mock_open,
            "makedirs": mock_makedirs,
            "exists": mock_exists,
            "unlink": mock_unlink,
        }


# If pytest is available, create proper fixtures
if pytest:
    # Convert functions to fixtures
    sample_image_params = pytest.fixture(sample_image_params)
    sample_generation_record = pytest.fixture(sample_generation_record)
    mock_generated_image_data = pytest.fixture(mock_generated_image_data)
    mock_genai = pytest.fixture(mock_genai)
    mock_google_api_error = pytest.fixture(mock_google_api_error)
    mock_aiohttp_session = pytest.fixture(mock_aiohttp_session)
    temp_db = pytest.fixture(temp_db)
    temp_images_dir = pytest.fixture(temp_images_dir)
    rate_limiter = pytest.fixture(rate_limiter)
    gemini_client = pytest.fixture(gemini_client)
    sample_exceptions = pytest.fixture(sample_exceptions)
    mock_env_vars = pytest.fixture(mock_env_vars)
    mock_file_operations = pytest.fixture(mock_file_operations)

    @pytest.fixture(scope="session")
    def event_loop():
        """Create event loop for async tests."""
        loop = asyncio.new_event_loop()
        yield loop
        loop.close()

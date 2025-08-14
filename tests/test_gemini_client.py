import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gemini_mcp_server.gemini_client import GeminiImageClient
from gemini_mcp_server.exceptions import ValidationError
from gemini_mcp_server.image_parameters import ImageGenerationParameters


class TestGeminiImageClient:
    """Test cases for the GeminiImageClient class."""

    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test that client initializes without API calls."""
        client = GeminiImageClient()
        assert client.model is None
        assert not client.is_initialized

    @pytest.mark.asyncio
    async def test_initialize_with_api_key(self):
        """Test client initialization with API key."""
        with patch("gemini_mcp_server.gemini_client.genai") as mock_genai:
            mock_model = MagicMock()
            mock_genai.GenerativeModel.return_value = mock_model

            client = GeminiImageClient()
            await client.initialize("fake-api-key")

            assert client.is_initialized
            assert client.model is not None
            mock_genai.configure.assert_called_once_with(api_key="fake-api-key")

    @pytest.mark.asyncio
    async def test_generate_image_placeholder_fallback(self):
        """Test placeholder image generation fallback."""
        with patch("gemini_mcp_server.gemini_client.genai") as mock_genai:
            mock_model = MagicMock()
            mock_genai.GenerativeModel.return_value = mock_model

            client = GeminiImageClient()
            await client.initialize("fake-api-key")

            # Mock the model to raise an exception, forcing placeholder
            mock_model.generate_content = AsyncMock(side_effect=Exception("API Error"))

            params = ImageGenerationParameters(prompt="test prompt")
            result = await client.generate_image("test prompt", params)

            assert result["prompt"] == "test prompt"
            assert result["model"] == "placeholder-error"
            assert "data" in result
            assert result["mime_type"] == "image/png"
            assert "error" in result

    @pytest.mark.asyncio
    async def test_empty_prompt_validation(self):
        """Test that empty prompts are rejected."""
        with patch("gemini_mcp_server.gemini_client.genai") as mock_genai:
            mock_model = MagicMock()
            mock_genai.GenerativeModel.return_value = mock_model

            client = GeminiImageClient()
            await client.initialize("fake-api-key")

            params = ImageGenerationParameters(prompt="")

            with pytest.raises(ValidationError, match="Prompt cannot be empty"):
                await client.generate_image("", params)

    @pytest.mark.asyncio
    async def test_uninitialized_model_error(self):
        """Test that uninitialized model raises error."""
        client = GeminiImageClient()
        params = ImageGenerationParameters(prompt="test prompt")

        with pytest.raises(ValidationError, match="Gemini client not initialized"):
            await client.generate_image("test prompt", params)

    @pytest.mark.asyncio
    async def test_successful_image_generation(self):
        """Test successful image generation."""
        with patch("gemini_mcp_server.gemini_client.genai") as mock_genai:
            # Mock response
            mock_part = MagicMock()
            mock_part.data = b"fake_image_data"
            mock_response = MagicMock()
            mock_response.parts = [mock_part]

            mock_model = MagicMock()
            mock_model.generate_content = AsyncMock(return_value=mock_response)
            mock_genai.GenerativeModel.return_value = mock_model

            client = GeminiImageClient()
            await client.initialize("fake-api-key")

            params = ImageGenerationParameters(prompt="test prompt")
            result = await client.generate_image("test prompt", params)

            assert result["prompt"] == "test prompt"
            assert result["model"] == "gemini-pro-vision"
            assert result["data"] == b"fake_image_data"
            assert result["mime_type"] == "image/png"
            assert "error" not in result

    @pytest.mark.asyncio
    async def test_download_from_url(self):
        """Test downloading image from URL."""
        with patch("aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.read.return_value = b"downloaded_image_data"

            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = (
                mock_response
            )

            client = GeminiImageClient()
            result = await client._download_from_url("https://example.com/image.png")

            assert result == b"downloaded_image_data"

    @pytest.mark.asyncio
    async def test_download_from_url_failure(self):
        """Test download failure handling."""
        with patch("aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 404

            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = (
                mock_response
            )

            client = GeminiImageClient()
            result = await client._download_from_url("https://example.com/image.png")

            assert result is None

    @pytest.mark.asyncio
    async def test_create_placeholder_image(self):
        """Test placeholder image creation."""
        client = GeminiImageClient()
        image_data = client._create_placeholder_image("Test message", "1:1")

        assert isinstance(image_data, bytes)
        assert len(image_data) > 0
        # Check PNG header
        assert image_data.startswith(b"\x89PNG")

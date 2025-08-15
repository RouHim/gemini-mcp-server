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
        client = GeminiImageClient("test-api-key")
        assert client.model is None

    @pytest.mark.asyncio
    async def test_initialize_with_api_key(self):
        """Test client initialization with API key."""
        with patch("gemini_mcp_server.gemini_client.genai") as mock_genai:
            mock_model = MagicMock()
            mock_genai.GenerativeModel.return_value = mock_model

            client = GeminiImageClient("fake-api-key")
            await client.initialize()

            assert client.model is not None
            mock_genai.configure.assert_called_once_with(api_key="fake-api-key")

    @pytest.mark.asyncio
    async def test_generate_image_placeholder_fallback(self):
        """Test placeholder image generation fallback."""
        with patch("gemini_mcp_server.gemini_client.genai") as mock_genai:
            mock_model = MagicMock()
            mock_genai.GenerativeModel.return_value = mock_model

            client = GeminiImageClient("fake-api-key")
            await client.initialize()

            # Mock the model to raise an exception, forcing placeholder
            mock_model.generate_content = AsyncMock(side_effect=Exception("API Error"))

            params = ImageGenerationParameters(prompt="test prompt")
            result = await client.generate_image("test prompt")

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

            client = GeminiImageClient("fake-api-key")
            await client.initialize()

            with pytest.raises(ValidationError, match="Prompt cannot be empty"):
                await client.generate_image("")

    @pytest.mark.asyncio
    async def test_uninitialized_model_error(self):
        """Test that uninitialized model raises error."""
        client = GeminiImageClient("fake-api-key")

        with pytest.raises(ValidationError, match="Gemini client not initialized"):
            await client.generate_image("test prompt")

    @pytest.mark.asyncio
    async def test_successful_image_generation(self):
        """Test successful image generation."""
        with patch("gemini_mcp_server.gemini_client.genai") as mock_genai:
            # Mock response with parts containing image data
            mock_inline_data = MagicMock()
            mock_inline_data.data = b"fake_image_data"
            mock_inline_data.mime_type = "image/png"
            
            mock_part = MagicMock()
            mock_part.inline_data = mock_inline_data
            
            mock_response = MagicMock()
            mock_response.parts = [mock_part]

            mock_model = MagicMock()
            mock_model.generate_content = MagicMock(return_value=mock_response)
            mock_genai.GenerativeModel.return_value = mock_model

            client = GeminiImageClient("fake-api-key")
            await client.initialize()

            params = ImageGenerationParameters(prompt="test prompt")
            result = await client.generate_image("test prompt")

            assert result["prompt"] == "test prompt"
            assert result["model"] == "gemini-2.0-flash-exp"
            assert "data" in result
            assert result["mime_type"] == "image/png"
            assert "error" not in result



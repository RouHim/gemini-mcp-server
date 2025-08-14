import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from gemini_mcp_server.gemini_client import GeminiImageClient


class TestGeminiImageClient:
    """Test cases for the GeminiImageClient class."""
    
    @pytest.mark.asyncio
    async def test_client_initialization(self):
        """Test that client initializes without API calls."""
        client = GeminiImageClient("fake-api-key")
        assert client.api_key == "fake-api-key"
        assert client.model is None
    
    @pytest.mark.asyncio
    async def test_generate_image_placeholder_fallback(self):
        """Test placeholder image generation fallback."""
        client = GeminiImageClient("fake-api-key")
        
        # Mock the model to avoid API calls
        client.model = Mock()
        
        # Mock the model to raise an exception, forcing placeholder
        client.model.generate_content.side_effect = Exception("API Error")
        
        result = await client.generate_image("test prompt")
        
        assert result["prompt"] == "test prompt"
        assert result["model"] == "placeholder-error"
        assert "data" in result
        assert result["mime_type"] == "image/png"
        assert "error" in result
    
    @pytest.mark.asyncio
    async def test_empty_prompt_validation(self):
        """Test that empty prompts are rejected."""
        client = GeminiImageClient("fake-api-key")
        client.model = Mock()
        
        with pytest.raises(ValueError, match="Prompt cannot be empty"):
            await client.generate_image("")
        
        with pytest.raises(ValueError, match="Prompt cannot be empty"):
            await client.generate_image("   ")
    
    @pytest.mark.asyncio
    async def test_uninitialized_model_error(self):
        """Test that uninitialized model raises error."""
        client = GeminiImageClient("fake-api-key")
        
        with pytest.raises(ValueError, match="Gemini client not initialized"):
            await client.generate_image("test prompt")
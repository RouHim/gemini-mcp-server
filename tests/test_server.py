import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import sys
import os
import json

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gemini_mcp_server.server import server, handle_list_tools, handle_call_tool
from gemini_mcp_server.exceptions import ValidationError


class TestMCPServer:
    """Test cases for the MCP server functions."""

    @pytest.mark.asyncio
    async def test_list_tools(self):
        """Test that list_tools returns all expected tools."""
        tools = await handle_list_tools()

        # Should have 7 tools now
        assert len(tools) == 7

        tool_names = [tool.name for tool in tools]
        expected_tools = [
            "generate_image",
            "get_queue_status",
            "search_generation_history",
            "get_generation_statistics",
            "export_generation_history",
            "cleanup_old_generations",
            "get_generation_details",
        ]

        for expected_tool in expected_tools:
            assert expected_tool in tool_names

        # Check the main generate_image tool
        generate_tool = next(tool for tool in tools if tool.name == "generate_image")
        assert "generate an image" in generate_tool.description.lower()
        assert generate_tool.inputSchema is not None

    @pytest.mark.asyncio
    async def test_call_tool_invalid_name(self):
        """Test that calling an invalid tool raises error."""
        with pytest.raises(ValueError, match="Unknown tool"):
            await handle_call_tool("invalid_tool", {"prompt": "test"})

    @pytest.mark.asyncio
    async def test_call_tool_missing_arguments(self):
        """Test that missing arguments raises error."""
        with pytest.raises(ValueError, match="Missing arguments"):
            await handle_call_tool("generate_image", None)

    @pytest.mark.asyncio
    async def test_call_tool_invalid_arguments(self):
        """Test that invalid arguments raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid arguments"):
            await handle_call_tool("generate_image", {"wrong_field": "test"})

    @pytest.mark.asyncio
    async def test_generate_image_tool(self):
        """Test generate_image tool with valid arguments."""
        with patch("gemini_mcp_server.server.queue_manager") as mock_queue:
            mock_queue.add_generation_request = AsyncMock(return_value="request-123")

            result = await handle_call_tool(
                "generate_image",
                {
                    "prompt": "A beautiful sunset",
                    "style": "photographic",
                    "aspect_ratio": "16:9",
                },
            )

            assert result["request_id"] == "request-123"
            assert result["status"] == "queued"
            mock_queue.add_generation_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_queue_status_tool(self):
        """Test get_queue_status tool."""
        with patch("gemini_mcp_server.server.queue_manager") as mock_queue:
            mock_queue.get_status.return_value = {
                "queue_size": 5,
                "processing": 1,
                "completed_today": 10,
            }

            result = await handle_call_tool("get_queue_status", {})

            assert result["queue_size"] == 5
            assert result["processing"] == 1
            assert result["completed_today"] == 10

    def test_server_initialization(self):
        """Test that server object is properly configured."""
        assert server.name == "gemini-mcp-server"

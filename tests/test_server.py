import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gemini_mcp_server.exceptions import ValidationError
from gemini_mcp_server.server import handle_call_tool, handle_list_tools, server


class TestMCPServer:
    """Test cases for the MCP server functions."""

    @pytest.mark.asyncio
    async def test_list_tools(self):
        """Test that list_tools returns all expected tools."""
        tools = await handle_list_tools()

        # Should have 2 tools currently
        assert len(tools) == 2

        tool_names = [tool.name for tool in tools]
        expected_tools = [
            "generate_image",
            "get_queue_status",
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
        with patch("gemini_mcp_server.server.get_request_queue") as mock_get_queue:
            mock_queue = AsyncMock()
            mock_queue.enqueue = AsyncMock(return_value="request-123")
            mock_queue._worker_task = None
            mock_queue.start = AsyncMock()

            # Mock the completed request
            mock_completed_request = MagicMock()
            mock_completed_request.status.value = "completed"
            mock_completed_request.result = {
                "data": b"fake_image_data",
                "mime_type": "image/png",
            }
            mock_queue.wait_for_completion = AsyncMock(
                return_value=mock_completed_request
            )

            mock_get_queue.return_value = mock_queue

            result = await handle_call_tool(
                "generate_image",
                {
                    "prompt": "A beautiful sunset",
                    "style": "photographic",
                    "aspect_ratio": "16:9",
                },
            )

            assert len(result) == 2  # TextContent and ImageContent
            mock_queue.enqueue.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_queue_status_tool(self):
        """Test get_queue_status tool."""
        with patch("gemini_mcp_server.server.get_request_queue") as mock_get_queue:
            mock_queue = AsyncMock()
            mock_queue.get_queue_stats = AsyncMock(
                return_value={
                    "queue_size": 5,
                    "processing_count": 1,
                    "max_concurrent": 3,
                    "requests_last_minute": 8,
                    "rate_limit_per_minute": 15,
                    "wait_time_seconds": 0.0,
                }
            )
            mock_get_queue.return_value = mock_queue

            result = await handle_call_tool("get_queue_status", {})

            assert len(result) == 1
            assert "Queue size: 5" in result[0].text
            assert "Processing: 1/3" in result[0].text

    def test_server_initialization(self):
        """Test that server object is properly configured."""
        assert server.name == "gemini-mcp-server"

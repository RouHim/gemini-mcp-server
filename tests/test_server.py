import pytest
import asyncio
from unittest.mock import Mock, patch
import sys
import os
import json

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from gemini_mcp_server.server import server, handle_list_tools, handle_call_tool


class TestMCPServer:
    """Test cases for the MCP server functions."""
    
    @pytest.mark.asyncio
    async def test_list_tools(self):
        """Test that list_tools returns the expected tool."""
        tools = await handle_list_tools()
        
        assert len(tools) == 1
        assert tools[0].name == "generate_image"
        assert "generate an image" in tools[0].description.lower()
        assert tools[0].inputSchema is not None
    
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
        """Test that invalid arguments raises error."""
        with pytest.raises(ValueError, match="Invalid arguments"):
            await handle_call_tool("generate_image", {"wrong_field": "test"})
    
    def test_server_initialization(self):
        """Test that server object is properly configured."""
        assert server.name == "gemini-mcp-server"
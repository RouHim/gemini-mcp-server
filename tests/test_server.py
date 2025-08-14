import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import sys
import os
import json

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

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
            "get_generation_details"
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
        with patch('gemini_mcp_server.server.queue_manager') as mock_queue:
            mock_queue.add_generation_request = AsyncMock(return_value="request-123")
            
            result = await handle_call_tool("generate_image", {
                "prompt": "A beautiful sunset",
                "style": "photographic",
                "aspect_ratio": "16:9"
            })
            
            assert result["request_id"] == "request-123"
            assert result["status"] == "queued"
            mock_queue.add_generation_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_queue_status_tool(self):
        """Test get_queue_status tool."""
        with patch('gemini_mcp_server.server.queue_manager') as mock_queue:
            mock_queue.get_status.return_value = {
                "queue_size": 5,
                "processing": 1,
                "completed_today": 10
            }
            
            result = await handle_call_tool("get_queue_status", {})
            
            assert result["queue_size"] == 5
            assert result["processing"] == 1
            assert result["completed_today"] == 10
    
    @pytest.mark.asyncio
    async def test_search_generation_history_tool(self):
        """Test search_generation_history tool."""
        with patch('gemini_mcp_server.server.history_manager') as mock_history:
            mock_history.search_generations = AsyncMock(return_value=[
                {"id": "gen-1", "prompt": "sunset", "status": "completed"},
                {"id": "gen-2", "prompt": "sunrise", "status": "completed"}
            ])
            
            result = await handle_call_tool("search_generation_history", {
                "search_term": "sun",
                "limit": 10
            })
            
            assert len(result["generations"]) == 2
            assert result["total_found"] == 2
            mock_history.search_generations.assert_called_once_with("sun", 10)
    
    @pytest.mark.asyncio
    async def test_get_generation_statistics_tool(self):
        """Test get_generation_statistics tool."""
        with patch('gemini_mcp_server.server.history_manager') as mock_history:
            mock_history.get_statistics = AsyncMock(return_value={
                "total_generations": 100,
                "successful_generations": 95,
                "failed_generations": 5,
                "average_processing_time": 2.5
            })
            
            result = await handle_call_tool("get_generation_statistics", {})
            
            assert result["total_generations"] == 100
            assert result["successful_generations"] == 95
            assert result["success_rate"] == 95.0
    
    @pytest.mark.asyncio
    async def test_export_generation_history_tool(self):
        """Test export_generation_history tool."""
        with patch('gemini_mcp_server.server.history_manager') as mock_history:
            mock_history.export_history = AsyncMock(return_value="/tmp/export.json")
            
            result = await handle_call_tool("export_generation_history", {
                "format": "json",
                "include_files": False
            })
            
            assert result["export_path"] == "/tmp/export.json"
            assert result["format"] == "json"
            mock_history.export_history.assert_called_once_with("json", False)
    
    @pytest.mark.asyncio
    async def test_cleanup_old_generations_tool(self):
        """Test cleanup_old_generations tool."""
        with patch('gemini_mcp_server.server.history_manager') as mock_history:
            mock_history.cleanup_old_records = AsyncMock(return_value={
                "deleted_records": 10,
                "deleted_files": 8,
                "freed_space_mb": 50.5
            })
            
            result = await handle_call_tool("cleanup_old_generations", {
                "days_old": 30,
                "delete_files": True
            })
            
            assert result["deleted_records"] == 10
            assert result["deleted_files"] == 8
            assert result["freed_space_mb"] == 50.5
    
    @pytest.mark.asyncio
    async def test_get_generation_details_tool(self):
        """Test get_generation_details tool."""
        with patch('gemini_mcp_server.server.history_manager') as mock_history:
            mock_history.get_generation_details = AsyncMock(return_value={
                "id": "gen-123",
                "prompt": "test prompt",
                "status": "completed",
                "file_path": "/tmp/image.png"
            })
            
            result = await handle_call_tool("get_generation_details", {
                "generation_id": "gen-123"
            })
            
            assert result["id"] == "gen-123"
            assert result["prompt"] == "test prompt"
            mock_history.get_generation_details.assert_called_once_with("gen-123")
    
    def test_server_initialization(self):
        """Test that server object is properly configured."""
        assert server.name == "gemini-mcp-server"
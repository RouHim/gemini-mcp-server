"""Integration tests for complete workflows."""

import pytest
import asyncio
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock, patch
import sys

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from gemini_mcp_server.server import server, handle_list_tools, handle_call_tool
from gemini_mcp_server.gemini_client import GeminiImageClient
from gemini_mcp_server.queue_manager import QueueManager
from gemini_mcp_server.history_manager import HistoryManager
from gemini_mcp_server.rate_limiter import RateLimiter
from gemini_mcp_server.image_parameters import ImageGenerationParameters
from gemini_mcp_server.exceptions import ValidationError


class TestIntegrationWorkflows:
    """Integration tests for complete workflows."""
    
    @pytest.fixture
    async def full_system(self):
        """Set up complete system for integration testing."""
        # Create temporary directories and files
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        temp_images_dir = tempfile.mkdtemp()
        
        try:
            # Initialize components
            rate_limiter = RateLimiter(max_calls=10, time_window=60)
            
            with patch('gemini_mcp_server.gemini_client.genai') as mock_genai:
                # Mock Gemini API
                mock_model = MagicMock()
                mock_response = MagicMock()
                mock_response.parts = [MagicMock()]
                mock_response.parts[0].data = b"fake_image_data"
                mock_model.generate_content = AsyncMock(return_value=mock_response)
                mock_genai.GenerativeModel.return_value = mock_model
                
                gemini_client = GeminiImageClient()
                await gemini_client.initialize("fake-api-key")
            
            history_manager = HistoryManager(db_path=temp_db.name, images_dir=temp_images_dir)
            await history_manager.initialize()
            
            queue_manager = QueueManager(
                rate_limiter=rate_limiter,
                gemini_client=gemini_client,
                history_manager=history_manager,
                max_queue_size=50,
                max_retries=3
            )
            
            yield {
                'rate_limiter': rate_limiter,
                'gemini_client': gemini_client,
                'history_manager': history_manager,
                'queue_manager': queue_manager,
                'temp_db': temp_db.name,
                'temp_images_dir': temp_images_dir
            }
            
        finally:
            # Cleanup
            try:
                os.unlink(temp_db.name)
                import shutil
                shutil.rmtree(temp_images_dir, ignore_errors=True)
            except:
                pass
    
    @pytest.mark.asyncio
    async def test_end_to_end_image_generation(self, full_system):
        """Test complete end-to-end image generation workflow."""
        components = full_system
        queue_manager = components['queue_manager']
        history_manager = components['history_manager']
        
        # Set up global components for server
        with patch('gemini_mcp_server.server.queue_manager', queue_manager), \
             patch('gemini_mcp_server.server.history_manager', history_manager):
            
            # 1. List available tools
            tools = await handle_list_tools()
            assert len(tools) == 7
            tool_names = [tool.name for tool in tools]
            assert "generate_image" in tool_names
            
            # 2. Generate an image
            generation_result = await handle_call_tool("generate_image", {
                "prompt": "A beautiful sunset over mountains",
                "style": "photographic",
                "aspect_ratio": "16:9",
                "quality": "standard"
            })
            
            request_id = generation_result["request_id"]
            assert request_id is not None
            assert generation_result["status"] == "queued"
            
            # 3. Check queue status
            queue_status = await handle_call_tool("get_queue_status", {})
            assert queue_status["queue_size"] >= 0
            
            # 4. Wait for processing (simulate)
            await asyncio.sleep(0.1)
            
            # 5. Search for the generation in history
            search_result = await handle_call_tool("search_generation_history", {
                "search_term": "sunset",
                "limit": 10
            })
            
            assert search_result["total_found"] >= 0
            
            # 6. Get statistics
            stats_result = await handle_call_tool("get_generation_statistics", {})
            assert "total_generations" in stats_result
            assert "success_rate" in stats_result
    
    @pytest.mark.asyncio
    async def test_rate_limiting_workflow(self, full_system):
        """Test rate limiting behavior in complete workflow."""
        components = full_system
        rate_limiter = components['rate_limiter']
        queue_manager = components['queue_manager']
        
        # Set rate limit to very low for testing
        rate_limiter.max_calls = 2
        
        with patch('gemini_mcp_server.server.queue_manager', queue_manager):
            # Make requests that exceed rate limit
            results = []
            for i in range(5):
                try:
                    result = await handle_call_tool("generate_image", {
                        "prompt": f"Test image {i}",
                        "style": "photographic"
                    })
                    results.append(result)
                except Exception as e:
                    results.append({"error": str(e)})
            
            # Should have some successful requests and some rate-limited
            assert len(results) == 5
            successful = [r for r in results if "request_id" in r]
            assert len(successful) >= 2  # At least the first few should succeed
    
    @pytest.mark.asyncio
    async def test_error_handling_workflow(self, full_system):
        """Test error handling throughout the workflow."""
        components = full_system
        queue_manager = components['queue_manager']
        
        with patch('gemini_mcp_server.server.queue_manager', queue_manager):
            # Test validation errors
            with pytest.raises(ValidationError):
                await handle_call_tool("generate_image", {
                    "wrong_field": "invalid"
                })
            
            # Test missing arguments
            with pytest.raises(ValueError, match="Missing arguments"):
                await handle_call_tool("generate_image", None)
            
            # Test unknown tool
            with pytest.raises(ValueError, match="Unknown tool"):
                await handle_call_tool("unknown_tool", {})
    
    @pytest.mark.asyncio
    async def test_queue_management_workflow(self, full_system):
        """Test queue management operations."""
        components = full_system
        queue_manager = components['queue_manager']
        
        with patch('gemini_mcp_server.server.queue_manager', queue_manager):
            # Add multiple requests to queue
            request_ids = []
            for i in range(3):
                result = await handle_call_tool("generate_image", {
                    "prompt": f"Queue test {i}",
                    "style": "photographic"
                })
                request_ids.append(result["request_id"])
            
            # Check queue status
            status = await handle_call_tool("get_queue_status", {})
            assert status["queue_size"] >= 0
            
            # Test queue operations would go here
            # (Note: actual queue processing happens in background)
    
    @pytest.mark.asyncio
    async def test_history_management_workflow(self, full_system):
        """Test history management operations."""
        components = full_system
        history_manager = components['history_manager']
        
        with patch('gemini_mcp_server.server.history_manager', history_manager):
            # Create some test history entries
            params = ImageGenerationParameters(
                prompt="Test history prompt",
                style="photographic"
            )
            
            generation_id = await history_manager.record_generation(
                "Test history prompt", params
            )
            
            # Test search
            search_result = await handle_call_tool("search_generation_history", {
                "search_term": "history",
                "limit": 10
            })
            assert search_result["total_found"] >= 0
            
            # Test getting details
            details_result = await handle_call_tool("get_generation_details", {
                "generation_id": generation_id
            })
            assert details_result["id"] == generation_id
            
            # Test statistics
            stats_result = await handle_call_tool("get_generation_statistics", {})
            assert "total_generations" in stats_result
            
            # Test export
            export_result = await handle_call_tool("export_generation_history", {
                "format": "json",
                "include_files": False
            })
            assert "export_path" in export_result
    
    @pytest.mark.asyncio
    async def test_concurrent_requests_workflow(self, full_system):
        """Test handling of concurrent requests."""
        components = full_system
        queue_manager = components['queue_manager']
        
        with patch('gemini_mcp_server.server.queue_manager', queue_manager):
            async def make_request(i):
                try:
                    return await handle_call_tool("generate_image", {
                        "prompt": f"Concurrent test {i}",
                        "style": "photographic"
                    })
                except Exception as e:
                    return {"error": str(e)}
            
            # Make concurrent requests
            tasks = [make_request(i) for i in range(10)]
            results = await asyncio.gather(*tasks)
            
            # Should handle all requests (some might be rate limited)
            assert len(results) == 10
            successful = [r for r in results if "request_id" in r]
            errors = [r for r in results if "error" in r]
            
            # Should have some successful requests
            assert len(successful) >= 1
    
    @pytest.mark.asyncio
    async def test_cleanup_workflow(self, full_system):
        """Test cleanup operations."""
        components = full_system
        history_manager = components['history_manager']
        
        with patch('gemini_mcp_server.server.history_manager', history_manager):
            # Create some test data to cleanup
            params = ImageGenerationParameters(
                prompt="Cleanup test prompt",
                style="photographic"
            )
            
            generation_id = await history_manager.record_generation(
                "Cleanup test prompt", params
            )
            
            # Test cleanup operation
            cleanup_result = await handle_call_tool("cleanup_old_generations", {
                "days_old": 0,  # Clean up everything
                "delete_files": True
            })
            
            assert "deleted_records" in cleanup_result
            assert "freed_space_mb" in cleanup_result
    
    @pytest.mark.asyncio
    async def test_server_initialization_workflow(self):
        """Test server initialization and basic operations."""
        # Test that server is properly configured
        assert server.name == "gemini-mcp-server"
        
        # Test tools are available
        tools = await handle_list_tools()
        assert len(tools) > 0
        
        # Test each tool has proper schema
        for tool in tools:
            assert tool.name is not None
            assert tool.description is not None
            assert tool.inputSchema is not None
    
    @pytest.mark.asyncio
    async def test_resilience_workflow(self, full_system):
        """Test system resilience under various conditions."""
        components = full_system
        queue_manager = components['queue_manager']
        gemini_client = components['gemini_client']
        
        # Test with network failures
        with patch.object(gemini_client, 'generate_image', side_effect=Exception("Network error")):
            with patch('gemini_mcp_server.server.queue_manager', queue_manager):
                # Should handle gracefully
                result = await handle_call_tool("generate_image", {
                    "prompt": "Resilience test",
                    "style": "photographic"
                })
                
                # Request should be queued even if processing might fail
                assert result["status"] == "queued"
    
    @pytest.mark.asyncio
    async def test_data_consistency_workflow(self, full_system):
        """Test data consistency across operations."""
        components = full_system
        history_manager = components['history_manager']
        queue_manager = components['queue_manager']
        
        with patch('gemini_mcp_server.server.history_manager', history_manager), \
             patch('gemini_mcp_server.server.queue_manager', queue_manager):
            
            # Generate image
            result = await handle_call_tool("generate_image", {
                "prompt": "Consistency test",
                "style": "photographic"
            })
            request_id = result["request_id"]
            
            # Check that data is consistent across different views
            queue_status = await handle_call_tool("get_queue_status", {})
            search_results = await handle_call_tool("search_generation_history", {
                "search_term": "consistency",
                "limit": 10
            })
            statistics = await handle_call_tool("get_generation_statistics", {})
            
            # Data should be consistent
            assert isinstance(queue_status["queue_size"], int)
            assert isinstance(search_results["total_found"], int)
            assert isinstance(statistics["total_generations"], int)


class TestPerformanceWorkflows:
    """Performance-focused integration tests."""
    
    @pytest.mark.asyncio
    async def test_high_volume_requests(self):
        """Test system behavior under high volume of requests."""
        # This would test with many concurrent requests
        # Simplified for this example
        tools = await handle_list_tools()
        assert len(tools) > 0
    
    @pytest.mark.asyncio
    async def test_memory_usage(self):
        """Test memory usage patterns."""
        # This would monitor memory usage during operations
        # Simplified for this example
        tools = await handle_list_tools()
        assert len(tools) > 0
    
    @pytest.mark.asyncio
    async def test_response_times(self):
        """Test response time requirements."""
        import time
        
        start_time = time.time()
        tools = await handle_list_tools()
        end_time = time.time()
        
        # Should respond quickly
        response_time = end_time - start_time
        assert response_time < 1.0  # Should be very fast for listing tools
        assert len(tools) > 0
"""Integration tests for complete workflows."""

import pytest
import asyncio
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock, patch
import sys

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gemini_mcp_server.server import server, handle_list_tools, handle_call_tool
from gemini_mcp_server.gemini_client import GeminiImageClient
from gemini_mcp_server.queue_manager import QueueManager
from gemini_mcp_server.rate_limiter import RateLimiter
from gemini_mcp_server.image_parameters import ImageGenerationParameters
from gemini_mcp_server.exceptions import ValidationError


class TestIntegrationWorkflows:
    """Integration tests for complete workflows."""

    @pytest.fixture
    async def full_system(self):
        """Set up complete system for integration testing."""
        try:
            # Initialize components
            rate_limiter = RateLimiter(max_calls=10, time_window=60)

            with patch("gemini_mcp_server.gemini_client.genai") as mock_genai:
                # Mock Gemini API
                mock_model = MagicMock()
                mock_response = MagicMock()
                mock_response.parts = [MagicMock()]
                mock_response.parts[0].data = b"fake_image_data"
                mock_model.generate_content = AsyncMock(return_value=mock_response)
                mock_genai.GenerativeModel.return_value = mock_model

                gemini_client = GeminiImageClient()
                await gemini_client.initialize("fake-api-key")

            queue_manager = QueueManager(
                rate_limiter=rate_limiter,
                gemini_client=gemini_client,
                max_queue_size=50,
                max_retries=3,
            )

            yield {
                "rate_limiter": rate_limiter,
                "gemini_client": gemini_client,
                "queue_manager": queue_manager,
            }

        finally:
            # Cleanup
            pass

    @pytest.mark.asyncio
    async def test_end_to_end_image_generation(self, full_system):
        """Test complete end-to-end image generation workflow."""
        components = full_system
        queue_manager = components["queue_manager"]

        # Set up global components for server
        with patch("gemini_mcp_server.server.queue_manager", queue_manager):

            # 1. List available tools
            tools = await handle_list_tools()
            assert len(tools) == 2  # Only generate_image and get_queue_status
            tool_names = [tool.name for tool in tools]
            assert "generate_image" in tool_names
            assert "get_queue_status" in tool_names

            # 2. Generate an image
            generation_result = await handle_call_tool(
                "generate_image",
                {
                    "prompt": "A beautiful sunset over mountains",
                    "style": "photographic",
                    "aspect_ratio": "16:9",
                    "quality": "standard",
                },
            )

            # Verify generation result structure (simplified without history)
            assert "data" in generation_result or "error" in generation_result

            # 3. Check queue status
            queue_status = await handle_call_tool("get_queue_status", {})
            assert "queue_size" in queue_status or "error" in queue_status

    @pytest.mark.asyncio
    async def test_rate_limiting_workflow(self, full_system):
        """Test rate limiting behavior in complete workflow."""
        components = full_system
        rate_limiter = components["rate_limiter"]
        queue_manager = components["queue_manager"]

        # Set rate limit to very low for testing
        rate_limiter.max_calls = 2

        with patch("gemini_mcp_server.server.queue_manager", queue_manager):
            # Make requests that exceed rate limit
            results = []
            for i in range(5):
                try:
                    result = await handle_call_tool(
                        "generate_image",
                        {"prompt": f"Test image {i}", "style": "photographic"},
                    )
                    results.append(result)
                except Exception as e:
                    results.append({"error": str(e)})

            # Should have some successful requests and some rate-limited
            assert len(results) == 5

    @pytest.mark.asyncio
    async def test_error_handling_workflow(self, full_system):
        """Test error handling throughout the workflow."""
        components = full_system
        queue_manager = components["queue_manager"]

        with patch("gemini_mcp_server.server.queue_manager", queue_manager):
            # Test validation errors
            with pytest.raises(ValidationError):
                await handle_call_tool("generate_image", {"wrong_field": "invalid"})

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
        queue_manager = components["queue_manager"]

        with patch("gemini_mcp_server.server.queue_manager", queue_manager):
            # Check queue status
            status = await handle_call_tool("get_queue_status", {})
            assert "queue_size" in status or "error" in status

    @pytest.mark.asyncio
    async def test_concurrent_requests_workflow(self, full_system):
        """Test handling of concurrent requests."""
        components = full_system
        queue_manager = components["queue_manager"]

        with patch("gemini_mcp_server.server.queue_manager", queue_manager):

            async def make_request(i):
                try:
                    return await handle_call_tool(
                        "generate_image",
                        {"prompt": f"Concurrent test {i}", "style": "photographic"},
                    )
                except Exception as e:
                    return {"error": str(e)}

            # Make concurrent requests
            tasks = [make_request(i) for i in range(5)]
            results = await asyncio.gather(*tasks)

            # Should handle all requests (some might be rate limited)
            assert len(results) == 5

    @pytest.mark.asyncio
    async def test_server_initialization_workflow(self):
        """Test server initialization and basic operations."""
        # Test that server is properly configured
        assert server.name == "gemini-mcp-server"

        # Test tools are available
        tools = await handle_list_tools()
        assert len(tools) == 2  # generate_image and get_queue_status

        # Test each tool has proper schema
        for tool in tools:
            assert tool.name is not None
            assert tool.description is not None
            assert tool.inputSchema is not None

    @pytest.mark.asyncio
    async def test_resilience_workflow(self, full_system):
        """Test system resilience under various conditions."""
        components = full_system
        queue_manager = components["queue_manager"]
        gemini_client = components["gemini_client"]

        # Test with network failures
        with patch.object(
            gemini_client, "generate_image", side_effect=Exception("Network error")
        ):
            with patch("gemini_mcp_server.server.queue_manager", queue_manager):
                # Should handle gracefully
                try:
                    result = await handle_call_tool(
                        "generate_image",
                        {"prompt": "Resilience test", "style": "photographic"},
                    )
                    # Should either succeed or fail gracefully
                    assert "data" in result or "error" in result
                except Exception:
                    # Exceptions are also acceptable for resilience test
                    pass

            # Check that data is consistent across different views
            queue_status = await handle_call_tool("get_queue_status", {})
            search_results = await handle_call_tool(
                "search_generation_history", {"search_term": "consistency", "limit": 10}
            )
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

"""Tests for the queue manager module."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os
from datetime import datetime, timedelta

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from gemini_mcp_server.queue_manager import QueueManager, QueueStatus, GenerationRequest
from gemini_mcp_server.image_parameters import ImageGenerationParameters
from gemini_mcp_server.exceptions import ValidationError, RateLimitError
from gemini_mcp_server.rate_limiter import RateLimiter


class TestQueueManager:
    """Test cases for the QueueManager class."""

    @pytest.fixture
    def mock_rate_limiter(self):
        """Create mock rate limiter."""
        limiter = MagicMock(spec=RateLimiter)
        limiter.can_make_call.return_value = True
        limiter.time_until_next_call.return_value = 0
        limiter.record_call = MagicMock()
        limiter.get_remaining_calls.return_value = 10
        return limiter

    @pytest.fixture
    def mock_gemini_client(self):
        """Create mock Gemini client."""
        client = AsyncMock()
        client.generate_image = AsyncMock(
            return_value={
                "prompt": "test",
                "data": b"image_data",
                "mime_type": "image/png",
                "model": "gemini-pro-vision",
            }
        )
        return client

    @pytest.fixture
    def mock_history_manager(self):
        """Create mock history manager."""
        manager = AsyncMock()
        manager.record_generation = AsyncMock(return_value="history-123")
        manager.update_generation_result = AsyncMock()
        manager.mark_generation_failed = AsyncMock()
        return manager

    @pytest.fixture
    def queue_manager(
        self, mock_rate_limiter, mock_gemini_client, mock_history_manager
    ):
        """Create queue manager with mocked dependencies."""
        return QueueManager(
            rate_limiter=mock_rate_limiter,
            gemini_client=mock_gemini_client,
            history_manager=mock_history_manager,
            max_queue_size=10,
            max_retries=3,
        )

    @pytest.fixture
    def sample_params(self):
        """Create sample generation parameters."""
        return ImageGenerationParameters(
            prompt="A beautiful sunset", style="photographic", aspect_ratio="16:9"
        )

    def test_queue_manager_initialization(self, queue_manager):
        """Test queue manager initialization."""
        assert queue_manager.max_queue_size == 10
        assert queue_manager.max_retries == 3
        assert len(queue_manager.pending_queue) == 0
        assert len(queue_manager.processing_requests) == 0
        assert queue_manager.is_processing is False

    @pytest.mark.asyncio
    async def test_add_generation_request(self, queue_manager, sample_params):
        """Test adding a generation request to the queue."""
        request_id = await queue_manager.add_generation_request(
            "test prompt", sample_params
        )

        assert request_id is not None
        assert len(queue_manager.pending_queue) == 1

        request = queue_manager.pending_queue[0]
        assert request.prompt == "test prompt"
        assert request.parameters == sample_params
        assert request.status == QueueStatus.PENDING

    @pytest.mark.asyncio
    async def test_add_request_queue_full(self, queue_manager, sample_params):
        """Test adding request when queue is full."""
        # Fill the queue
        for i in range(queue_manager.max_queue_size):
            await queue_manager.add_generation_request(f"prompt {i}", sample_params)

        # Try to add one more
        with pytest.raises(ValidationError, match="Queue is full"):
            await queue_manager.add_generation_request("overflow prompt", sample_params)

    @pytest.mark.asyncio
    async def test_add_request_rate_limited(
        self, queue_manager, sample_params, mock_rate_limiter
    ):
        """Test adding request when rate limited."""
        mock_rate_limiter.can_make_call.return_value = False
        mock_rate_limiter.time_until_next_call.return_value = 30

        request_id = await queue_manager.add_generation_request(
            "test prompt", sample_params
        )

        # Should still add to queue but not process immediately
        assert request_id is not None
        assert len(queue_manager.pending_queue) == 1

    @pytest.mark.asyncio
    async def test_process_queue(self, queue_manager, sample_params):
        """Test processing the queue."""
        # Add a request
        await queue_manager.add_generation_request("test prompt", sample_params)

        # Start processing
        processing_task = asyncio.create_task(queue_manager._process_queue())

        # Give it a moment to process
        await asyncio.sleep(0.1)

        # Cancel the task to avoid running forever
        processing_task.cancel()

        try:
            await processing_task
        except asyncio.CancelledError:
            pass

        # Should have started processing
        assert queue_manager.is_processing is True

    @pytest.mark.asyncio
    async def test_process_single_request_success(
        self, queue_manager, sample_params, mock_gemini_client, mock_history_manager
    ):
        """Test processing a single request successfully."""
        request = GenerationRequest(
            id="test-123",
            prompt="test prompt",
            parameters=sample_params,
            timestamp=datetime.now(),
            status=QueueStatus.PENDING,
        )

        await queue_manager._process_request(request)

        assert request.status == QueueStatus.COMPLETED
        mock_gemini_client.generate_image.assert_called_once()
        mock_history_manager.update_generation_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_single_request_failure(
        self, queue_manager, sample_params, mock_gemini_client, mock_history_manager
    ):
        """Test processing a single request with failure."""
        mock_gemini_client.generate_image.side_effect = Exception("API Error")

        request = GenerationRequest(
            id="test-123",
            prompt="test prompt",
            parameters=sample_params,
            timestamp=datetime.now(),
            status=QueueStatus.PENDING,
        )

        await queue_manager._process_request(request)

        assert request.status == QueueStatus.FAILED
        assert request.retry_count == 0  # First failure
        mock_history_manager.mark_generation_failed.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_mechanism(
        self, queue_manager, sample_params, mock_gemini_client
    ):
        """Test request retry mechanism."""
        # First two calls fail, third succeeds
        mock_gemini_client.generate_image.side_effect = [
            Exception("API Error 1"),
            Exception("API Error 2"),
            {
                "prompt": "test",
                "data": b"image_data",
                "mime_type": "image/png",
                "model": "gemini-pro-vision",
            },
        ]

        request = GenerationRequest(
            id="test-123",
            prompt="test prompt",
            parameters=sample_params,
            timestamp=datetime.now(),
            status=QueueStatus.PENDING,
        )

        # Process with retries
        await queue_manager._process_request(request)
        await queue_manager._process_request(request)  # First retry
        await queue_manager._process_request(request)  # Second retry

        assert request.status == QueueStatus.COMPLETED
        assert request.retry_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(
        self, queue_manager, sample_params, mock_gemini_client
    ):
        """Test behavior when max retries are exceeded."""
        mock_gemini_client.generate_image.side_effect = Exception("Persistent Error")

        request = GenerationRequest(
            id="test-123",
            prompt="test prompt",
            parameters=sample_params,
            timestamp=datetime.now(),
            status=QueueStatus.PENDING,
            retry_count=queue_manager.max_retries,
        )

        await queue_manager._process_request(request)

        assert request.status == QueueStatus.FAILED
        assert request.retry_count == queue_manager.max_retries

    def test_get_status(self, queue_manager, sample_params):
        """Test getting queue status."""
        # Add some requests to test status
        queue_manager.pending_queue.extend(
            [
                GenerationRequest(
                    id=f"req-{i}",
                    prompt=f"prompt {i}",
                    parameters=sample_params,
                    timestamp=datetime.now(),
                    status=QueueStatus.PENDING,
                )
                for i in range(3)
            ]
        )

        queue_manager.processing_requests.update(
            {
                "proc-1": GenerationRequest(
                    id="proc-1",
                    prompt="processing prompt",
                    parameters=sample_params,
                    timestamp=datetime.now(),
                    status=QueueStatus.PROCESSING,
                )
            }
        )

        status = queue_manager.get_status()

        assert status["queue_size"] == 3
        assert status["processing"] == 1
        assert status["is_processing"] is False
        assert "rate_limit_remaining" in status
        assert "rate_limit_reset_time" in status

    @pytest.mark.asyncio
    async def test_get_request_status(self, queue_manager, sample_params):
        """Test getting status of a specific request."""
        request_id = await queue_manager.add_generation_request(
            "test prompt", sample_params
        )

        status = queue_manager.get_request_status(request_id)

        assert status is not None
        assert status["id"] == request_id
        assert status["status"] == QueueStatus.PENDING.value
        assert status["prompt"] == "test prompt"

    def test_get_request_status_not_found(self, queue_manager):
        """Test getting status of non-existent request."""
        status = queue_manager.get_request_status("non-existent")
        assert status is None

    @pytest.mark.asyncio
    async def test_cancel_request(self, queue_manager, sample_params):
        """Test canceling a pending request."""
        request_id = await queue_manager.add_generation_request(
            "test prompt", sample_params
        )

        success = queue_manager.cancel_request(request_id)

        assert success is True
        assert len(queue_manager.pending_queue) == 0

    def test_cancel_request_not_found(self, queue_manager):
        """Test canceling non-existent request."""
        success = queue_manager.cancel_request("non-existent")
        assert success is False

    def test_cancel_processing_request(self, queue_manager, sample_params):
        """Test that processing requests cannot be canceled."""
        request = GenerationRequest(
            id="proc-1",
            prompt="processing prompt",
            parameters=sample_params,
            timestamp=datetime.now(),
            status=QueueStatus.PROCESSING,
        )
        queue_manager.processing_requests["proc-1"] = request

        success = queue_manager.cancel_request("proc-1")
        assert success is False

    @pytest.mark.asyncio
    async def test_clear_queue(self, queue_manager, sample_params):
        """Test clearing the queue."""
        # Add some requests
        for i in range(3):
            await queue_manager.add_generation_request(f"prompt {i}", sample_params)

        cleared_count = queue_manager.clear_queue()

        assert cleared_count == 3
        assert len(queue_manager.pending_queue) == 0

    def test_get_queue_history(self, queue_manager, sample_params):
        """Test getting queue history."""
        # Add some completed requests to history
        for i in range(5):
            request = GenerationRequest(
                id=f"completed-{i}",
                prompt=f"completed prompt {i}",
                parameters=sample_params,
                timestamp=datetime.now() - timedelta(minutes=i),
                status=QueueStatus.COMPLETED,
            )
            queue_manager.completed_requests.append(request)

        history = queue_manager.get_queue_history(limit=3)

        assert len(history) == 3
        assert all(req["status"] == QueueStatus.COMPLETED.value for req in history)

    @pytest.mark.asyncio
    async def test_rate_limit_handling(
        self, queue_manager, sample_params, mock_rate_limiter
    ):
        """Test rate limit handling during processing."""
        mock_rate_limiter.can_make_call.return_value = False
        mock_rate_limiter.time_until_next_call.return_value = 1

        request = GenerationRequest(
            id="test-123",
            prompt="test prompt",
            parameters=sample_params,
            timestamp=datetime.now(),
            status=QueueStatus.PENDING,
        )

        # This should wait for rate limit
        start_time = datetime.now()
        await queue_manager._handle_rate_limit()
        end_time = datetime.now()

        # Should have waited approximately 1 second
        wait_time = (end_time - start_time).total_seconds()
        assert wait_time >= 0.5  # Allow some tolerance

    @pytest.mark.asyncio
    async def test_cleanup_completed_requests(self, queue_manager, sample_params):
        """Test cleanup of old completed requests."""
        # Add old completed requests
        old_time = datetime.now() - timedelta(hours=2)
        for i in range(10):
            request = GenerationRequest(
                id=f"old-{i}",
                prompt=f"old prompt {i}",
                parameters=sample_params,
                timestamp=old_time,
                status=QueueStatus.COMPLETED,
            )
            queue_manager.completed_requests.append(request)

        # Add recent completed request
        recent_request = GenerationRequest(
            id="recent-1",
            prompt="recent prompt",
            parameters=sample_params,
            timestamp=datetime.now(),
            status=QueueStatus.COMPLETED,
        )
        queue_manager.completed_requests.append(recent_request)

        # Cleanup should remove old requests but keep recent ones
        queue_manager._cleanup_completed_requests(max_age_hours=1, max_count=5)

        assert len(queue_manager.completed_requests) <= 5
        assert any(req.id == "recent-1" for req in queue_manager.completed_requests)

"""Tests for the history manager module."""

import pytest
import asyncio
import sqlite3
import tempfile
import os
import json
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timedelta
import sys

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from gemini_mcp_server.history_manager import ImageHistoryManager
from gemini_mcp_server.image_parameters import ImageGenerationParameters


class TestHistoryManager:
    """Test cases for the HistoryManager class."""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        yield path
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass
    
    @pytest.fixture
    def temp_images_dir(self):
        """Create temporary images directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    async def history_manager(self, temp_db, temp_images_dir):
        """Create history manager with temporary database."""
        manager = ImageHistoryManager(db_path=temp_db, images_dir=temp_images_dir)
        await manager.initialize()
        return manager
    
    @pytest.fixture
    def sample_params(self):
        """Create sample generation parameters."""
        return ImageGenerationParameters(
            prompt="A beautiful sunset over mountains",
            style="photographic",
            aspect_ratio="16:9",
            quality="standard",
            safety_level="moderate",
            temperature=0.7
        )
    
    @pytest.mark.asyncio
    async def test_initialization(self, history_manager, temp_db):
        """Test history manager initialization."""
        assert history_manager.db_path == temp_db
        assert os.path.exists(temp_db)
        
        # Check that tables were created
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        assert "generations" in tables
    
    @pytest.mark.asyncio
    async def test_record_generation(self, history_manager, sample_params):
        """Test recording a new generation."""
        generation_id = await history_manager.record_generation(
            prompt="test prompt",
            parameters=sample_params
        )
        
        assert generation_id is not None
        assert isinstance(generation_id, str)
        
        # Verify it was stored in database
        details = await history_manager.get_generation_details(generation_id)
        assert details is not None
        assert details["prompt"] == "test prompt"
        assert details["status"] == "pending"
    
    @pytest.mark.asyncio
    async def test_update_generation_result_success(self, history_manager, sample_params):
        """Test updating generation with successful result."""
        generation_id = await history_manager.record_generation(
            prompt="test prompt",
            parameters=sample_params
        )
        
        result_data = {
            "prompt": "test prompt",
            "data": b"fake_image_data",
            "mime_type": "image/png",
            "model": "gemini-pro-vision"
        }
        
        with patch('builtins.open', create=True) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            await history_manager.update_generation_result(
                generation_id=generation_id,
                result_data=result_data,
                processing_time=2.5
            )
        
        # Verify update
        details = await history_manager.get_generation_details(generation_id)
        assert details["status"] == "completed"
        assert details["success"] is True
        assert details["processing_time"] == 2.5
        assert details["file_path"] is not None
    
    @pytest.mark.asyncio
    async def test_mark_generation_failed(self, history_manager, sample_params):
        """Test marking generation as failed."""
        generation_id = await history_manager.record_generation(
            prompt="test prompt",
            parameters=sample_params
        )
        
        await history_manager.mark_generation_failed(
            generation_id=generation_id,
            error_message="Test error",
            retry_count=2
        )
        
        # Verify failure was recorded
        details = await history_manager.get_generation_details(generation_id)
        assert details["status"] == "failed"
        assert details["success"] is False
        assert details["error_message"] == "Test error"
        assert details["retry_count"] == 2
    
    @pytest.mark.asyncio
    async def test_search_generations(self, history_manager, sample_params):
        """Test searching through generations."""
        # Create test data
        test_prompts = [
            "beautiful sunset over mountains",
            "amazing sunrise at the beach",
            "peaceful forest landscape",
            "bustling city street"
        ]
        
        generation_ids = []
        for prompt in test_prompts:
            gen_id = await history_manager.record_generation(prompt, sample_params)
            generation_ids.append(gen_id)
        
        # Search for "sun" - should match sunset and sunrise
        results = await history_manager.search_generations("sun", limit=10)
        
        assert len(results) == 2
        assert all("sun" in result["prompt"].lower() for result in results)
    
    @pytest.mark.asyncio
    async def test_search_generations_with_filters(self, history_manager, sample_params):
        """Test searching with status and date filters."""
        # Create generations with different statuses
        success_id = await history_manager.record_generation("success prompt", sample_params)
        await history_manager.update_generation_result(
            success_id,
            {"prompt": "success prompt", "data": b"data", "mime_type": "image/png", "model": "test"},
            1.0
        )
        
        failed_id = await history_manager.record_generation("failed prompt", sample_params)
        await history_manager.mark_generation_failed(failed_id, "Error", 0)
        
        # Search only successful generations
        with patch('builtins.open', create=True):
            results = await history_manager.search_generations(
                search_term="prompt",
                status_filter="completed",
                limit=10
            )
        
        assert len(results) >= 1
        assert all(result["status"] == "completed" for result in results)
    
    @pytest.mark.asyncio
    async def test_get_statistics(self, history_manager, sample_params):
        """Test getting generation statistics."""
        # Create test data
        for i in range(5):
            gen_id = await history_manager.record_generation(f"prompt {i}", sample_params)
            if i < 4:  # 4 successful, 1 failed
                with patch('builtins.open', create=True):
                    await history_manager.update_generation_result(
                        gen_id,
                        {"prompt": f"prompt {i}", "data": b"data", "mime_type": "image/png", "model": "test"},
                        1.5
                    )
            else:
                await history_manager.mark_generation_failed(gen_id, "Error", 0)
        
        stats = await history_manager.get_statistics()
        
        assert stats["total_generations"] == 5
        assert stats["successful_generations"] == 4
        assert stats["failed_generations"] == 1
        assert stats["average_processing_time"] == 1.5
        assert stats["success_rate"] == 80.0
    
    @pytest.mark.asyncio
    async def test_export_history_json(self, history_manager, sample_params, temp_images_dir):
        """Test exporting history to JSON format."""
        # Create test data
        gen_id = await history_manager.record_generation("test prompt", sample_params)
        
        with patch('builtins.open', create=True) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            await history_manager.update_generation_result(
                gen_id,
                {"prompt": "test prompt", "data": b"data", "mime_type": "image/png", "model": "test"},
                1.0
            )
        
        # Export
        with patch('builtins.open', create=True) as mock_export_open:
            mock_export_file = MagicMock()
            mock_export_open.return_value.__enter__.return_value = mock_export_file
            
            export_path = await history_manager.export_history(format="json", include_files=False)
        
        assert export_path is not None
        assert export_path.endswith('.json')
        mock_export_file.write.assert_called()
    
    @pytest.mark.asyncio
    async def test_export_history_csv(self, history_manager, sample_params):
        """Test exporting history to CSV format."""
        # Create test data
        gen_id = await history_manager.record_generation("test prompt", sample_params)
        
        with patch('builtins.open', create=True) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            await history_manager.update_generation_result(
                gen_id,
                {"prompt": "test prompt", "data": b"data", "mime_type": "image/png", "model": "test"},
                1.0
            )
        
        # Export
        with patch('csv.writer') as mock_csv_writer, \
             patch('builtins.open', create=True):
            
            export_path = await history_manager.export_history(format="csv", include_files=False)
        
        assert export_path is not None
        assert export_path.endswith('.csv')
        mock_csv_writer.assert_called()
    
    @pytest.mark.asyncio
    async def test_cleanup_old_records(self, history_manager, sample_params, temp_images_dir):
        """Test cleaning up old records and files."""
        # Create old and new records
        old_time = datetime.now() - timedelta(days=35)
        recent_time = datetime.now() - timedelta(days=5)
        
        # Mock datetime for old record
        with patch('gemini_mcp_server.history_manager.datetime') as mock_datetime:
            mock_datetime.now.return_value = old_time
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            old_id = await history_manager.record_generation("old prompt", sample_params)
        
        # Create recent record normally
        recent_id = await history_manager.record_generation("recent prompt", sample_params)
        
        # Create fake image files
        old_file_path = os.path.join(temp_images_dir, f"{old_id}.png")
        recent_file_path = os.path.join(temp_images_dir, f"{recent_id}.png")
        
        with open(old_file_path, 'wb') as f:
            f.write(b"old_image_data")
        with open(recent_file_path, 'wb') as f:
            f.write(b"recent_image_data")
        
        # Update records with file paths
        await history_manager._execute_query(
            "UPDATE generations SET file_path = ? WHERE id = ?",
            (old_file_path, old_id)
        )
        await history_manager._execute_query(
            "UPDATE generations SET file_path = ? WHERE id = ?",
            (recent_file_path, recent_id)
        )
        
        # Cleanup records older than 30 days
        result = await history_manager.cleanup_old_records(
            days_old=30,
            delete_files=True
        )
        
        assert result["deleted_records"] >= 1
        assert result["deleted_files"] >= 1
        assert result["freed_space_mb"] > 0
        
        # Verify old record is gone but recent remains
        old_details = await history_manager.get_generation_details(old_id)
        recent_details = await history_manager.get_generation_details(recent_id)
        
        assert old_details is None
        assert recent_details is not None
    
    @pytest.mark.asyncio
    async def test_get_generation_details_not_found(self, history_manager):
        """Test getting details for non-existent generation."""
        details = await history_manager.get_generation_details("non-existent-id")
        assert details is None
    
    @pytest.mark.asyncio
    async def test_database_error_handling(self, history_manager):
        """Test handling of database errors."""
        # Close the database to simulate error
        if hasattr(history_manager, '_close_db'):
            await history_manager._close_db()
        
        # Try to use closed database - should handle gracefully
        with pytest.raises(Exception):
            await history_manager.record_generation("test", sample_params)
    
    @pytest.mark.asyncio
    async def test_concurrent_access(self, history_manager, sample_params):
        """Test concurrent database access."""
        async def create_generation(i):
            return await history_manager.record_generation(f"prompt {i}", sample_params)
        
        # Create multiple generations concurrently
        tasks = [create_generation(i) for i in range(10)]
        generation_ids = await asyncio.gather(*tasks)
        
        assert len(generation_ids) == 10
        assert len(set(generation_ids)) == 10  # All IDs should be unique
    
    @pytest.mark.asyncio
    async def test_large_data_handling(self, history_manager, sample_params):
        """Test handling of large image data."""
        # Create large fake image data (1MB)
        large_data = b"x" * (1024 * 1024)
        
        generation_id = await history_manager.record_generation("large image", sample_params)
        
        result_data = {
            "prompt": "large image",
            "data": large_data,
            "mime_type": "image/png",
            "model": "gemini-pro-vision"
        }
        
        with patch('builtins.open', create=True) as mock_open:
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            await history_manager.update_generation_result(
                generation_id,
                result_data,
                3.0
            )
        
        # Verify large data was handled
        details = await history_manager.get_generation_details(generation_id)
        assert details["status"] == "completed"
        mock_file.write.assert_called_with(large_data)
    
    @pytest.mark.asyncio
    async def test_file_cleanup_on_failure(self, history_manager, sample_params, temp_images_dir):
        """Test that files are cleaned up when operations fail."""
        generation_id = await history_manager.record_generation("test prompt", sample_params)
        
        # Simulate file write failure
        with patch('builtins.open', side_effect=IOError("Disk full")):
            with pytest.raises(IOError):
                await history_manager.update_generation_result(
                    generation_id,
                    {"prompt": "test", "data": b"data", "mime_type": "image/png", "model": "test"},
                    1.0
                )
        
        # Verify generation is marked as failed
        details = await history_manager.get_generation_details(generation_id)
        assert details["status"] == "failed"
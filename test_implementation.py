#!/usr/bin/env python3
"""
Simple test script to validate the main functionality.
This doesn't require external dependencies to be installed.
"""

import os
import sys
import tempfile
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_exceptions():
    """Test the exceptions module."""
    print("Testing exceptions module...")
    try:
        from gemini_mcp_server.exceptions import (
            GeminiMCPError, RateLimitError, ValidationError
        )
        
        # Test basic exception
        error = GeminiMCPError("test message", "TEST_CODE")
        assert error.message == "test message"
        assert error.error_code == "TEST_CODE"
        
        # Test rate limit error
        rate_error = RateLimitError(retry_after=30.0)
        assert rate_error.retry_after == 30.0
        
        print("✓ Exceptions module works correctly")
        return True
    except Exception as e:
        print(f"✗ Exceptions module failed: {e}")
        return False

def test_image_parameters():
    """Test the image parameters module."""
    print("Testing image parameters module...")
    try:
        from gemini_mcp_server.image_parameters import (
            ImageGenerationParameters, AspectRatio, ImageStyle
        )
        
        # Test default parameters
        params = ImageGenerationParameters(prompt="test prompt")
        assert params.prompt == "test prompt"
        assert params.aspect_ratio == AspectRatio.SQUARE
        
        # Test enhanced prompt
        enhanced = params.get_enhanced_prompt()
        assert "test prompt" in enhanced
        
        # Test generation config
        config = params.to_generation_config()
        assert "temperature" in config
        assert "max_output_tokens" in config
        
        print("✓ Image parameters module works correctly")
        return True
    except Exception as e:
        print(f"✗ Image parameters module failed: {e}")
        return False

def test_history_manager():
    """Test the history manager module."""
    print("Testing history manager module...")
    try:
        from gemini_mcp_server.history_manager import ImageHistoryManager
        
        # Create a temporary database
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = tmp.name
        
        try:
            # Initialize manager
            manager = ImageHistoryManager(db_path=db_path)
            
            # Test that database was created
            assert Path(db_path).exists()
            
            print("✓ History manager module works correctly")
            return True
        finally:
            # Cleanup
            if Path(db_path).exists():
                os.unlink(db_path)
            
    except Exception as e:
        print(f"✗ History manager module failed: {e}")
        return False

def test_queue_manager():
    """Test the queue manager module."""
    print("Testing queue manager module...")
    try:
        from gemini_mcp_server.queue_manager import (
            AsyncRequestQueue, RequestStatus, RequestPriority
        )
        
        # Test basic queue creation
        queue = AsyncRequestQueue(max_concurrent=1, max_queue_size=10)
        
        # Test enum values
        assert RequestStatus.PENDING.value == "pending"
        assert RequestPriority.HIGH.value == "high"
        
        print("✓ Queue manager module works correctly")
        return True
    except Exception as e:
        print(f"✗ Queue manager module failed: {e}")
        return False

def main():
    """Run all tests."""
    print("Running validation tests...\n")
    
    tests = [
        test_exceptions,
        test_image_parameters,
        test_history_manager,
        test_queue_manager,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
            failed += 1
        print()
    
    print(f"Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! The implementation looks good.")
        return 0
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
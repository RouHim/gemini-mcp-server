"""Tests for image generation parameters."""

import pytest
from src.gemini_mcp_server.image_parameters import (
    ImageGenerationParameters,
    AspectRatio,
    ImageStyle,
    SafetyLevel,
    ImageQuality,
)


def test_image_generation_parameters_default():
    """Test default parameters."""
    params = ImageGenerationParameters(prompt="test prompt")

    assert params.prompt == "test prompt"
    assert params.aspect_ratio == AspectRatio.SQUARE
    assert params.style == ImageStyle.REALISTIC
    assert params.safety_level == SafetyLevel.MODERATE
    assert params.quality == ImageQuality.STANDARD
    assert params.temperature == 0.7


def test_image_generation_parameters_custom():
    """Test custom parameters."""
    params = ImageGenerationParameters(
        prompt="test prompt",
        aspect_ratio=AspectRatio.LANDSCAPE_16_9,
        style=ImageStyle.ARTISTIC,
        safety_level=SafetyLevel.STRICT,
        quality=ImageQuality.HIGH,
        temperature=0.5,
    )

    assert params.prompt == "test prompt"
    assert params.aspect_ratio == AspectRatio.LANDSCAPE_16_9
    assert params.style == ImageStyle.ARTISTIC
    assert params.safety_level == SafetyLevel.STRICT
    assert params.quality == ImageQuality.HIGH
    assert params.temperature == 0.5


def test_prompt_validation():
    """Test prompt validation."""
    # Empty prompt should fail
    with pytest.raises(ValueError):
        ImageGenerationParameters(prompt="")

    # Whitespace-only prompt should fail
    with pytest.raises(ValueError):
        ImageGenerationParameters(prompt="   ")

    # Valid prompt should work
    params = ImageGenerationParameters(prompt="  test prompt  ")
    assert params.prompt == "test prompt"


def test_temperature_validation():
    """Test temperature validation."""
    # Valid temperature
    params = ImageGenerationParameters(prompt="test", temperature=0.5)
    assert params.temperature == 0.5

    # Invalid temperatures should fail
    with pytest.raises(ValueError):
        ImageGenerationParameters(prompt="test", temperature=-0.1)

    with pytest.raises(ValueError):
        ImageGenerationParameters(prompt="test", temperature=1.1)


def test_to_generation_config():
    """Test generation config conversion."""
    # Standard quality
    params = ImageGenerationParameters(
        prompt="test", quality=ImageQuality.STANDARD, temperature=0.8
    )
    config = params.to_generation_config()

    assert config["temperature"] == 0.8
    assert config["max_output_tokens"] == 2048
    assert config["top_p"] == 0.9
    assert config["top_k"] == 40

    # High quality
    params = ImageGenerationParameters(
        prompt="test", quality=ImageQuality.HIGH, temperature=0.5
    )
    config = params.to_generation_config()

    assert config["temperature"] == 0.5
    assert config["max_output_tokens"] == 4096
    assert config["top_p"] == 0.95
    assert config["top_k"] == 50


def test_get_enhanced_prompt():
    """Test enhanced prompt generation."""
    params = ImageGenerationParameters(
        prompt="a cat",
        style=ImageStyle.PHOTOGRAPHIC,
        aspect_ratio=AspectRatio.LANDSCAPE_16_9,
    )

    enhanced = params.get_enhanced_prompt()
    assert "realistic photograph" in enhanced
    assert "wide landscape format" in enhanced
    assert "a cat" in enhanced


def test_aspect_ratio_enum():
    """Test aspect ratio enum values."""
    assert AspectRatio.SQUARE.value == "1:1"
    assert AspectRatio.LANDSCAPE_16_9.value == "16:9"
    assert AspectRatio.PORTRAIT_9_16.value == "9:16"


def test_image_style_enum():
    """Test image style enum values."""
    assert ImageStyle.PHOTOGRAPHIC.value == "photographic"
    assert ImageStyle.ARTISTIC.value == "artistic"
    assert ImageStyle.SKETCH.value == "sketch"


def test_safety_level_enum():
    """Test safety level enum values."""
    assert SafetyLevel.STRICT.value == "strict"
    assert SafetyLevel.MODERATE.value == "moderate"
    assert SafetyLevel.PERMISSIVE.value == "permissive"


def test_image_quality_enum():
    """Test image quality enum values."""
    assert ImageQuality.STANDARD.value == "standard"
    assert ImageQuality.HIGH.value == "high"

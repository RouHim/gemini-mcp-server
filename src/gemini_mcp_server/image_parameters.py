"""Image generation parameter definitions and validation."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class AspectRatio(str, Enum):
    """Supported aspect ratios for image generation."""

    SQUARE = "1:1"
    LANDSCAPE_16_9 = "16:9"
    PORTRAIT_9_16 = "9:16"
    LANDSCAPE_4_3 = "4:3"
    PORTRAIT_3_4 = "3:4"


class ImageStyle(str, Enum):
    """Supported image styles."""

    PHOTOGRAPHIC = "photographic"
    ARTISTIC = "artistic"
    SKETCH = "sketch"
    DIGITAL_ART = "digital-art"
    CARTOON = "cartoon"
    REALISTIC = "realistic"


class SafetyLevel(str, Enum):
    """Safety filter levels."""

    STRICT = "strict"
    MODERATE = "moderate"
    PERMISSIVE = "permissive"


class ImageQuality(str, Enum):
    """Image quality settings optimized for free tier."""

    STANDARD = "standard"
    HIGH = "high"


class ImageGenerationParameters(BaseModel):
    """Parameters for image generation."""

    prompt: str = Field(
        ...,
        description="Text prompt for image generation",
        min_length=1,
        max_length=1000,
    )
    aspect_ratio: AspectRatio = Field(
        default=AspectRatio.SQUARE, description="Aspect ratio of the generated image"
    )
    style: ImageStyle = Field(
        default=ImageStyle.REALISTIC, description="Style of the generated image"
    )
    safety_level: SafetyLevel = Field(
        default=SafetyLevel.MODERATE, description="Content safety filtering level"
    )
    quality: ImageQuality = Field(
        default=ImageQuality.STANDARD, description="Image quality setting"
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Creativity level (0.0 = deterministic, 1.0 = very creative)",
    )

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, v):
        """Validate prompt content."""
        if not v.strip():
            raise ValueError("Prompt cannot be empty or only whitespace")
        return v.strip()

    def to_generation_config(self) -> dict[str, Any]:
        """Convert parameters to Gemini generation config."""
        # Map quality to specific parameters
        if self.quality == ImageQuality.HIGH:
            max_tokens = 4096
            top_p = 0.95
            top_k = 50
        else:  # STANDARD
            max_tokens = 2048
            top_p = 0.9
            top_k = 40

        return {
            "temperature": self.temperature,
            "top_p": top_p,
            "top_k": top_k,
            "max_output_tokens": max_tokens,
        }

    def get_enhanced_prompt(self) -> str:
        """Get enhanced prompt with style and aspect ratio information."""
        style_prompts = {
            ImageStyle.PHOTOGRAPHIC: "realistic photograph",
            ImageStyle.ARTISTIC: "artistic rendering",
            ImageStyle.SKETCH: "pencil sketch",
            ImageStyle.DIGITAL_ART: "digital art",
            ImageStyle.CARTOON: "cartoon style",
            ImageStyle.REALISTIC: "realistic image",
        }

        aspect_ratio_prompts = {
            AspectRatio.SQUARE: "square format",
            AspectRatio.LANDSCAPE_16_9: "wide landscape format",
            AspectRatio.PORTRAIT_9_16: "tall portrait format",
            AspectRatio.LANDSCAPE_4_3: "landscape format",
            AspectRatio.PORTRAIT_3_4: "portrait format",
        }

        enhanced_prompt = f"Generate a {style_prompts[self.style]} in {aspect_ratio_prompts[self.aspect_ratio]}: {self.prompt}"
        return enhanced_prompt

    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "A beautiful sunset over mountains",
                "aspect_ratio": "16:9",
                "style": "photographic",
                "safety_level": "moderate",
                "quality": "standard",
                "temperature": 0.7,
            }
        }

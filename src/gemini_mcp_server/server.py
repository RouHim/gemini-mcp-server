#!/usr/bin/env python3

import asyncio
import logging
import os
from typing import Any, Sequence

import google.generativeai as genai
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequest,
    ListToolsRequest,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from .gemini_client import GeminiImageClient
from .rate_limiter import RateLimiter

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize server
server = Server("gemini-mcp-server")

# Initialize rate limiter (15 requests per minute for free tier)
rate_limiter = RateLimiter(max_calls=15, time_window=60)

# Initialize Gemini client
gemini_client = None


class ImageGenerationRequest(BaseModel):
    prompt: str = Field(..., description="Text prompt for image generation")
    
    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "A beautiful sunset over mountains"
            }
        }


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="generate_image",
            description="Generate an image from a text prompt using Google Gemini",
            inputSchema=ImageGenerationRequest.model_json_schema(),
        )
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any] | None
) -> list[TextContent | ImageContent | EmbeddedResource]:
    """Handle tool calls."""
    if name != "generate_image":
        raise ValueError(f"Unknown tool: {name}")
    
    if not arguments:
        raise ValueError("Missing arguments")
    
    # Validate arguments
    try:
        request = ImageGenerationRequest(**arguments)
    except Exception as e:
        raise ValueError(f"Invalid arguments: {e}")
    
    # Check rate limit
    if not await rate_limiter.acquire():
        raise ValueError("Rate limit exceeded. Please wait before making another request.")
    
    try:
        # Generate image using Gemini client
        image_data = await gemini_client.generate_image(request.prompt)
        
        return [
            TextContent(
                type="text",
                text=f"Successfully generated image from prompt: '{request.prompt}'"
            ),
            ImageContent(
                type="image",
                data=image_data["data"],
                mimeType=image_data["mime_type"]
            )
        ]
    
    except Exception as e:
        logger.error(f"Error generating image: {e}")
        return [
            TextContent(
                type="text", 
                text=f"Error generating image: {str(e)}"
            )
        ]


async def main():
    """Main server function."""
    global gemini_client
    
    # Check for API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY environment variable not set")
        raise ValueError("GEMINI_API_KEY environment variable is required")
    
    # Initialize Gemini client
    try:
        gemini_client = GeminiImageClient(api_key)
        await gemini_client.initialize()
        logger.info("Gemini client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Gemini client: {e}")
        raise
    
    # Run the server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, 
            write_stream, 
            InitializationOptions(
                server_name="gemini-mcp-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=None,
                    experimental_capabilities=None,
                ),
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
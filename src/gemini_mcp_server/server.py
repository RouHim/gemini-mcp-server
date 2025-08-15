#!/usr/bin/env python3

import asyncio
import logging
import os
from typing import Any, cast

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    EmbeddedResource,
    ImageContent,
    TextContent,
    Tool,
)
from pydantic import BaseModel

from .exceptions import ValidationError
from .gemini_client import GeminiImageClient
from .image_parameters import ImageGenerationParameters
from .queue_manager import RequestPriority, get_request_queue
from .rate_limiter import RateLimiter
from .retry_handler import (
    create_structured_error_response,
)

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


class QueueStatusRequest(BaseModel):
    """Request for queue status."""

    pass


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="generate_image",
            description="Generate an image from a text prompt using Google Gemini with configurable parameters",
            inputSchema=ImageGenerationParameters.model_json_schema(),
        ),
        Tool(
            name="get_queue_status",
            description="Get the current status of the request queue",
            inputSchema=QueueStatusRequest.model_json_schema(),
        ),
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any] | None
) -> list[TextContent | ImageContent | EmbeddedResource]:
    """Handle tool calls."""

    if name == "generate_image":
        return await handle_generate_image(arguments)
    elif name == "get_queue_status":
        return cast(
            "list[TextContent | ImageContent | EmbeddedResource]",
            await handle_get_queue_status(),
        )
    else:
        raise ValueError(f"Unknown tool: {name}")


async def handle_generate_image(
    arguments: dict[str, Any] | None,
) -> list[TextContent | ImageContent | EmbeddedResource]:
    """Handle image generation requests."""
    if not arguments:
        raise ValueError("Missing arguments")

    # Validate arguments
    try:
        request = ImageGenerationParameters(**arguments)
    except Exception as e:
        raise ValidationError(f"Invalid arguments: {e}")

    # Get the request queue
    queue = get_request_queue()
    if not queue._worker_task:
        await queue.start()

    try:
        # Enqueue the generation request
        request_id = await queue.enqueue(
            _generate_image, request, priority=RequestPriority.NORMAL
        )

        # Wait for completion
        completed_request = await queue.wait_for_completion(
            request_id, timeout=300
        )  # 5 minutes

        if completed_request.status.value == "completed" and completed_request.result:
            result = completed_request.result

            return [
                TextContent(
                    type="text",
                    text=f"Successfully generated image from prompt: '{request.prompt}'\n"
                    f"Parameters: {request.model_dump()}",
                ),
                ImageContent(
                    type="image", data=result["data"], mimeType=result["mime_type"]
                ),
            ]
        else:
            error_msg = completed_request.error or "Unknown error occurred"
            return [
                TextContent(type="text", text=f"Error generating image: {error_msg}")
            ]

    except Exception as e:
        error_response = create_structured_error_response(e)
        return [TextContent(type="text", text=f"Error: {error_response['message']}")]


async def _generate_image(request: ImageGenerationParameters) -> dict[Any, Any]:
    """Generate image."""
    try:
        # Ensure client is initialized
        assert gemini_client is not None, "Gemini client not initialized"

        # Generate the image
        result = await gemini_client.generate_image(
            prompt=request.get_enhanced_prompt(),
            **request.to_generation_config(),
            safety_level=request.safety_level.value,
        )

        return result

    except Exception:
        raise


async def handle_get_queue_status() -> list[TextContent]:
    """Handle queue status requests."""
    try:
        queue = get_request_queue()
        stats = await queue.get_queue_stats()

        return [
            TextContent(
                type="text",
                text=f"Queue Status:\n"
                f"- Queue size: {stats['queue_size']}\n"
                f"- Processing: {stats['processing_count']}/{stats['max_concurrent']}\n"
                f"- Rate limit: {stats['requests_last_minute']}/{stats['rate_limit_per_minute']} per minute\n"
                f"- Wait time: {stats['wait_time_seconds']:.1f} seconds",
            )
        ]
    except Exception as e:
        return [TextContent(type="text", text=f"Error getting queue status: {e!s}")]


async def main() -> None:
    """Main server function."""
    global gemini_client

    # Check for API key
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.error("GOOGLE_API_KEY environment variable not set")
        raise ValueError("GOOGLE_API_KEY environment variable is required")

    # Initialize Gemini client
    try:
        gemini_client = GeminiImageClient(api_key)
        await gemini_client.initialize()
        logger.info("Gemini client initialized successfully")
    except Exception as e:
        logger.exception(f"Failed to initialize Gemini client: {e}")
        raise

    # Initialize the request queue
    queue = get_request_queue()
    await queue.start()
    logger.info("Request queue started")

    try:
        # Run the server
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="gemini-mcp-server",
                    server_version="0.2.0",
                    capabilities=server.get_capabilities(
                        notification_options=None,
                        experimental_capabilities=None,
                    ),
                ),
            )
    finally:
        # Cleanup
        await queue.stop()
        logger.info("Server shutdown complete")


def console_main() -> None:
    """Console script entry point."""
    asyncio.run(main())


if __name__ == "__main__":
    console_main()

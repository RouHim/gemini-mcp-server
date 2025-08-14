#!/usr/bin/env python3

import asyncio
import logging
import os
import base64
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
from .image_parameters import ImageGenerationParameters
from .queue_manager import get_request_queue, RequestPriority
from .history_manager import get_history_manager
from .retry_handler import (
    get_user_friendly_error_message,
    create_structured_error_response,
)
from .exceptions import ValidationError

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


class HistoryRequest(BaseModel):
    """Request for generation history."""

    limit: int = Field(
        default=10, ge=1, le=100, description="Number of records to return"
    )
    offset: int = Field(default=0, ge=0, description="Number of records to skip")
    success_only: bool = Field(
        default=False, description="Only return successful generations"
    )


class SearchHistoryRequest(BaseModel):
    """Request for searching generation history."""

    search_term: str = Field(..., description="Search term to look for in prompts")
    limit: int = Field(
        default=10, ge=1, le=50, description="Number of records to return"
    )


class ExportHistoryRequest(BaseModel):
    """Request for exporting generation history."""

    format: str = Field(default="json", description="Export format (json or csv)")
    include_files: bool = Field(
        default=False, description="Include base64 encoded image data"
    )


class CleanupRequest(BaseModel):
    """Request for cleanup operations."""

    dry_run: bool = Field(
        default=True, description="If true, only report what would be deleted"
    )


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
        Tool(
            name="get_generation_history",
            description="Get image generation history with filtering options",
            inputSchema=HistoryRequest.model_json_schema(),
        ),
        Tool(
            name="search_generation_history",
            description="Search image generation history by prompt text",
            inputSchema=SearchHistoryRequest.model_json_schema(),
        ),
        Tool(
            name="get_generation_statistics",
            description="Get generation statistics and usage metrics",
            inputSchema=QueueStatusRequest.model_json_schema(),  # No parameters needed
        ),
        Tool(
            name="export_generation_history",
            description="Export generation history to JSON or CSV format",
            inputSchema=ExportHistoryRequest.model_json_schema(),
        ),
        Tool(
            name="cleanup_old_files",
            description="Cleanup old image files based on retention policies",
            inputSchema=CleanupRequest.model_json_schema(),
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
        return await handle_get_queue_status()
    elif name == "get_generation_history":
        return await handle_get_generation_history(arguments)
    elif name == "search_generation_history":
        return await handle_search_generation_history(arguments)
    elif name == "get_generation_statistics":
        return await handle_get_generation_statistics()
    elif name == "export_generation_history":
        return await handle_export_generation_history(arguments)
    elif name == "cleanup_old_files":
        return await handle_cleanup_old_files(arguments)
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
            _generate_image_with_history, request, priority=RequestPriority.NORMAL
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
                    f"Parameters: {request.dict()}\n"
                    f"Generation ID: {result.get('generation_id', 'unknown')}",
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


async def _generate_image_with_history(request: ImageGenerationParameters) -> dict:
    """Generate image and save to history."""
    import time

    start_time = time.time()
    history_manager = get_history_manager()

    try:
        # Generate the image
        result = await gemini_client.generate_image(
            prompt=request.get_enhanced_prompt(),
            **request.to_generation_config(),
            safety_level=request.safety_level.value,
        )

        generation_time = time.time() - start_time

        # Decode image data for storage
        image_data = None
        if result.get("data"):
            try:
                image_data = base64.b64decode(result["data"])
            except Exception as e:
                logger.warning(f"Failed to decode image data: {e}")

        # Save to history
        generation_id = await history_manager.save_generation(
            prompt=request.prompt,
            parameters=request.dict(),
            image_data=image_data,
            success=True,
            generation_time=generation_time,
            model=result.get("model", "unknown"),
        )

        result["generation_id"] = generation_id
        return result

    except Exception as e:
        generation_time = time.time() - start_time

        # Save failed generation to history
        await history_manager.save_generation(
            prompt=request.prompt,
            parameters=request.dict(),
            success=False,
            error_message=str(e),
            generation_time=generation_time,
        )

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
        return [TextContent(type="text", text=f"Error getting queue status: {str(e)}")]


async def handle_get_generation_history(
    arguments: dict[str, Any] | None,
) -> list[TextContent]:
    """Handle generation history requests."""
    try:
        request = HistoryRequest(**(arguments or {}))
        history_manager = get_history_manager()

        history = await history_manager.get_history(
            limit=request.limit,
            offset=request.offset,
            success_only=request.success_only,
        )

        if not history:
            return [TextContent(type="text", text="No generation history found.")]

        history_text = "Generation History:\n\n"
        for item in history:
            status = "✓" if item.success else "✗"
            history_text += f"{status} {item.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
            history_text += f"   ID: {item.id}\n"
            history_text += f"   Prompt: {item.prompt[:100]}{'...' if len(item.prompt) > 100 else ''}\n"
            history_text += f"   Model: {item.model}\n"
            if item.generation_time:
                history_text += f"   Time: {item.generation_time:.2f}s\n"
            if item.error_message:
                history_text += f"   Error: {item.error_message}\n"
            history_text += "\n"

        return [TextContent(type="text", text=history_text)]
    except Exception as e:
        return [
            TextContent(type="text", text=f"Error getting generation history: {str(e)}")
        ]


async def handle_search_generation_history(
    arguments: dict[str, Any] | None,
) -> list[TextContent]:
    """Handle search history requests."""
    try:
        if not arguments:
            raise ValueError("Missing search term")

        request = SearchHistoryRequest(**arguments)
        history_manager = get_history_manager()

        results = await history_manager.search_history(
            search_term=request.search_term,
            limit=request.limit,
        )

        if not results:
            return [
                TextContent(
                    type="text", text=f"No results found for '{request.search_term}'"
                )
            ]

        results_text = f"Search Results for '{request.search_term}':\n\n"
        for item in results:
            status = "✓" if item.success else "✗"
            results_text += f"{status} {item.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
            results_text += f"   ID: {item.id}\n"
            results_text += f"   Prompt: {item.prompt}\n"
            results_text += f"   Model: {item.model}\n\n"

        return [TextContent(type="text", text=results_text)]
    except Exception as e:
        return [
            TextContent(
                type="text", text=f"Error searching generation history: {str(e)}"
            )
        ]


async def handle_get_generation_statistics() -> list[TextContent]:
    """Handle generation statistics requests."""
    try:
        history_manager = get_history_manager()
        stats = await history_manager.get_statistics()

        stats_text = "Generation Statistics:\n\n"
        stats_text += f"Total generations: {stats.get('total_generations', 0)}\n"
        stats_text += f"Successful: {stats.get('successful_generations', 0)}\n"
        stats_text += f"Failed: {stats.get('failed_generations', 0)}\n"
        stats_text += f"Success rate: {stats.get('success_rate', 0.0):.1%}\n"
        stats_text += f"Average generation time: {stats.get('average_generation_time', 0.0):.2f}s\n"
        stats_text += (
            f"Storage used: {stats.get('total_storage_size_mb', 0.0):.1f} MB\n"
        )
        stats_text += (
            f"Recent activity (7 days): {stats.get('recent_generations_7_days', 0)}\n\n"
        )

        model_counts = stats.get("model_counts", {})
        if model_counts:
            stats_text += "Model usage:\n"
            for model, count in model_counts.items():
                stats_text += f"  {model}: {count}\n"

        return [TextContent(type="text", text=stats_text)]
    except Exception as e:
        return [
            TextContent(
                type="text", text=f"Error getting generation statistics: {str(e)}"
            )
        ]


async def handle_export_generation_history(
    arguments: dict[str, Any] | None,
) -> list[TextContent]:
    """Handle export history requests."""
    try:
        request = ExportHistoryRequest(**(arguments or {}))
        history_manager = get_history_manager()

        exported_data = await history_manager.export_history(
            format=request.format,
            include_files=request.include_files,
        )

        return [
            TextContent(
                type="text",
                text=f"Exported generation history in {request.format.upper()} format:\n\n{exported_data}",
            )
        ]
    except Exception as e:
        return [
            TextContent(
                type="text", text=f"Error exporting generation history: {str(e)}"
            )
        ]


async def handle_cleanup_old_files(
    arguments: dict[str, Any] | None,
) -> list[TextContent]:
    """Handle cleanup requests."""
    try:
        request = CleanupRequest(**(arguments or {}))
        history_manager = get_history_manager()

        result = await history_manager.cleanup_old_files(dry_run=request.dry_run)

        if "error" in result:
            return [TextContent(type="text", text=f"Cleanup error: {result['error']}")]

        action = "Would delete" if result["dry_run"] else "Deleted"
        cleanup_text = f"Cleanup Results:\n\n"
        cleanup_text += f"{action} {result['deleted_count']} files\n"
        cleanup_text += f"Space freed: {result['deleted_size_mb']:.1f} MB\n"

        if result.get("errors"):
            cleanup_text += f"\nErrors:\n"
            for error in result["errors"]:
                cleanup_text += f"  {error}\n"

        return [TextContent(type="text", text=cleanup_text)]
    except Exception as e:
        return [TextContent(type="text", text=f"Error during cleanup: {str(e)}")]


async def main():
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
        logger.error(f"Failed to initialize Gemini client: {e}")
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

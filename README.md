# Gemini MCP Server

MCP server for Gemini image generation optimized for free tier usage with comprehensive features for production use.

## Features

- 🎨 **Advanced Image Generation**: Generate images from text prompts using Google's Gemini 2.0 Flash Experimental
- 🚀 **Free Tier Optimized**: Built specifically for free tier rate limits (15 requests/minute) and quotas
- ⚡ **Async Queue Management**: Intelligent request queuing with priority support and persistence
- 🛡️ **Robust Error Handling**: Comprehensive retry logic, circuit breaker pattern, and structured error responses
- 📊 **History Tracking**: Complete generation history with metadata, search, and export capabilities
- 🔧 **Configurable Parameters**: Customize aspect ratios, styles, safety settings, and quality levels
- 🗄️ **Optional Local Storage**: Save generated images locally with automatic cleanup policies
- 📈 **Usage Statistics**: Track generation metrics, success rates, and storage usage

## Quick Start

### Prerequisites

- Python 3.10 or higher
- Google AI API key (get one [here](https://makersuite.google.com/app/apikey))

### Installation

```bash
# Clone the repository
git clone https://github.com/RouHim/gemini-mcp-server.git
cd gemini-mcp-server

# Install dependencies
pip install -e .

# Copy environment template and add your API key
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

### Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Required
GEMINI_API_KEY=your_gemini_api_key_here

# Optional storage configuration
IMAGE_STORAGE_PATH=/path/to/store/images  # Enable local image storage
MAX_STORAGE_MB=1000                       # Maximum storage size in MB
MAX_AGE_DAYS=30                          # Maximum age of stored images
MAX_IMAGE_COUNT=100                      # Maximum number of images to keep
```

### Usage

```bash
# Start the MCP server
python -m gemini_mcp_server.server

# Or use the main entry point
python main.py
```

## MCP Tools

### Core Generation

#### `generate_image`
Generate an image from a text prompt with advanced configuration options.

**Parameters:**
- `prompt` (string, required): Text description of the image to generate
- `aspect_ratio` (string, optional): Image aspect ratio
  - `"1:1"` - Square (default)
  - `"16:9"` - Wide landscape
  - `"9:16"` - Tall portrait
  - `"4:3"` - Standard landscape
  - `"3:4"` - Standard portrait
- `style` (string, optional): Artistic style
  - `"realistic"` - Photorealistic images (default)
  - `"photographic"` - Professional photography style
  - `"artistic"` - Artistic rendering
  - `"sketch"` - Pencil sketch style
  - `"digital-art"` - Digital art style
  - `"cartoon"` - Cartoon style
- `safety_level` (string, optional): Content filtering level
  - `"moderate"` - Balanced filtering (default)
  - `"strict"` - Strict content filtering
  - `"permissive"` - Minimal filtering
- `quality` (string, optional): Image quality setting
  - `"standard"` - Optimized for free tier (default)
  - `"high"` - Higher quality, more tokens
- `temperature` (number, optional): Creativity level (0.0-1.0, default: 0.7)

**Example:**
```json
{
  "prompt": "A serene mountain landscape at sunset",
  "aspect_ratio": "16:9",
  "style": "photographic",
  "safety_level": "moderate",
  "quality": "standard",
  "temperature": 0.8
}
```

### Queue Management

#### `get_queue_status`
Get the current status of the request queue.

**Returns:**
- Queue size and processing status
- Rate limit usage
- Wait time estimates

### History and Analytics

#### `get_generation_history`
Retrieve image generation history with filtering options.

**Parameters:**
- `limit` (number, optional): Maximum number of entries to return (1-100, default: 10)
- `offset` (number, optional): Number of entries to skip (default: 0)
- `success_only` (boolean, optional): Only return successful generations (default: false)

#### `search_generation_history`
Search generation history by prompt text.

**Parameters:**
- `search_term` (string, required): Text to search for in prompts
- `limit` (number, optional): Maximum number of results (1-50, default: 10)

#### `get_generation_statistics`
Get comprehensive generation statistics and metrics.

**Returns:**
- Total/successful/failed generation counts
- Success rate and average generation time
- Storage usage and model breakdown
- Recent activity metrics

#### `export_generation_history`
Export generation history to JSON or CSV format.

**Parameters:**
- `format` (string, optional): Export format ("json" or "csv", default: "json")
- `include_files` (boolean, optional): Include base64 encoded image data (default: false)

### Storage Management

#### `cleanup_old_files`
Manually clean up old image files based on retention policies.

**Parameters:**
- `dry_run` (boolean, optional): Only report what would be deleted (default: true)

**Returns:**
- Number of files that would be/were deleted
- Amount of storage space freed
- Any errors encountered

## Free Tier Optimization

The server is specifically designed to work efficiently with Gemini's free tier:

### Rate Limiting
- **15 requests per minute** limit enforcement
- Automatic queuing when limits are reached
- Exponential backoff for rate limit errors

### Request Management
- **Async queue system** with priority support
- **Circuit breaker pattern** for repeated failures
- **Request persistence** across server restarts
- **Intelligent retry logic** with exponential backoff

### Error Handling
- **Structured error responses** with user-friendly messages
- **Comprehensive exception mapping** from Google API errors
- **Graceful degradation** with placeholder images on failure
- **Detailed logging** for debugging and monitoring

## Architecture

### Core Components

1. **GeminiImageClient**: Handles communication with Gemini API
2. **AsyncRequestQueue**: Manages request queuing and rate limiting
3. **ImageHistoryManager**: Tracks generation history and metadata
4. **RetryHandler**: Implements retry logic and error handling
5. **ImageParameters**: Validates and processes generation parameters

### Data Storage

- **SQLite databases** for queue persistence and history tracking
- **Optional local file storage** for generated images
- **Automatic cleanup** based on configurable retention policies

### Error Recovery

- **Circuit breaker pattern** prevents cascading failures
- **Exponential backoff** for transient errors
- **Structured exception hierarchy** for precise error handling
- **Fallback mechanisms** ensure service availability

## Development

### Running Tests

```bash
# Install development dependencies
pip install -e .[dev]

# Run validation tests
python test_implementation.py

# Run full test suite (requires pytest)
pytest tests/ -v

# Run with coverage
pytest --cov=src tests/

# Linting and formatting
ruff check src/ tests/
black src/ tests/
mypy src/
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass and code is properly formatted
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

- **Issues**: Report bugs and request features on [GitHub Issues](https://github.com/RouHim/gemini-mcp-server/issues)
- **Discussions**: Join the conversation in [GitHub Discussions](https://github.com/RouHim/gemini-mcp-server/discussions)

## Acknowledgments

- Built with the [Model Context Protocol (MCP)](https://github.com/modelcontextprotocol/python-sdk)
- Powered by [Google Gemini AI](https://deepmind.google/technologies/gemini/)
- Optimized for free tier usage patterns
# Gemini MCP Server

[![CI](https://github.com/RouHim/gemini-mcp-server/workflows/CI/badge.svg)](https://github.com/RouHim/gemini-mcp-server/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Model Context Protocol (MCP) server for Gemini image generation, optimized for free tier usage.

## Features

- 🎨 Image generation using Google's Gemini API
- 🚀 Free tier optimized with rate limiting (15 requests/minute)
- ⚡ Async queue management with SQLite persistence
- 🛡️ Retry logic and error handling
- 📊 Generation history tracking
- 🗄️ Optional local image storage

## Quick Start

### Prerequisites

- Python 3.10+
- [Google AI API key](https://makersuite.google.com/app/apikey)

### Installation

```bash
# Clone and install
git clone https://github.com/RouHim/gemini-mcp-server.git
cd gemini-mcp-server
pip install -e .

# Configure API key
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

### Usage

```bash
# Start the server
python -m gemini_mcp_server.server

# Or use the installed command
gemini-mcp-server
```

## MCP Tools

### `generate_image`
Generate images from text prompts.

**Parameters:**
- `prompt` (required): Text description
- `aspect_ratio` (optional): "1:1", "16:9", "9:16", "4:3", "3:4"
- `style` (optional): "realistic", "photographic", "artistic", "sketch", "digital-art", "cartoon"
- `safety_level` (optional): "moderate", "strict", "permissive"
- `quality` (optional): "standard", "high"

### `get_queue_status`
Check request queue status and rate limits.

### `get_generation_history`
Retrieve generation history with filtering.

**Parameters:**
- `limit` (optional): Max entries (1-100, default: 10)
- `offset` (optional): Skip entries (default: 0)
- `success_only` (optional): Only successful generations

### `get_generation_statistics`
Get usage statistics and metrics.

### `cleanup_old_files`
Clean up old stored images.

## Configuration

Environment variables (`.env` file):

```bash
# Required
GOOGLE_API_KEY=your_api_key_here

# Optional storage
IMAGE_STORAGE_PATH=./images
MAX_STORAGE_SIZE_MB=1000
MAX_IMAGE_COUNT=100
CLEANUP_AFTER_DAYS=30

# Optional rate limiting
MAX_REQUESTS_PER_MINUTE=15
MAX_CONCURRENT_REQUESTS=3
```

## Development

### Setup

```bash
# Install development dependencies
pip install -e .[dev]

# Or use Makefile
make dev-setup
```

### Commands

```bash
# Quality checks
make format      # Black formatting
make lint        # Ruff linting
make typecheck   # MyPy type checking

# Testing
make test        # Run all tests
make test-coverage  # Run with coverage

# All checks
make all         # Format + lint + typecheck + test
```

### Project Structure

```
src/gemini_mcp_server/
├── server.py              # MCP server
├── gemini_client.py       # Google AI client
├── queue_manager.py       # Request queue
├── history_manager.py     # History tracking
├── rate_limiter.py        # Rate limiting
├── retry_handler.py       # Error handling
├── image_parameters.py    # Parameter validation
└── exceptions.py          # Custom exceptions

tests/                     # Test suite
├── test_server.py
├── test_gemini_client.py
├── test_queue_manager.py
└── ...
```

## License

MIT License - see LICENSE file for details.

## Links

- [Issues](https://github.com/RouHim/gemini-mcp-server/issues)
- [Model Context Protocol](https://github.com/modelcontextprotocol/python-sdk)
- [Google Gemini AI](https://deepmind.google/technologies/gemini/)
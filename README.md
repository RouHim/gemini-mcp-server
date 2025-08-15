# Gemini MCP Server

[![CI](https://github.com/RouHim/gemini-mcp-server/workflows/CI/badge.svg)](https://github.com/RouHim/gemini-mcp-server/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Model Context Protocol (MCP) server for Gemini image generation, optimized for free tier usage with Claude Desktop and opencode.

## Features

- 🎨 Image generation using Google's Gemini API
- 🚀 Free tier optimized with rate limiting (15 requests/minute)
- ⚡ Async queue management with SQLite persistence
- 🛡️ Retry logic and error handling
- 📊 Generation history tracking
- 🗄️ Optional local image storage
- 🤖 Full Claude Desktop integration
- 🔧 opencode compatible
- 🛠️ [Just](https://github.com/casey/just) command runner for easy development

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

# Configure environment
cp .env.template .env
# Edit .env and add your GOOGLE_API_KEY
```

## Integration with Claude Desktop

### Configuration Steps

1. **Install the server:**
   ```bash
   pip install -e .
   ```

2. **Configure Claude Desktop:**
   
   Find your Claude Desktop configuration directory:
   - **macOS**: `~/Library/Application Support/Claude/`
   - **Windows**: `%APPDATA%/Claude/`
   - **Linux**: `~/.config/claude/`

3. **Create or edit `mcp_settings.json`:**
   ```json
   {
     "mcpServers": {
       "gemini-mcp-server": {
         "command": "gemini-mcp-server",
         "env": {
           "GOOGLE_API_KEY": "your-google-api-key-here"
         }
       }
     }
   }
   ```

4. **Restart Claude Desktop**

### Testing Claude Integration

Once configured, you can use these commands in Claude Desktop:

```
Generate an image of a sunset over mountains
```

```
Show me my image generation history
```

```
Check the status of my image generation queue
```

## Integration with opencode

### Configuration

Add the server to your MCP configuration (usually `mcp.json`):

```json
{
  "mcpServers": {
    "gemini-mcp-server": {
      "command": "gemini-mcp-server",
      "env": {
        "GOOGLE_API_KEY": "your-google-api-key-here"
      }
    }
  }
}
```

### Alternative: Python Module

If you prefer to run the server as a Python module:

```json
{
  "mcpServers": {
    "gemini-mcp-server": {
      "command": "python",
      "args": ["-m", "gemini_mcp_server.server"],
      "env": {
        "GOOGLE_API_KEY": "your-google-api-key-here"
      }
    }
  }
}
```

## Standalone Usage

```bash
# Start the server directly
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

### Environment Variables

Create a `.env` file (copy from `.env.template`):

```bash
# Required
GOOGLE_API_KEY=your_api_key_here

# Optional settings
LOG_LEVEL=INFO
MAX_REQUESTS_PER_MINUTE=15
IMAGE_OUTPUT_DIR=./generated_images
```

### Advanced Configuration

For more control, you can configure additional settings:

```bash
# Optional rate limiting
MAX_CONCURRENT_REQUESTS=3
```

## Development

### Setup

```bash
# Install development dependencies
pip install -e .[dev]
```

### Commands

#### Option 1: Direct Commands
```bash
# Quality checks
black src/ tests/ scripts/        # Format code
ruff check src/ tests/ scripts/   # Lint code
mypy src/                         # Type check

# Testing
pytest tests/ -v                  # Run all tests
pytest tests/ -v --cov=src --cov-report=html --cov-report=term  # Run with coverage

# All at once
black src/ tests/ scripts/ && ruff check src/ tests/ scripts/ && mypy src/ && pytest tests/ -v
```

#### Option 2: Using Just (Recommended)
Install [just](https://github.com/casey/just) command runner:

```bash
# Install just
cargo install just  # Or: brew install just, scoop install just

# See all available commands
just

# Common development tasks
just dev-setup      # Set up development environment
just quality         # Run all quality checks
just test           # Run tests
just dev            # Format + lint + test
just ci             # Full CI pipeline
just clean          # Clean artifacts
just serve          # Start development server
```

## Troubleshooting

### Common Issues

1. **"GOOGLE_API_KEY not found"**
   - Ensure your `.env` file contains `GOOGLE_API_KEY=your-key-here`
   - Verify the API key is valid at [Google AI Studio](https://makersuite.google.com/app/apikey)

2. **"Module not found"**
   - Run `pip install -e .` to install the package
   - Ensure you're in the correct directory

3. **"Rate limit exceeded"**
   - The free tier allows 15 requests per minute
   - Check queue status with `get_queue_status` tool

4. **Claude Desktop not detecting server**
   - Restart Claude Desktop after configuration
   - Check `mcp_settings.json` syntax is valid
   - Verify the server command is accessible

### Getting Help

- Check the [Issues](https://github.com/RouHim/gemini-mcp-server/issues) page
- Review logs for error messages
- Ensure all dependencies are installed

## License

MIT License - see LICENSE file for details.

## Links

- [Issues](https://github.com/RouHim/gemini-mcp-server/issues)
- [Model Context Protocol](https://github.com/modelcontextprotocol/python-sdk)
- [Google Gemini AI](https://deepmind.google/technologies/gemini/)
- [Claude Desktop](https://claude.ai/download)
- [opencode](https://github.com/sst/opencode)
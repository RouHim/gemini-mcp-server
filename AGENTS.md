# Agent Guidelines for Gemini MCP Server

## Commands
- **Test**: `just test`
- **Lint**: `just lint` 
- **Format**: `just format`
- **Type check**: `just typecheck`
- **Quality**: `just quality` (lint + typecheck)

## Code Style
- Use **Black** formatting (88 char line length)
- **Type hints required** for all functions (mypy strict mode)
- Use `async`/`await` for all I/O operations
- Error handling: catch specific exceptions, use logging for errors
- Use Pydantic models for data validation with Field descriptions
- Module structure: `/src/gemini_mcp_server/`

## Architecture
- **Queue-based processing** for rate limiting and request management
- **Modular design** with separate concerns (client, queue, rate limiter, retry handler)
- **Exponential backoff** retry strategy for API failures
- **Queue persistence** for request durability across restarts

## Testing
- Use **pytest** with async support (`pytest-asyncio`)
- **Mock external dependencies** (Google AI API calls)
- **Test both success and failure paths**
- Maintain **100% test coverage**

## Pipeline
- **Local testing**: `act` (GitHub Actions locally, requires Docker)
- **Quick checks**: `act -j validate` (lint, format, type check)
- **Jobs**: validate → test → build → deploy (main only)
- **Matrix**: Python 3.10-3.13, Ubuntu/Windows/macOS
- **Security**: Dependency scan, secret detection

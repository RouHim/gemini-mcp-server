# Agent Guidelines for Gemini MCP Server

## Build/Test Commands
- **Install deps**: `pip install -e .[dev]`
- **Run tests**: `pytest tests/` 
- **Single test**: `pytest tests/test_server.py::TestMCPServer::test_list_tools -v`
- **Lint**: `ruff check src/ tests/` 
- **Format**: `black src/ tests/`
- **Type check**: `mypy src/`
- **Coverage**: `pytest --cov=src tests/`

## Code Style
- Use **Black** formatting (88 char line length)
- Follow **Ruff** linting rules (comprehensive ruleset enabled)
- **Type hints required** for all functions (mypy strict mode)
- Import order: stdlib, third-party, local (sorted within groups)
- Use `async`/`await` for all I/O operations
- Error handling: catch specific exceptions, use logging for errors
- Naming: snake_case for functions/variables, PascalCase for classes
- Use Pydantic models for data validation with Field descriptions
- Add docstrings for classes and public methods (Google style)
- Module structure: `/src/gemini_mcp_server/` with `__init__.py` files

## Available MCP Tools
- **searxng**: Web search & article scraping (`searxng_search`, `searxng_scrape_article`)
- **fetch**: URL fetching (`fetch_fetch`)
- **context7**: Library documentation (`context7_resolve_library_id`, `context7_get_library_docs`)
- **memory-bank**: Project memory & progress tracking (`movibe-memory-bank_*`)
- **puppeteer**: Browser automation (`puppeteer_navigate`, `puppeteer_screenshot`, `puppeteer_click`)
- **github**: GitHub API operations (`github_create_repository`, `github_push_files`, etc.)

## Testing
- Use **pytest** with async support (`pytest-asyncio`)
- Test classes named `TestClassName`
- Mock external dependencies (Google AI API calls)
- Test both success and error paths
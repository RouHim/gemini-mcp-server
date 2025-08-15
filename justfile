# Gemini MCP Server - Just Commands
# Run `just` to see all available commands

# Default recipe - show help
default:
    @just --list

# Development setup
dev-setup:
    #!/usr/bin/env bash
    echo "🚀 Setting up development environment..."
    python -m venv .venv || true
    source .venv/bin/activate
    echo "📦 Installing dependencies..."
    pip install -e .[dev]
    echo "✅ Development environment ready!"
    echo "💡 Activate with: source .venv/bin/activate"

# Install package and dependencies
install:
    uv sync --dev

# Code formatting
format:
    uv run ruff format src/ tests/ scripts/

# Code linting
lint:
    uv run ruff check src/ tests/ scripts/

# Type checking
typecheck:
    uv run mypy src/

# Run all quality checks
quality: format lint typecheck

# Run tests
test:
    uv run pytest tests/ -v

# Run specific test
test-one TEST:
    uv run pytest tests/{{TEST}} -v

# Run unit tests only
test-unit:
    uv run pytest tests/ -v -m "unit"

# Run integration tests only
test-integration:
    uv run pytest tests/ -v -m "integration"

# Run tests with coverage
test-coverage:
    uv run pytest tests/ -v --cov=src --cov-report=html --cov-report=term

# Clean build artifacts
clean:
    #!/usr/bin/env bash
    rm -rf build/ dist/ *.egg-info/
    rm -rf .pytest_cache/ .coverage htmlcov/
    find . -type d -name __pycache__ -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete
    echo "🧹 Cleaned build artifacts"

# Build package
build: clean
    uv build --wheel --sdist

# Run all checks (CI pipeline)
ci: lint typecheck test-coverage

# Validate project setup
validate:
    uv run python scripts/validate.py

# Start development server
serve:
    uv run python -m gemini_mcp_server.server

# Start server with debug
debug:
    uv run python -m pdb -m gemini_mcp_server.server

# Test installation verification
test-install:
    uv run python test_installation.py

# Configure MCP for Claude Desktop
configure-claude:
    uv run python configure_mcp.py claude

# Configure MCP for opencode
configure-opencode:
    uv run python configure_mcp.py opencode

# Show project status
status:
    #!/usr/bin/env bash
    echo "📊 Project Status"
    echo "=================="
    echo "📁 Working directory: $(pwd)"
    echo "🐍 Python version: $(python --version)"
    echo "📦 Package installed: $(pip list | grep gemini-mcp-server || echo 'Not installed')"
    echo "🔧 Git status:"
    git status --short
    echo "📋 Recent commits:"
    git log --oneline -5

# Run security checks
security:
    #!/usr/bin/env bash
    echo "🔒 Running security checks..."
    pip-audit
    bandit -r src/

# Update dependencies
update-deps:
    #!/usr/bin/env bash
    echo "📦 Updating dependencies..."
    pip install --upgrade pip
    pip install --upgrade -e .[dev]
    pip list --outdated

# Run performance benchmarks
benchmark:
    #!/usr/bin/env bash
    echo "⚡ Running performance benchmarks..."
    python -m pytest tests/test_integration.py -v --benchmark-only

# Generate documentation
docs:
    #!/usr/bin/env bash
    echo "📚 Generating documentation..."
    mkdir -p docs/
    python -m pydoc -w src/gemini_mcp_server/
    mv *.html docs/ || true
    echo "📖 Documentation generated in docs/"

# Release preparation
pre-release: clean quality test build
    #!/usr/bin/env bash
    echo "🎉 Release preparation complete!"
    echo "📦 Package built and ready"
    echo "✅ All quality checks passed"
    echo "🚀 Ready for semantic-release"

# Database operations
db-reset:
    #!/usr/bin/env bash
    echo "🗄️ Resetting database..."
    rm -f queue_persistence.db
    echo "✅ Database reset complete"

# Show logs
logs:
    #!/usr/bin/env bash
    if [ -f gemini_mcp_server.log ]; then
        tail -f gemini_mcp_server.log
    else
        echo "📝 No log file found. Run the server first."
    fi

# Environment setup check
env-check:
    #!/usr/bin/env bash
    echo "🔍 Environment Check"
    echo "===================="
    echo "GOOGLE_API_KEY: $([ -n "$GOOGLE_API_KEY" ] && echo "✅ Set" || echo "❌ Not set")"
    echo "LOG_LEVEL: ${LOG_LEVEL:-INFO}"
    echo "MAX_REQUESTS_PER_MINUTE: ${MAX_REQUESTS_PER_MINUTE:-15}"
    echo "IMAGE_OUTPUT_DIR: ${IMAGE_OUTPUT_DIR:-./generated_images}"

# Docker operations (future enhancement)
docker-build:
    @echo "🐳 Docker support coming soon..."

docker-run:
    @echo "🐳 Docker support coming soon..."

# Quick development cycle
dev: format lint test
    @echo "🚀 Development cycle complete!"

# Watch files and run tests (requires entr)
watch:
    #!/usr/bin/env bash
    if command -v entr >/dev/null 2>&1; then
        find src/ tests/ -name "*.py" | entr -c just test
    else
        echo "❌ entr not found. Install with: brew install entr (macOS) or apt install entr (Ubuntu)"
    fi

# Profile performance
profile:
    #!/usr/bin/env bash
    echo "📊 Profiling server performance..."
    python -m cProfile -o profile.stats -m gemini_mcp_server.server &
    SERVER_PID=$!
    sleep 5
    kill $SERVER_PID
    python -c "import pstats; p = pstats.Stats('profile.stats'); p.sort_stats('cumulative').print_stats(20)"

# Check dependencies for updates
deps-check:
    pip list --outdated --format=columns

# Lint fix (auto-fix what's possible)
lint-fix:
    uv run ruff check src/ tests/ scripts/ --fix

# Format check (don't modify, just check)
format-check:
    uv run ruff format src/ tests/ scripts/ --check

# Full reset (clean + reinstall)
reset: clean
    pip uninstall -y gemini-mcp-server || true
    just install
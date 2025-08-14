# Makefile for Gemini MCP Server Development

.PHONY: help install test lint format typecheck clean build validate dev-setup all

# Default target
help: ## Show this help message
	@echo "Gemini MCP Server Development Commands"
	@echo "======================================"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Development setup
dev-setup: ## Set up development environment
	@echo "🚀 Setting up development environment..."
	python -m venv .venv || true
	@echo "📦 Installing dependencies..."
	.venv/bin/pip install -e .[dev]
	@echo "✅ Development environment ready!"
	@echo "💡 Activate with: source .venv/bin/activate"

install: ## Install package and dependencies
	pip install -e .[dev]

# Code quality
format: ## Format code with Black
	black src/ tests/ scripts/

lint: ## Lint code with Ruff
	ruff check src/ tests/ scripts/

typecheck: ## Type check with MyPy
	mypy src/

# Testing
test: ## Run all tests
	pytest tests/ -v

test-unit: ## Run unit tests only
	pytest tests/ -v -m "unit"

test-integration: ## Run integration tests only
	pytest tests/ -v -m "integration"

test-coverage: ## Run tests with coverage
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term

# Quality checks
quality: format lint typecheck ## Run all quality checks

validate: ## Validate project setup
	python scripts/validate.py

# Build and clean
build: ## Build package
	python -m build

clean: ## Clean build artifacts
	rm -rf build/ dist/ *.egg-info/
	rm -rf .pytest_cache/ .coverage htmlcov/
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

# All-in-one targets
all: quality test ## Run all quality checks and tests

ci: lint typecheck test-coverage ## Run CI pipeline locally

# Docker (future enhancement)
docker-build: ## Build Docker image
	@echo "🐳 Docker support coming soon..."

docker-run: ## Run in Docker container
	@echo "🐳 Docker support coming soon..."

# Release helpers
pre-release: clean quality test build ## Prepare for release
	@echo "🎉 Ready for release! Run semantic-release to publish."

# Development server
serve: ## Start development server
	python -m gemini_mcp_server.server

# Debugging
debug: ## Start server in debug mode
	PYTHONPATH=src python -m pdb -m gemini_mcp_server.server
#!/usr/bin/env python3
"""
Project validation script for Gemini MCP Server.
Checks project setup, dependencies, and basic functionality.
"""

import importlib.util
import subprocess
import sys
from pathlib import Path


def run_command(cmd: str, description: str) -> bool:
    """Run a command and return success status."""
    print(f"✓ {description}...")
    try:
        subprocess.run(cmd.split(), capture_output=True, text=True, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ✗ Failed: {e.stderr.strip()}")
        return False
    except FileNotFoundError:
        print(f"  ✗ Command not found: {cmd.split()[0]}")
        return False


def check_file_exists(path: str, description: str) -> bool:
    """Check if a file exists."""
    if Path(path).exists():
        print(f"✓ {description} exists")
        return True
    else:
        print(f"✗ {description} missing")
        return False


def check_import(module: str, description: str) -> bool:
    """Check if a module can be imported."""
    try:
        importlib.import_module(module)
        print(f"✓ {description} imports successfully")
        return True
    except ImportError as e:
        print(f"✗ {description} import failed: {e}")
        return False


def main():
    """Run all validation checks."""
    print("🚀 Validating Gemini MCP Server Project Setup\n")

    checks_passed = 0
    total_checks = 0

    # File structure checks
    files_to_check = [
        ("pyproject.toml", "Project configuration"),
        ("README.md", "Documentation"),
        ("src/gemini_mcp_server/__init__.py", "Main package"),
        ("src/gemini_mcp_server/server.py", "MCP server"),
        ("tests/conftest.py", "Test configuration"),
        (".github/workflows/ci.yml", "CI pipeline"),
        ("config/.env.example", "Environment template"),
    ]

    print("📁 Checking file structure...")
    for file_path, description in files_to_check:
        total_checks += 1
        if check_file_exists(file_path, description):
            checks_passed += 1

    # Import checks
    print("\n📦 Checking imports...")
    modules_to_check = [
        ("gemini_mcp_server", "Main package"),
        ("gemini_mcp_server.server", "MCP server"),
        ("gemini_mcp_server.gemini_client", "Gemini client"),
        ("gemini_mcp_server.queue_manager", "Queue manager"),
    ]

    for module, description in modules_to_check:
        total_checks += 1
        if check_import(module, description):
            checks_passed += 1

    # Command checks
    print("\n🔧 Checking development tools...")
    commands_to_check = [
        ("python --version", "Python installation"),
        ("pip --version", "Pip package manager"),
        ("black --version", "Black formatter"),
        ("ruff --version", "Ruff linter"),
        ("mypy --version", "MyPy type checker"),
        ("pytest --version", "Pytest test runner"),
    ]

    for cmd, description in commands_to_check:
        total_checks += 1
        if run_command(cmd, description):
            checks_passed += 1

    # Summary
    print("\n📊 Validation Summary:")
    print(f"   Passed: {checks_passed}/{total_checks} checks")

    if checks_passed == total_checks:
        print("   🎉 All checks passed! Project is ready for development.")
        return 0
    else:
        print(
            f"   ⚠️  {total_checks - checks_passed} checks failed. Please fix issues above."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())

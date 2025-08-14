#!/usr/bin/env python3

"""
Test script for Gemini MCP Server installation
"""

import sys
import os
import subprocess
import importlib.util
from pathlib import Path

def check_python_version():
    """Check if Python version is 3.10+"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print(f"❌ Python 3.10+ required, found {version.major}.{version.minor}")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    return True

def check_package_installed():
    """Check if gemini-mcp-server is installed"""
    try:
        import gemini_mcp_server
        print("✅ gemini-mcp-server package installed")
        return True
    except ImportError:
        print("❌ gemini-mcp-server package not found")
        return False

def check_console_script():
    """Check if console script is available"""
    try:
        result = subprocess.run(
            ["gemini-mcp-server", "--help"], 
            capture_output=True, 
            text=True, 
            timeout=5
        )
        if result.returncode == 0:
            print("✅ gemini-mcp-server command available")
            return True
        else:
            print("❌ gemini-mcp-server command failed")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("❌ gemini-mcp-server command not found")
        return False

def check_env_file():
    """Check if .env file exists"""
    env_path = Path(".env")
    if env_path.exists():
        print("✅ .env file exists")
        
        # Check if GOOGLE_API_KEY is set
        with open(env_path) as f:
            content = f.read()
            if "GOOGLE_API_KEY=" in content and "your-google-api-key-here" not in content:
                print("✅ GOOGLE_API_KEY appears to be configured")
                return True
            else:
                print("⚠️  GOOGLE_API_KEY needs to be set in .env file")
                return False
    else:
        print("❌ .env file not found")
        return False

def check_dependencies():
    """Check if key dependencies are available"""
    dependencies = [
        "mcp",
        "google.generativeai", 
        "aiohttp",
        "pydantic",
        "python_dotenv"
    ]
    
    all_good = True
    for dep in dependencies:
        try:
            if dep == "python_dotenv":
                import dotenv
            else:
                importlib.import_module(dep.replace(".", "_"))
            print(f"✅ {dep}")
        except ImportError:
            print(f"❌ {dep} not installed")
            all_good = False
    
    return all_good

def main():
    """Run all checks"""
    print("🧪 Testing Gemini MCP Server Installation\n")
    
    checks = [
        ("Python Version", check_python_version),
        ("Package Installation", check_package_installed), 
        ("Console Script", check_console_script),
        ("Environment File", check_env_file),
        ("Dependencies", check_dependencies),
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\n📋 {name}:")
        results.append(check_func())
    
    print(f"\n{'='*50}")
    if all(results):
        print("🎉 All checks passed! Installation looks good.")
        print("\nNext steps:")
        print("1. Ensure your GOOGLE_API_KEY is set in .env")
        print("2. Configure Claude Desktop or opencode")
        print("3. Start using: gemini-mcp-server")
    else:
        print("⚠️  Some checks failed. Please review the output above.")
        print("\nTo fix issues:")
        print("1. Run: pip install -e .")
        print("2. Copy .env.template to .env and configure")
        print("3. Add your GOOGLE_API_KEY")
    
    return all(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
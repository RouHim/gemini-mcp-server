#!/usr/bin/env python3

"""
MCP Configuration Helper for Gemini MCP Server
Helps configure Claude Desktop and other MCP clients
"""

import json
import os
import platform
import shutil
from pathlib import Path

def get_claude_desktop_config_dir():
    """Get Claude Desktop configuration directory based on platform"""
    system = platform.system().lower()
    
    if system == "darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / "Claude"
    elif system == "linux":
        return Path.home() / ".config" / "claude"
    elif system == "windows":
        return Path(os.environ.get("APPDATA", "")) / "Claude"
    else:
        return None

def create_mcp_config(config_dir, api_key=None):
    """Create MCP configuration for Claude Desktop"""
    config_file = config_dir / "mcp_settings.json"
    
    # Read existing config if it exists
    existing_config = {}
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                existing_config = json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️  Warning: Existing {config_file} is not valid JSON")
    
    # Ensure mcpServers section exists
    if "mcpServers" not in existing_config:
        existing_config["mcpServers"] = {}
    
    # Add or update gemini-mcp-server configuration
    gemini_config = {
        "command": "gemini-mcp-server",
        "env": {
            "GOOGLE_API_KEY": api_key or "your-google-api-key-here"
        }
    }
    
    existing_config["mcpServers"]["gemini-mcp-server"] = gemini_config
    
    # Create directory if it doesn't exist
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Write updated configuration
    with open(config_file, 'w') as f:
        json.dump(existing_config, f, indent=2)
    
    return config_file

def get_api_key_from_env():
    """Try to get API key from environment or .env file"""
    # Check environment variable first
    api_key = os.environ.get("GOOGLE_API_KEY")
    if api_key:
        return api_key
    
    # Check .env file
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith("GOOGLE_API_KEY=") and not line.endswith("your-google-api-key-here"):
                    return line.split("=", 1)[1].strip('"\'')
    
    return None

def main():
    """Main configuration function"""
    print("🔧 MCP Configuration Helper for Gemini MCP Server\n")
    
    # Get API key
    api_key = get_api_key_from_env()
    if api_key:
        print(f"✅ Found API key in environment")
    else:
        print("⚠️  No API key found. Please set GOOGLE_API_KEY in .env file")
    
    # Check if gemini-mcp-server command is available
    if shutil.which("gemini-mcp-server"):
        print("✅ gemini-mcp-server command is available")
    else:
        print("❌ gemini-mcp-server command not found. Run: pip install -e .")
        return False
    
    # Try to configure Claude Desktop
    claude_config_dir = get_claude_desktop_config_dir()
    if claude_config_dir:
        print(f"\n📁 Claude Desktop config directory: {claude_config_dir}")
        
        if claude_config_dir.exists():
            print("✅ Claude Desktop directory found")
            
            try:
                config_file = create_mcp_config(claude_config_dir, api_key)
                print(f"✅ MCP configuration updated: {config_file}")
                
                if not api_key:
                    print("⚠️  Remember to update the GOOGLE_API_KEY in the configuration")
                
                print("\n🎉 Claude Desktop configuration complete!")
                print("Please restart Claude Desktop for changes to take effect.")
                
            except Exception as e:
                print(f"❌ Failed to create configuration: {e}")
                return False
        else:
            print("⚠️  Claude Desktop directory not found")
            print("Please install Claude Desktop first, or create the configuration manually")
    else:
        print(f"❌ Unsupported platform: {platform.system()}")
    
    # Show example configurations
    print(f"\n📋 Example MCP Configurations:")
    
    print("\n1. Claude Desktop (mcp_settings.json):")
    example_config = {
        "mcpServers": {
            "gemini-mcp-server": {
                "command": "gemini-mcp-server",
                "env": {
                    "GOOGLE_API_KEY": "your-google-api-key-here"
                }
            }
        }
    }
    print(json.dumps(example_config, indent=2))
    
    print("\n2. opencode (mcp.json):")
    opencode_config = {
        "mcpServers": {
            "gemini-mcp-server": {
                "command": "gemini-mcp-server",
                "env": {
                    "GOOGLE_API_KEY": "your-google-api-key-here"
                }
            }
        }
    }
    print(json.dumps(opencode_config, indent=2))
    
    print("\n3. Alternative using Python module:")
    python_config = {
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
    print(json.dumps(python_config, indent=2))
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
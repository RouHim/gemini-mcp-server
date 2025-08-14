#!/bin/bash

# Gemini MCP Server Installation Script
# This script helps set up the Gemini MCP Server for use with Claude Desktop and opencode

set -e

echo "🚀 Setting up Gemini MCP Server..."

# Check if Python 3.10+ is available
python_version=$(python3 --version 2>&1 | sed 's/.* \([0-9]\)\.\([0-9]*\).*/\1\2/')
if [ "$python_version" -lt "310" ]; then
    echo "❌ Python 3.10 or higher is required. Current version: $(python3 --version)"
    exit 1
fi
echo "✅ Python version check passed"

# Install the package
echo "📦 Installing gemini-mcp-server..."
pip install -e .

# Create environment file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📄 Creating .env file from template..."
    cp .env.template .env
    echo "⚠️  Please edit .env and add your GOOGLE_API_KEY"
    echo "   Get your API key at: https://makersuite.google.com/app/apikey"
else
    echo "✅ .env file already exists"
fi

# Check if MCP configuration directory exists
MCP_CONFIG_DIR=""
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    MCP_CONFIG_DIR="$HOME/Library/Application Support/Claude"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    MCP_CONFIG_DIR="$HOME/.config/claude"
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    # Windows
    MCP_CONFIG_DIR="$APPDATA/Claude"
fi

if [ -n "$MCP_CONFIG_DIR" ] && [ -d "$MCP_CONFIG_DIR" ]; then
    echo "📁 Found Claude Desktop configuration directory: $MCP_CONFIG_DIR"
    
    if [ ! -f "$MCP_CONFIG_DIR/mcp_settings.json" ]; then
        echo "📝 Creating MCP configuration..."
        mkdir -p "$MCP_CONFIG_DIR"
        cp mcp.json.example "$MCP_CONFIG_DIR/mcp_settings.json"
        echo "⚠️  Please edit $MCP_CONFIG_DIR/mcp_settings.json and add your GOOGLE_API_KEY"
    else
        echo "📋 MCP configuration already exists at $MCP_CONFIG_DIR/mcp_settings.json"
        echo "   You can manually add the gemini-mcp-server configuration from mcp.json.example"
    fi
else
    echo "📋 Claude Desktop not found. You can manually configure MCP using mcp.json.example"
fi

echo ""
echo "🎉 Installation complete!"
echo ""
echo "Next steps:"
echo "1. Add your GOOGLE_API_KEY to .env file"
echo "2. If using Claude Desktop, restart the application"
echo "3. If using opencode, add the server to your MCP configuration"
echo ""
echo "Available commands:"
echo "  gemini-mcp-server          - Start the MCP server"
echo "  python test_installation.py - Test your installation"
echo "  python configure_mcp.py     - Configure MCP clients"
echo ""
echo "For help, see: README.md"
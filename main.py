#!/usr/bin/env python3

"""
Entry point for the Gemini MCP Server.
"""

import asyncio
import sys
from pathlib import Path

# Add the src directory to the Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from gemini_mcp_server.server import main

if __name__ == "__main__":
    asyncio.run(main())
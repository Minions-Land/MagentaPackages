#!/usr/bin/env python3
"""Launcher for cardio-api MCP server.

This script sets up sys.path so cardio_api_server can be imported, then runs it.
It's invoked from the Cardiomni/cardio-api.toml descriptor.
"""
import sys
from pathlib import Path

# Add the python/ directory (one level up from this script, then into python/) to sys.path
# This script lives at tools/cardio-api/Cardiomni/run_cardio_api_server.py
# We need tools/cardio-api/python/
script_dir = Path(__file__).parent  # tools/cardio-api/Cardiomni/
parent_dir = script_dir.parent       # tools/cardio-api/
python_dir = parent_dir / "python"   # tools/cardio-api/python/
sys.path.insert(0, str(python_dir))

# Now we can import and run the server
import asyncio
from cardio_api_server.server import main

if __name__ == "__main__":
    asyncio.run(main())

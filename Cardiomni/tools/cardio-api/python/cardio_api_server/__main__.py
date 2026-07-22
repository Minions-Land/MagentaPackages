"""Entry point for running the cardio-api MCP server."""

import asyncio
from .server import main as server_main


if __name__ == "__main__":
    asyncio.run(server_main())

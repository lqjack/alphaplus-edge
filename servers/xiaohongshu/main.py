from asyncio import run
from asyncio.exceptions import CancelledError
from contextlib import suppress
from sys import argv
import os
import sys
# Configure logging using centralized logger
from core.loggerimport setup_logger
logger = setup_logger("mcp-server-xiaohongshu")
from source import Settings
from source import XHS
from source import XHSDownloader
from source import cli


# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    # Use logger if available, otherwise print
    if 'logger' in locals() or 'logger' in globals():
        sys.stderr.write(f"Added project root to Python path: {project_root}\n")


    else:
        sys.stderr.write(f"Added project root to Python path: {project_root}\n")



async def app():
    async with XHSDownloader() as xhs:
        await xhs.run_async()


async def api_server(
    host="0.0.0.0",
    port=5556,
    log_level="info",
):
    async with XHS(**Settings().run()) as xhs:
        await xhs.run_api_server(
            host,
            port,
            log_level,
        )


async def mcp_server(
    transport="stdio",
    host="0.0.0.0",
    port=5556,
    log_level="INFO",
):
    async with XHS(**Settings().run()) as xhs:
        await xhs.run_mcp_server(
            transport=transport,
            host=host,
            port=port,
            log_level=log_level,
        )


if __name__ == "__main__":
    with suppress(
        KeyboardInterrupt,
        CancelledError,
    ):
        if len(argv) > 1:
          if argv[1].upper() == "CLI":
              cli()
          elif argv[1].upper() == "MCP":
              run(mcp_server())
              # run(mcp_server("stdio"))
          elif argv[1].upper() == "APP":
              run(app())
          elif argv[1].upper() == "API":
            run(api_server())
        else:
            run(mcp_server())
            

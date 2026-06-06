# -*- coding: utf-8 -*-
"""OpenCLI Weixin MCP Server — WeChat Official Account via jackwener/OpenCLI."""

import sys
from pathlib import Path

current_dir = Path(__file__).parent.absolute()
servers_dir = current_dir.parent
src_dir = servers_dir.parent
project_root = src_dir.parent
for path in [str(current_dir), str(servers_dir), str(src_dir), str(project_root)]:
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    from core.service_ports import get_port

    DEFAULT_PORT = get_port("opencli_weixin", "mcp")
except ImportError:
    DEFAULT_PORT = 10488

from handlers.tool_handler import OpenCLIWeixinToolHandler
from shared.mcp_base import create_server

server = create_server("opencli_weixin", tool_handler_class=OpenCLIWeixinToolHandler)

if __name__ == "__main__":
    server.run()

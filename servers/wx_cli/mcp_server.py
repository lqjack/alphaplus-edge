# -*- coding: utf-8 -*-
"""wx-cli MCP Server — personal WeChat local data via jackwener/wx-cli."""

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

    DEFAULT_PORT = get_port("wx_cli", "mcp")
except ImportError:
    DEFAULT_PORT = 10478

from handlers.tool_handler import WxCliToolHandler
from shared.mcp_base import create_server

server = create_server("wx_cli", tool_handler_class=WxCliToolHandler)

if __name__ == "__main__":
    server.run()

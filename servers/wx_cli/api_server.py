# -*- coding: utf-8 -*-
"""wx-cli REST API Server — DataproAI / llm-gateway invoke via /api/tools/call."""

import sys
from pathlib import Path

current_dir = Path(__file__).parent.absolute()
servers_dir = current_dir.parent
src_dir = servers_dir.parent
project_root = src_dir.parent
for path in [str(current_dir), str(servers_dir), str(src_dir), str(project_root)]:
    if path not in sys.path:
        sys.path.insert(0, path)

from core.service_ports import get_port
from handlers.tool_handler import WxCliToolHandler
from shared.api_base import BaseAPIServer


class WxCliAPIServer(BaseAPIServer):
    def __init__(self):
        super().__init__("wx_cli", get_port("wx_cli", "api"))
        self._init_components()

    def _init_components(self):
        try:
            self.tool_handler = WxCliToolHandler()
            self._logger.info("wx_cli API components initialized")
        except Exception as exc:
            self._logger.error("Failed to init wx_cli handler: %s", exc)
            self.tool_handler = None


server = WxCliAPIServer()

if __name__ == "__main__":
    server.run()

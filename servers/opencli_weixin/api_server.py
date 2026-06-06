# -*- coding: utf-8 -*-
"""OpenCLI Weixin REST API — DataproAI / llm-gateway invoke via /api/tools/call."""

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
from handlers.tool_handler import OpenCLIWeixinToolHandler
from shared.api_base import BaseAPIServer


class OpenCLIWeixinAPIServer(BaseAPIServer):
    def __init__(self):
        super().__init__("opencli_weixin", get_port("opencli_weixin", "api"))
        self._init_components()

    def _init_components(self):
        try:
            self.tool_handler = OpenCLIWeixinToolHandler()
            self._logger.info("opencli_weixin API components initialized")
        except Exception as exc:
            self._logger.error("Failed to init opencli_weixin handler: %s", exc)
            self.tool_handler = None


server = OpenCLIWeixinAPIServer()

if __name__ == "__main__":
    server.run()

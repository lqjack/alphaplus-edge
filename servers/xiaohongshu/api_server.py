# -*- coding: utf-8 -*-
"""
Xiaohongshu API Server
Provides an HTTP/REST interface for Xiaohongshu operations.

Updated to use unified BaseAPIServer for proper event loop management.
"""

import sys
import os
import asyncio
import logging
from flask import Flask, request, jsonify

os.environ.setdefault("IS_MCP_SERVER", "true")

# Setup environment - match youtube_viewer pattern for sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_src = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
project_root = os.path.dirname(project_src)

# Add paths to sys.path - order matters (most specific first)
server_local = current_dir
servers_dir = os.path.dirname(current_dir)
src_dir = os.path.dirname(servers_dir)
for path in [
    server_local,
    servers_dir,
    src_dir,
    project_src,
    project_root,
]:
    if path not in sys.path:
        sys.path.insert(0, path)

from core.service_ports import get_port
from deps.manager import get_dependency_manager
from mcp_api.client import XiaohongshuAPIClient
from handlers.tool_handler import XiaohongshuToolHandler

# Import unified base class
from shared.api_base import BaseAPIServer


class XiaohongshuAPIServer(BaseAPIServer):
    """Xiaohongshu API Server using unified base class"""

    def __init__(self):
        super().__init__("xiaohongshu", get_port("xiaohongshu", "api"))

        self.dep_manager = None
        self.api_client = None
        self._init_dependencies()
        self._init_tool_handler()

    def _init_dependencies(self):
        try:
            self.dep_manager = get_dependency_manager()
            loop = self.get_loop()
            if asyncio.iscoroutinefunction(self.dep_manager.initialize_all):
                loop.run_until_complete(self.dep_manager.initialize_all())
            else:
                self.dep_manager.initialize_all()
            self._logger.info("Xiaohongshu dependencies initialized")
        except Exception as e:
            self._logger.error(f"Failed to initialize: {e}")

    def _init_tool_handler(self):
        try:
            self.api_client = XiaohongshuAPIClient(self.dep_manager)
            self.tool_handler = XiaohongshuToolHandler(
                self.dep_manager, self.api_client
            )
            self._logger.info("Xiaohongshu tool handler initialized")
        except Exception as e:
            self._logger.error(f"Failed to init handler: {e}")
            self.tool_handler = None


app = None


def create_app():
    global app
    server = XiaohongshuAPIServer()
    app = server.app
    return app


if __name__ == "__main__":
    server = XiaohongshuAPIServer()
    server.run()

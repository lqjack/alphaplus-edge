# -*- coding: utf-8 -*-
"""
WeChat Viewer API Server - Flask Implementation

Updated to use unified BaseAPIServer for proper event loop management.
"""

import sys
import os
import logging
import asyncio
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS

os.environ.setdefault("IS_MCP_SERVER", "true")

# Setup environment
current_dir = Path(__file__).parent.absolute()
project_src = current_dir.parent.parent.parent  # dataproai/
project_root = project_src.parent  # DataProAI/

# Add paths to sys.path - order matters (most specific first)
server_local = current_dir
servers_dir = current_dir.parent
src_dir = servers_dir.parent
for path in [
    str(server_local),
    str(servers_dir),
    str(src_dir),
    str(project_src),
    str(project_root),
]:
    if path not in sys.path:
        sys.path.insert(0, path)

from core.service_ports import get_port
from deps.manager import get_dependency_manager
from handlers.server_handler import WeChatViewerServerHandler
from shared.api_base import BaseAPIServer
from shared.opencli_weixin_handler import OpenCLIWeixinToolHandler

USE_OPENCLI_BACKEND = os.environ.get("WECHAT_VIEWER_BACKEND", "opencli").strip().lower() in {
    "opencli",
    "1",
    "true",
    "yes",
    "on",
}


class WeChatViewerAPIServer(BaseAPIServer):
    """WeChat Viewer API Server using unified base class"""

    def __init__(self):
        self.ocr_processor = None
        self.automation = None
        self.server_handler = None

        # Initialize with port from centralized config
        super().__init__("wechat_viewer", get_port("wechat_viewer", "api"))

        # Initialize components after base class
        self._init_components()

    def _init_components(self):
        """Initialize all components"""
        try:
            self._logger.info("Initializing WeChat Viewer API components...")

            if USE_OPENCLI_BACKEND:
                self._logger.info("Using OpenCLI backend (WECHAT_VIEWER_BACKEND=opencli)")
                self.dep_manager = get_dependency_manager()
                self.ocr_processor = None
                self.automation = None
                self.tool_handler = OpenCLIWeixinToolHandler(self.dep_manager)
                self.server_handler = WeChatViewerServerHandler(self.tool_handler)
                self._logger.info("OpenCLI Weixin handler initialized")
                return

            from ocr.ocr_processor import OCRProcessor
            from automation.wechat_automation import WeChatAutomation
            from handlers.tool_handler import WeChatViewerToolHandler

            # Initialize dependency manager
            self.dep_manager = get_dependency_manager()
            self._logger.info("WeChat Viewer dependency manager created")
            loop = self.get_loop()
            if asyncio.iscoroutinefunction(self.dep_manager.initialize_all):
                self._logger.info("Initializing WeChat Viewer dependencies asynchronously")
                loop.run_until_complete(self.dep_manager.initialize_all())
            else:
                self._logger.info("Initializing WeChat Viewer dependencies synchronously")
                self.dep_manager.initialize_all()
            self._logger.info("WeChat Viewer dependencies initialized")

            # Initialize OCR processor
            self._logger.info("Initializing WeChat Viewer OCR processor")
            self.ocr_processor = OCRProcessor(self.dep_manager)
            self._logger.info("WeChat Viewer OCR processor initialized")

            # Initialize WeChat automation with the LLM client pulled from
            # the dependency manager so llm_element_locator is actually wired
            # up instead of silently falling to llm_element_locator=None.
            self._logger.info("Resolving WeChat Viewer LLM client dependency")
            llm_client = self.dep_manager.get_dependency("llm_chain")
            if llm_client is None:
                self._logger.warning(
                    "LLM client not available from dependency manager; article reading will be degraded"
                )
            else:
                self._logger.info("WeChat Viewer LLM client dependency resolved")
            self._logger.info("Initializing WeChatAutomation")
            self.automation = WeChatAutomation(
                dep_manager=self.dep_manager,
                ocr_processor=self.ocr_processor,
                llm_client=llm_client,
            )
            self._logger.info("WeChatAutomation initialized")

            # Initialize handlers
            self._logger.info("Initializing WeChatViewerToolHandler")
            self.tool_handler = WeChatViewerToolHandler(
                self.dep_manager, self.automation
            )
            self._logger.info("WeChatViewerToolHandler initialized")
            self._logger.info("Initializing WeChatViewerServerHandler")
            self.server_handler = WeChatViewerServerHandler(self.tool_handler)
            self._logger.info("WeChatViewerServerHandler initialized")

            self._logger.info("WeChat Viewer API Components Initialized")
        except Exception as e:
            self._logger.error(f"Failed to initialize components: {e}", exc_info=True)
            self.tool_handler = None
            self.server_handler = None

    def _health(self):
        payload = {
            "status": "ok",
            "service": self.name,
            "port": self.port,
            "backend": "opencli" if USE_OPENCLI_BACKEND else "legacy",
        }
        if self.automation:
            try:
                ax_status = self.automation.get_accessibility_status()
                payload["accessibility"] = {
                    "accessibility_available": bool(ax_status.get("accessibility_available")),
                    "native_ax_trusted": bool(ax_status.get("native_ax_trusted")),
                    "system_events_accessible": bool(ax_status.get("system_events_accessible")),
                    "system_events_ui_enabled": bool(ax_status.get("system_events_ui_enabled")),
                    "assistive_access_denied": bool(ax_status.get("assistive_access_denied")),
                    "recommended_backend": ax_status.get("recommended_backend"),
                }
            except Exception as exc:
                payload["accessibility_error"] = str(exc)
        return jsonify(payload)


# Logging setup
# Ensure logs directory exists at root
root_dir = project_root
log_file = os.path.join(str(root_dir), "logs", "wechat_viewer.log")
os.makedirs(os.path.dirname(log_file), exist_ok=True)

log_handlers = [logging.FileHandler(log_file, encoding='utf-8')]
if os.getenv("WECHAT_VIEWER_STDERR_LOG", "").strip().lower() in {"1", "true", "yes", "on"}:
    log_handlers.insert(0, logging.StreamHandler())

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=log_handlers,
    force=True,
)
log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)

# Create server instance
server = WeChatViewerAPIServer()


# Create Flask app for compatibility
def create_app():
    """Create and configure Flask app"""
    return server.app


if __name__ == "__main__":
    server.run()

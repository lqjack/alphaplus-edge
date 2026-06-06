# -*- coding: utf-8 -*-
"""
Xiaohongshu MCP Server
Port: 10351

使用 shared/mcp_base + deps_compat 迁移
迁移日期: 2026-03-18
"""

import sys
import os
from pathlib import Path

current_dir = Path(__file__).parent.absolute()
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# 添加父目录以便导入
parent_dir = current_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# 尝试导入 deps.manager，失败时使用兼容版本
try:
    from deps.manager import get_dependency_manager
except ImportError:
    from shared.deps_compat import get_dependency_manager

# 尝试导入端口配置
try:
    from core.service_ports import get_port
    DEFAULT_PORT = get_port("xiaohongshu", "mcp")
except ImportError:
    DEFAULT_PORT = 10351

# 尝试导入处理器
try:
    from handlers.tool_handler import XiaohongshuToolHandler
    HAS_TOOL_HANDLER = True
except ImportError:
    HAS_TOOL_HANDLER = False

try:
    from handlers.mcp_handler import XiaohongshuMCPHandler
    HAS_MCP_HANDLER = True
except ImportError:
    HAS_MCP_HANDLER = False

# 使用 shared/mcp_base
from shared.mcp_base import BaseMCPServer


class XiaohongshuMCPServer(BaseMCPServer):
    """Xiaohongshu MCP Server"""
    
    def __init__(self):
        super().__init__("xiaohongshu", DEFAULT_PORT)
        self._init_handler()
    
    def _init_handler(self):
        """初始化处理器"""
        try:
            dep_manager = get_dependency_manager()
            if HAS_TOOL_HANDLER:
                api_client = None
                try:
                    from mcp_api.client import XiaohongshuAPIClient
                    api_client = XiaohongshuAPIClient(dep_manager)
                except Exception as api_exc:
                    self._logger.warning("Xiaohongshu API client skipped: %s", api_exc)
                self.tool_handler = XiaohongshuToolHandler(dep_manager, api_client)
                backend = "opencli" if os.environ.get("XIAOHONGSHU_BACKEND", "opencli").lower() in (
                    "opencli", "1", "true", "yes"
                ) else "legacy"
                self._logger.info("Xiaohongshu Tool Handler initialized (backend=%s)", backend)
            elif HAS_MCP_HANDLER:
                self.mcp_handler = XiaohongshuMCPHandler(dep_manager)
                self._logger.info("Xiaohongshu MCP Handler initialized")
        except Exception as e:
            self._logger.error(f"Failed to init handler: {e}")


server = XiaohongshuMCPServer()

if __name__ == "__main__":
    server.run()

"""
微信观看者MCP服务器
Port: 10497

使用 shared/mcp_base + deps_compat 迁移
迁移日期: 2026-03-20
"""
import sys
import os
from pathlib import Path

# 添加公共目录到Python路径
common_dir = Path(__file__).parent.parent / "common"
if str(common_dir) not in sys.path:
    sys.path.insert(0, str(common_dir))

# 添加当前目录到Python路径
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
    DEFAULT_PORT = get_port("wechat_viewer", "mcp")
except ImportError:
    # Fallback to the correct port for wechat_viewer mcp
    DEFAULT_PORT = 10471

# 导入基础MCP服务器
from common.mcp_server_base import WebAutomationMCPServer


class WechatViewerMCPServer(WebAutomationMCPServer):
    """微信观看者MCP服务器"""

    def __init__(self):
        super().__init__("wechat_viewer", DEFAULT_PORT)


server = WechatViewerMCPServer()

if __name__ == "__main__":
    server.run()
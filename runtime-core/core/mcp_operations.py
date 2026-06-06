import asyncio
import logging
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from core.server_client import get_mcp_manager, get_plugin_manager

logger = logging.getLogger(__name__)

class MCPOperations:
    """MCP Operations - handles MCP server startup and calling with connection reuse"""

    def __init__(self):
        # Force re-initialization of MCP manager to ensure it uses registered config
        global _mcp_manager_instance
        _mcp_manager_instance = None
        self.mcp_manager = get_mcp_manager()
        self.cline_config = self._load_cline_config()
        self._register_servers_from_cline_config()

    def _load_cline_config(self):
        """从 Cline 配置文件加载 MCP 服务器配置"""
        config_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))) / 'cline_mcp_settings.json'
        if not config_path.exists():
            logger.warning("Cline 配置文件不存在: {}".format(config_path))
            return {}

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logger.info("成功加载 Cline MCP 配置，共 {} 个服务器".format(len(config.get('mcpServers', {}))))
                return config
        except Exception as e:
            logger.error("加载 Cline 配置失败: {}".format(e))
            return {}

    def _register_servers_from_cline_config(self):
        """从 Cline 配置注册 MCP 服务器，并验证文件存在性"""
        mcp_servers = self.cline_config.get('mcpServers', {})

        for server_name, server_config in mcp_servers.items():
            if server_config.get('disabled', False):
                logger.info("跳过已禁用的服务器: {}".format(server_name))
                continue

            # 验证服务器文件是否存在
            if not self._validate_server_config(server_config):
                logger.warning("跳过无效配置的服务器: {} (文件不存在)".format(server_name))
                continue

            try:
                # Import here to avoid circular import
                try:
                    from api.mcp.client import MCPServerConfig
                except ImportError:
                    class MCPServerConfig:
                        def __init__(self, name, command, args, env=None, enabled=True, description=""):
                            self.name = name
                            self.command = command
                            self.args = args
                            self.env = env or {}
                            self.enabled = enabled
                            self.description = description

                config = MCPServerConfig(
                    name=server_name,
                    command=server_config['command'],
                    args=server_config['args'],
                    env=server_config.get('env', {}),
                    enabled=not server_config.get('disabled', False),
                    description="MCP Server: {}".format(server_name)
                )
                self.mcp_manager.register_server({
                    'name': config.name,
                    'command': config.command,
                    'args': config.args,
                    'env': config.env,
                    'enabled': config.enabled,
                    'description': config.description
                })
                logger.info("已注册 MCP 服务器: {}".format(server_name))
            except Exception as e:
                logger.error("注册服务器 {} 失败: {}".format(server_name, e))

    def _validate_server_config(self, server_config):
        """验证服务器配置的有效性"""
        try:
            # 检查命令是否存在
            command = server_config.get('command')
            if not command or not os.path.exists(command):
                # 如果是 uv 命令，检查是否在 PATH 中
                if command and 'uv' in command:
                    # uv 命令可能在 PATH 中，跳过检查
                    pass
                else:
                    logger.warning("命令不存在: {}".format(command))
                    return False

            # 检查服务器目录和入口文件
            args = server_config.get('args', [])
            if len(args) >= 3 and args[0] == 'run' and args[1] == '--directory':
                server_dir = args[2]
                entry_file = args[3] if len(args) > 3 else 'mcp_server.py'

                server_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), server_dir.replace("{}/".format(os.path.dirname(os.path.dirname(__file__))), ""))
                entry_path = os.path.join(server_path, entry_file)

                if not os.path.exists(server_path):
                    # logger.warning("服务器目录不存在: {}".format(server_path))
                    return False

                if not os.path.exists(entry_path):
                    # logger.warning("服务器入口文件不存在: {}".format(entry_path))
                    return False

            return True

        except Exception as e:
            logger.error("验证服务器配置失败: {}".format(e))
            return False

    async def connect_server(self, server_name, timeout=60.0 * 3):
        """连接单个 MCP 服务"""
        return await self.mcp_manager.connect_server(server_name, timeout=timeout)

    async def call_tool(self, server_name, tool_name, arguments):
        """调用 MCP 工具 - 使用连接复用"""
        try:
            # 如果是远程 API 模式，使用 API 服务器名称
            # 例如: ai -> ai_api, wechat -> wechat_api
            actual_server_name = self._resolve_server_name(server_name)

            # 首先检查是否已连接，如果未连接则连接
            if not self.mcp_manager.is_connected(actual_server_name):
                logger.info(f"Connecting to server {actual_server_name} (alias: {server_name}) for tool {tool_name}")
                await self.mcp_manager.connect_server(actual_server_name, timeout=30.0)

            # 使用现有的连接调用工具
            result = await self.mcp_manager.call_tool(actual_server_name, tool_name, arguments)
            import json
            try:
                result_str = json.dumps(result, ensure_ascii=False, default=str)
                logger.info(f"MCP tool {tool_name} on {actual_server_name} completed, result: {result_str}")
            except:
                logger.info(f"MCP tool {tool_name} on {actual_server_name} completed, result type: {type(result)}")
            return result
        except Exception as e:
            logger.error(f"Failed to call tool {tool_name} on {server_name}: {e}")
            # 如果调用失败，不使用 close()，而是直接重新连接特定服务器
            try:
                actual_server_name = self._resolve_server_name(server_name)
                await self.mcp_manager.connect_server(actual_server_name, timeout=30.0)
                result = await self.mcp_manager.call_tool(actual_server_name, tool_name, arguments)
                logger.info(f"Tool {tool_name} on {actual_server_name} completed after reconnection")
                return result
            except Exception as retry_error:
                logger.error(f"Failed to call tool {tool_name} on {server_name} after retry: {retry_error}")
                raise

    def _resolve_server_name(self, server_name: str) -> str:
        """
        解析服务器名称，处理远程 API 模式的映射

        支持两种配置方式：
        1. MCP_{SERVICE}_API_URL: 创建 {service}_api 插件（使用 HTTP REST）
        2. MCP_{SERVICE}_URL: 创建 {service} 插件（使用 SSE）

        命名约定：
        - 插件名可以是: service, service_mcp, service_api 等
        - 远程 API 模式通过环境变量 MCP_{SERVICE}_API_URL 激活

        逻辑：
        1. 检查是否有远程 API 配置 (MCP_{SERVICE}_API_URL)
        2. 如果有，返回 {service}_api（需要提前在配置中注册）
        3. 否则，检查已注册的服务器，找到匹配的（service_mcp 或 service）
        """
        # 获取所有已注册的服务器
        registered_servers = self.mcp_manager.get_registered_servers()

        # 检查环境变量中是否有远程 API 配置
        # 格式: MCP_{SERVICE_NAME}_API_URL=http://host:port
        api_env_var = f"MCP_{server_name.upper()}_API_URL"
        api_remote_url = os.getenv(api_env_var)

        # 如果配置了远程 API URL，优先使用 API 服务器
        if api_remote_url:
            api_server_name = f"{server_name}_api"
            # 检查 API 服务器是否已注册
            if api_server_name in registered_servers:
                logger.info(f"检测到远程 API 配置: {api_env_var}={api_remote_url}，使用服务器: {api_server_name}")
                return api_server_name
            else:
                logger.warning(f"环境变量 {api_env_var} 已设置，但服务器 {api_server_name} 未注册")

        # 检查 SSE 远程配置（备用）
        sse_env_var = f"MCP_{server_name.upper()}_URL"
        sse_remote_url = os.getenv(sse_env_var)

        if sse_remote_url:
            # SSE 模式使用原始服务器名
            logger.info(f"检测到 SSE 远程配置: {sse_env_var}={sse_remote_url}，使用服务器: {server_name}")
            return server_name

        # 检查已注册的服务器，优先查找 *_mcp 后缀的
        mcp_server_name = f"{server_name}_mcp"
        if mcp_server_name in registered_servers:
            logger.debug(f"使用 stdio 服务器 (本地): {mcp_server_name}")
            return mcp_server_name

        # 检查原始服务器名
        if server_name in registered_servers:
            logger.debug(f"使用已注册服务器: {server_name}")
            return server_name

        # 如果都没有，返回原始名称（让后续调用处理错误）
        logger.warning(f"未找到服务器 {server_name}、{server_name}_mcp 或 {server_name}_api，返回原始名称")
        return server_name

    async def initialize_mcp(self):
        """初始化 MCP 连接"""
        logger.info("初始化 MCP 服务器连接...")

        registered_servers = self.mcp_manager.get_registered_servers()
        logger.info("已注册的服务器: {}".format(registered_servers))

        success_count = 0
        total_count = len(registered_servers)

        # 如果没有服务器通过 MCP 连接，尝试基本连接性测试
        basic_success = await self._test_basic_server_startup()
        if basic_success > 0:
            logger.info("基本启动测试通过: {}/{} 个服务器可启动".format(basic_success, total_count))
            return True

        return success_count > 0

    async def _test_basic_server_startup(self) -> int:
        """测试基本服务器启动功能（不依赖 MCP 协议）"""
        logger.info("开始基本服务器启动测试...")

        registered_servers = self.mcp_manager.get_registered_servers()
        success_count = 0

        for server_name in registered_servers:
            try:
                logger.info(f"测试启动服务器: {server_name}")

                # 直接尝试连接服务器
                connected = await self.connect_server(server_name, timeout=10.0)
                if connected:
                    success_count += 1
                    logger.info("✓ {} 连接成功".format(server_name))
                else:
                    logger.warning("⚠ {} 连接失败".format(server_name))

            except Exception as e:
                error_msg = str(e)
                logger.error("✗ {} 启动测试失败: {}".format(server_name, error_msg))

        logger.info("基本启动测试完成: {}/{} 个服务器可启动".format(success_count, len(registered_servers)))
        return success_count

    def get_registered_servers(self):
        """获取已注册的服务列表"""
        return self.mcp_manager.get_registered_servers()

    def is_connected(self, server_name):
        """检查服务器是否已连接"""
        return self.mcp_manager.is_connected(server_name)

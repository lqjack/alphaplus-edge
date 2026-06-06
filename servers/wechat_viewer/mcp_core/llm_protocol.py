"""
LLM Protocol

Defines the protocol for LLM clients to ensure consistent interface across different AI services.
Based on MCP tool handler patterns for WeChat automation.
支持通过 MCP 调用 AI chat_completion 功能。

NOTE: This module now imports core LLM implementations from core.llm for consistency.
The legacy local implementations are kept for backward compatibility but delegate to core.llm.

Visual protocol layering:
- `computer_use_grounding`: primary single-target grounding contract
- `legacy_visual_fallback`: explicit compatibility path for older multimodal tasks
- `analyze_screenshot`: backward-compatible alias only

架构设计：
- LLMClientProtocol: LLM 客户端协议接口 (from core.llm)
- BaseLLMClient: LLM 客户端基类（共享逻辑）(from core.llm)
- MCPBasedLLMClient: 基于 MCP 的 LLM 客户端实现 (from core.llm)
- WeChatViewerLLMClient: WeChat Viewer 专用客户端
- ScreenshotOptimizer: 截图优化器（共享模块）
- LLMResponseParser: 响应解析器（共享模块）
"""

import sys
import json
import logging
from typing import Protocol, Dict, Any, Optional, Union, List
from dataclasses import dataclass
from enum import Enum

# Try importing from core.llm (new shared module)
try:
    from core.llm.base import BaseLLMClient as _CoreBaseLLMClient
    from core.llm.base import LLMClientProtocol as _CoreLLMClientProtocol
    from core.llm.mcp_client import MCPBasedLLMClient as _CoreMCPBasedLLMClient

    CORE_LLM_AVAILABLE = True
except ImportError:
    CORE_LLM_AVAILABLE = False

# Import ServiceGateway for centralized AI service calls
try:
    from core.service.gateway import get_service_gateway, ServiceGateway
    GATEWAY_AVAILABLE = True
except ImportError:
    GATEWAY_AVAILABLE = False
    get_service_gateway = None
    ServiceGateway = None

# Import from local automation modules
try:
    from automation.screenshot_optimizer import ScreenshotOptimizer, ScreenshotInfo
    from automation.llm_response_parser import LLMResponseParser, get_response_parser
except ImportError:
    ScreenshotOptimizer = None
    ScreenshotInfo = None
    LLMResponseParser = None
    get_response_parser = None

# Use loguru if available, fallback to logging
try:
    from loguru import logger
except ImportError:
    logger = logging.getLogger(__name__)

# Import MCP types for tool definitions (optional - may not be available in all environments)
try:
    import mcp.types as types
except ImportError:
    types = None


# Re-export from core.llm if available, otherwise define locally
if CORE_LLM_AVAILABLE:
    LLMClientProtocol = _CoreLLMClientProtocol
    BaseLLMClient = _CoreBaseLLMClient
    MCPBasedLLMClient = _CoreMCPBasedLLMClient
else:
    # Fallback: Define local Protocol (simplified)
    class LLMClientProtocol(Protocol):
        """LLM客户端协议，定义MCP调用接口"""

        async def analyze(self, prompt: str) -> str:
            """通过MCP协议调用AI MCP Server进行分析"""
            ...

        async def chat(self, messages: List[Dict[str, Any]], **kwargs) -> Any:
            """通过MCP协议进行对话"""
            ...

        async def generate_response(self, prompt: str, **kwargs) -> str:
            """生成响应"""
            ...

        async def analyze_screenshot(
            self, prompt: str, screenshot_b64: str
        ) -> Optional[Union[Dict[str, Any], List[Any], str]]:
            """旧截图分析别名；新代码应优先使用 legacy_visual_fallback。"""
            ...

        async def legacy_visual_fallback(
            self, prompt: str, screenshot_b64: str
        ) -> Optional[Union[Dict[str, Any], List[Any], str]]:
            """兼容旧多模态截图分析协议的显式 fallback 入口。"""
            ...

        async def computer_use_grounding(
            self,
            target: str,
            screenshot_b64: str,
            region: Optional[Dict[str, Any]] = None,
            ui_context: Optional[Dict[str, Any]] = None,
            allowed_actions: Optional[List[str]] = None,
            request_next_action: bool = True,
        ) -> Optional[Dict[str, Any]]:
            """使用结构化桌面 grounding 协议定位元素。"""
            ...

    # Fallback BaseLLMClient
    class BaseLLMClient:
        def __init__(self, logger_instance=None):
            self.logger = logger_instance or logger
            self.response_parser = None

        def _parse_response(self, content):
            if self.response_parser:
                return self.response_parser.parse(content)
            return str(content) if content else ""

        async def analyze(self, prompt: str) -> str:
            raise NotImplementedError()

        async def chat(self, messages, **kwargs):
            raise NotImplementedError()

    # Fallback MCPBasedLLMClient
    class MCPBasedLLMClient(BaseLLMClient):
        def __init__(self, mcp_server_name="ai"):
            super().__init__(logger)
            self.mcp_server_name = mcp_server_name
            # Defer MCPOperations import
            self._mcp_ops = None

        @property
        def mcp_ops(self):
            if self._mcp_ops is None:
                from core.mcp_operations import MCPOperations

                self._mcp_ops = MCPOperations()
            return self._mcp_ops

        async def chat(self, messages, **kwargs):
            raise NotImplementedError("MCP operations not available")


@dataclass
class LLMToolResult:
    """LLM工具执行结果"""

    success: bool
    result: Optional[Dict[str, Any]]
    error: Optional[str] = None
    execution_time: float = 0.0


class BaseLLMClient:
    """
    LLM 客户端基类

    包含共享的响应解析逻辑，可被其他 LLM 客户端继承
    """

    def __init__(self, logger_instance: Optional[logging.Logger] = None):
        """初始化基类"""
        self.logger = logger_instance or logger
        # 使用共享的响应解析器
        self.response_parser = get_response_parser(self.logger)

    def _parse_response(
        self, content: Any
    ) -> Optional[Union[Dict[str, Any], List[Any], str]]:
        """解析响应（使用共享解析器）"""
        return self.response_parser.parse(content)

    async def analyze(self, prompt: str) -> str:
        """通过LLM进行分析（需子类实现）"""
        raise NotImplementedError("子类必须实现 analyze 方法")

    async def chat(self, messages: List[Dict[str, Any]], **kwargs) -> Any:
        """通过LLM进行对话（需子类实现）"""
        raise NotImplementedError("子类必须实现 chat 方法")

    async def generate_response(self, prompt: str, **kwargs) -> str:
        """生成响应"""
        return await self.analyze(prompt)

    async def computer_use_grounding(
        self,
        target: str,
        screenshot_b64: str,
        region: Optional[Dict[str, Any]] = None,
        ui_context: Optional[Dict[str, Any]] = None,
        allowed_actions: Optional[List[str]] = None,
        request_next_action: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """结构化桌面元素定位（需子类实现）。"""
        raise NotImplementedError("子类必须实现 computer_use_grounding 方法")


class MCPBasedLLMClient(BaseLLMClient):
    """基于 MCP 的 LLM 客户端实现"""

    def __init__(self, mcp_server_name: str = "ai"):
        """
        初始化基于 MCP 的 LLM 客户端
        """
        super().__init__(logger)  # 调用基类初始化
        self.mcp_server_name = mcp_server_name
        self._mcp_ops = None
        self.logger.info(f"MCP LLM 客户端初始化完成，服务器: {mcp_server_name}")

        # Ensure AI calls use the gateway if not explicitly configured otherwise
        import os
        env_var = f"MCP_{mcp_server_name.upper()}_API_URL"
        if not os.getenv(env_var) and not os.getenv(f"MCP_{mcp_server_name.upper()}_URL"):
            try:
                from core.service_ports import get_port

                gateway_base = os.getenv(
                    "GATEWAY_URL",
                    f"http://localhost:{get_port('gateway', 'api')}",
                )
            except Exception:
                gateway_base = os.getenv("GATEWAY_URL", "http://localhost:8001")
            gateway_url = f"{gateway_base.rstrip('/')}/ai/"
            os.environ[env_var] = gateway_url
            self.logger.info(f"Automatically configured {mcp_server_name} to use Gateway: {gateway_url}")

        # 初始化截图优化器
        self.screenshot_optimizer = ScreenshotOptimizer(logger=self.logger)

    @property
    def mcp_ops(self):
        """延迟加载 MCPOperations"""
        if self._mcp_ops is None:
            try:
                from core.mcp_operations import MCPOperations
                self._mcp_ops = MCPOperations()
            except ImportError:
                self.logger.error("无法加载 core.mcp_operations")
                return None
        return self._mcp_ops

    async def chat(self, messages: List[Dict[str, Any]], **kwargs) -> Any:
        """通过 MCP 协议进行对话，返回原始结果供解析"""
        try:
            # 构建 chat_completion 工具参数
            arguments = {"messages": messages}

            # 添加可选参数
            if "max_tokens" in kwargs:
                arguments["max_tokens"] = kwargs["max_tokens"]
            if "temperature" in kwargs:
                arguments["temperature"] = kwargs["temperature"]

            self.logger.info(
                f"通过 MCP 调用 {self.mcp_server_name} 服务器的 chat_completion 工具"
            )

            # 调用工具
            result = await self.mcp_ops.call_tool(
                self.mcp_server_name, "chat_completion", arguments
            )
            return result

        except Exception as e:
            self.logger.error(f"MCP LLM 对话调用失败: {e}")
            return None

    async def analyze(self, prompt: str) -> str:
        """通过 MCP 协议进行文本分析"""
        messages = [{"role": "user", "content": prompt}]
        result = await self.chat(messages)
        parsed = self._parse_response(result)
        return str(parsed) if parsed is not None else ""

    async def analyze_screenshot(
        self, prompt: str, screenshot_b64: str
    ) -> Optional[Union[Dict[str, Any], List[Any], str]]:
        """Backward-compatible alias for legacy_visual_fallback."""
        return await self.legacy_visual_fallback(prompt, screenshot_b64)

    async def legacy_visual_fallback(
        self, prompt: str, screenshot_b64: str
    ) -> Optional[Union[Dict[str, Any], List[Any], str]]:
        """发送截图给 LLM 进行旧协议视觉分析并解析结果。"""
        try:
            # 使用截图优化器压缩截图，获取截图信息（包含缩放比例）
            optimized_b64, screenshot_info = self.screenshot_optimizer.optimize(
                screenshot_b64
            )

            # 保存截图信息供后续坐标转换使用
            self._last_screenshot_info = screenshot_info

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{optimized_b64}"
                            },
                        },
                    ],
                }
            ]

            self.logger.info(f"发送优化后的截图给 LLM 进行多模态分析...")
            response = await self.chat(messages)

            if response is None:
                return None

            # DEBUG: 添加日志显示原始响应
            import json

            try:
                response_str = json.dumps(response, ensure_ascii=False, default=str)[
                    :1000
                ]
                self.logger.info(f"LLM 原始响应: {response_str}")
            except:
                self.logger.info(
                    f"LLM 原始响应 (无法序列化): {type(response)}, {response}"
                )

            parsed_result = self._parse_response(response)
            self.logger.info(f"解析后结果: {parsed_result}")
            return parsed_result
        except Exception as e:
            self.logger.error(f"legacy_visual_fallback 失败: {e}")
            return None

    async def computer_use_grounding(
        self,
        target: str,
        screenshot_b64: str,
        region: Optional[Dict[str, Any]] = None,
        ui_context: Optional[Dict[str, Any]] = None,
        allowed_actions: Optional[List[str]] = None,
        request_next_action: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """通过 AI MCP 工具执行结构化桌面视觉定位。"""
        try:
            optimized_b64, screenshot_info = self.screenshot_optimizer.optimize(
                screenshot_b64
            )
            self._last_screenshot_info = screenshot_info
            arguments = {
                "target": target,
                "screenshot_b64": optimized_b64,
                "region": region,
                "ui_context": ui_context,
                "allowed_actions": allowed_actions,
                "request_next_action": request_next_action,
            }
            result = await self.mcp_ops.call_tool(
                self.mcp_server_name,
                "computer_use_grounding",
                arguments,
            )
            parsed = self._parse_response(result)
            if isinstance(parsed, dict) and isinstance(parsed.get("result"), dict):
                parsed = parsed["result"]
            return parsed if isinstance(parsed, dict) else None
        except Exception as e:
            self.logger.error(f"computer_use_grounding 失败: {e}")
            return None

    def get_last_screenshot_info(self) -> Optional[ScreenshotInfo]:
        """获取最后处理的截图信息"""
        return getattr(self, "_last_screenshot_info", None)


class LLMToolHandler:
    """LLM工具处理器，基于tool_handler.py模式实现"""

    def __init__(self, llm_client: Optional[LLMClientProtocol] = None):
        self.llm_client = llm_client
        self.tools = self._define_wechat_tools()

    def _define_wechat_tools(self) -> Dict[str, Dict[str, Any]]:
        """定义WeChat相关的MCP工具"""
        return {
            "analyze_wechat_ui": {
                "name": "analyze_wechat_ui",
                "description": "Analyze WeChat UI state and provide decision recommendations",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "ui_state": {
                            "type": "object",
                            "description": "Current UI state from OCR and window analysis",
                        },
                        "task_description": {
                            "type": "string",
                            "description": "Description of the current automation task",
                        },
                        "available_actions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of available actions for the current state",
                        },
                    },
                    "required": ["ui_state", "task_description", "available_actions"],
                },
            },
            "generate_automation_plan": {
                "name": "generate_automation_plan",
                "description": "Generate a step-by-step automation plan for WeChat tasks",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target_account": {
                            "type": "string",
                            "description": "Target WeChat account to search for",
                        },
                        "task_type": {
                            "type": "string",
                            "enum": [
                                "search_account",
                                "read_articles",
                                "monitor_updates",
                            ],
                            "description": "Type of automation task",
                        },
                        "constraints": {
                            "type": "object",
                            "description": "Constraints and preferences for the automation",
                        },
                    },
                    "required": ["target_account", "task_type"],
                },
            },
            "validate_automation_step": {
                "name": "validate_automation_step",
                "description": "Validate if an automation step is correct and suggest improvements",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "step_description": {
                            "type": "string",
                            "description": "Description of the automation step",
                        },
                        "current_state": {
                            "type": "object",
                            "description": "Current state of the automation",
                        },
                        "expected_outcome": {
                            "type": "string",
                            "description": "Expected outcome of the step",
                        },
                    },
                    "required": [
                        "step_description",
                        "current_state",
                        "expected_outcome",
                    ],
                },
            },
            "optimize_automation_strategy": {
                "name": "optimize_automation_strategy",
                "description": "Optimize automation strategy based on performance metrics",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "performance_metrics": {
                            "type": "object",
                            "description": "Performance metrics from previous automation runs",
                        },
                        "failure_patterns": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Common failure patterns observed",
                        },
                        "success_rate": {
                            "type": "number",
                            "description": "Current success rate of automation",
                        },
                    },
                    "required": [
                        "performance_metrics",
                        "failure_patterns",
                        "success_rate",
                    ],
                },
            },
            "generate_error_recovery": {
                "name": "generate_error_recovery",
                "description": "Generate error recovery strategies for failed automation steps",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "error_description": {
                            "type": "string",
                            "description": "Description of the error that occurred",
                        },
                        "failed_step": {
                            "type": "string",
                            "description": "The step that failed",
                        },
                        "current_state": {
                            "type": "object",
                            "description": "Current state after the failure",
                        },
                    },
                    "required": ["error_description", "failed_step", "current_state"],
                },
            },
        }

    def get_tool_definitions(self) -> List[Any]:
        """获取MCP工具定义"""
        if types is None:
            return []
        return [
            types.Tool(
                name=tool_def["name"],
                description=tool_def["description"],
                inputSchema=tool_def["inputSchema"],
            )
            for tool_def in self.tools.values()
        ]

    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """执行工具调用"""
        logger.info(f"执行工具: {name} 参数: {arguments}")

        try:
            if name == "analyze_wechat_ui":
                return await self._handle_analyze_wechat_ui(arguments)
            elif name == "generate_automation_plan":
                return await self._handle_generate_automation_plan(arguments)
            elif name == "validate_automation_step":
                return await self._handle_validate_automation_step(arguments)
            elif name == "optimize_automation_strategy":
                return await self._handle_optimize_automation_strategy(arguments)
            elif name == "generate_error_recovery":
                return await self._handle_generate_error_recovery(arguments)
            else:
                raise ValueError(f"未知工具: {name}")
        except Exception as e:
            logger.error(f"工具执行失败: {name} - {e}")
            return {"error": str(e), "tool": name}

    async def _handle_analyze_wechat_ui(
        self, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理WeChat UI分析工具"""
        ui_state = arguments.get("ui_state", {})
        task_description = arguments.get("task_description", "")
        available_actions = arguments.get("available_actions", [])

        if not ui_state or not task_description:
            raise ValueError("UI状态和任务描述是必需的")

        # 使用LLM分析UI状态并提供决策建议
        prompt = f"""
        请分析当前WeChat界面状态并提供决策建议：

        任务描述: {task_description}
        当前UI状态: {json.dumps(ui_state, ensure_ascii=False)}
        可用操作: {", ".join(available_actions)}

        请提供：
        1. 当前界面状态分析
        2. 推荐的下一步操作
        3. 操作的置信度评估
        4. 可能的风险和注意事项
        """

        if self.llm_client:
            analysis = await self.llm_client.analyze(prompt)
        else:
            analysis = "LLM客户端不可用，使用默认分析"

        return {
            "analysis": analysis,
            "recommendations": available_actions[:3],
            "confidence": 0.8,
            "status": "success",
        }

    async def _handle_generate_automation_plan(
        self, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理自动化计划生成工具"""
        target_account = arguments.get("target_account", "")
        task_type = arguments.get("task_type", "search_account")
        constraints = arguments.get("constraints", {})

        if not target_account:
            raise ValueError("目标账户是必需的")

        plan = {
            "target_account": target_account,
            "task_type": task_type,
            "steps": [],
            "estimated_time": "2-5分钟",
            "success_criteria": [],
        }

        if task_type == "search_account":
            plan["steps"] = [
                "1. 激活WeChat窗口",
                "2. 定位并点击搜索框",
                "3. 输入账户名称",
                "4. 等待搜索结果",
                "5. 识别并点击目标账户",
                "6. 验证账户页面打开",
            ]
            plan["success_criteria"] = [
                "成功找到目标账户",
                "账户页面正常打开",
                "能够看到账户信息",
            ]
        elif task_type == "read_articles":
            plan["steps"] = [
                "1. 搜索并打开目标账户",
                "2. 定位文章列表",
                "3. 识别最新文章",
                "4. 点击阅读文章",
                "5. 提取文章内容",
                "6. 保存或分析内容",
            ]
            plan["success_criteria"] = ["成功打开文章", "文章内容可读", "完成内容提取"]

        return {"plan": plan, "constraints": constraints, "status": "success"}

    async def _handle_validate_automation_step(
        self, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理自动化步骤验证工具"""
        step_description = arguments.get("step_description", "")
        current_state = arguments.get("current_state", {})
        expected_outcome = arguments.get("expected_outcome", "")

        if not step_description or not expected_outcome:
            raise ValueError("步骤描述和期望结果是必需的")

        validation = {
            "step_description": step_description,
            "current_state": current_state,
            "expected_outcome": expected_outcome,
            "validity_score": 0.85,
            "issues": [],
            "improvements": [],
        }

        if "点击" in step_description and "坐标" not in step_description:
            validation["issues"].append("缺少具体的点击坐标信息")
            validation["improvements"].append("建议提供精确的点击坐标")

        if "等待" in step_description and "时间" not in step_description:
            validation["issues"].append("缺少等待时间说明")
            validation["improvements"].append("建议指定具体的等待时间")

        return {"validation": validation, "status": "success"}

    async def _handle_optimize_automation_strategy(
        self, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理自动化策略优化工具"""
        performance_metrics = arguments.get("performance_metrics", {})
        failure_patterns = arguments.get("failure_patterns", [])
        success_rate = arguments.get("success_rate", 0.0)

        optimization = {
            "current_success_rate": success_rate,
            "failure_patterns": failure_patterns,
            "performance_metrics": performance_metrics,
            "optimization_suggestions": [],
            "priority_actions": [],
        }

        if "OCR识别失败" in failure_patterns:
            optimization["optimization_suggestions"].append(
                "改进OCR识别算法，增加容错机制"
            )
            optimization["priority_actions"].append("优化图像预处理")

        if "点击坐标偏移" in failure_patterns:
            optimization["optimization_suggestions"].append("增加坐标校准机制")
            optimization["priority_actions"].append("实现动态坐标计算")

        if success_rate < 0.7:
            optimization["optimization_suggestions"].append(
                "整体成功率较低，建议全面优化"
            )
            optimization["priority_actions"].append("重新评估自动化策略")

        return {"optimization": optimization, "status": "success"}

    async def _handle_generate_error_recovery(
        self, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理错误恢复生成工具"""
        error_description = arguments.get("error_description", "")
        failed_step = arguments.get("failed_step", "")
        current_state = arguments.get("current_state", {})

        if not error_description or not failed_step:
            raise ValueError("错误描述和失败步骤是必需的")

        recovery = {
            "error_description": error_description,
            "failed_step": failed_step,
            "current_state": current_state,
            "recovery_strategies": [],
            "alternative_approaches": [],
            "restart_points": [],
        }

        if "网络超时" in error_description:
            recovery["recovery_strategies"].append("增加超时重试机制")
            recovery["alternative_approaches"].append("使用本地缓存数据")
            recovery["restart_points"].append("重新连接网络后重试")

        if "元素未找到" in error_description:
            recovery["recovery_strategies"].append("增加元素等待和重试")
            recovery["alternative_approaches"].append("使用多种定位方式")
            recovery["restart_points"].append("重新加载页面后重试")

        if "权限不足" in error_description:
            recovery["recovery_strategies"].append("检查权限设置")
            recovery["alternative_approaches"].append("使用管理员权限运行")
            recovery["restart_points"].append("重新配置权限后重试")

        return {"recovery": recovery, "status": "success"}


class WeChatViewerLLMClient(BaseLLMClient):
    """WeChat Viewer LLM 客户端 - 提供完整的 MCP 集成"""

    def __init__(self, mcp_server_name: str = "ai"):
        """
        初始化 WeChat Viewer LLM 客户端

        Args:
            mcp_server_name: MCP 服务器名称，默认为 "ai"
        """
        # 调用基类初始化
        super().__init__(logger)

        # 内部 MCP 客户端
        self._mcp_client = MCPBasedLLMClient(mcp_server_name)
        self.tool_handler = LLMToolHandler(self._mcp_client)
        self.logger.info("WeChat Viewer LLM 客户端初始化完成")

        # 截图优化器
        self.screenshot_optimizer = self._mcp_client.screenshot_optimizer

    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """通过 MCP 协议进行对话"""
        return await self._mcp_client.chat(messages, **kwargs)

    async def analyze(self, prompt: str) -> str:
        """通过 MCP 协议调用 AI MCP Server 进行分析"""
        messages = [{"role": "user", "content": prompt}]
        result = await self.chat(messages)
        parsed = self._parse_response(result)
        return str(parsed) if parsed is not None else ""

    async def analyze_screenshot(
        self, prompt: str, screenshot_b64: str
    ) -> Optional[Union[Dict[str, Any], List[Any], str]]:
        """Backward-compatible alias for legacy_visual_fallback."""
        return await self.legacy_visual_fallback(prompt, screenshot_b64)

    async def legacy_visual_fallback(
        self, prompt: str, screenshot_b64: str
    ) -> Optional[Union[Dict[str, Any], List[Any], str]]:
        """发送旧协议截图分析 fallback 请求。"""
        return await self._mcp_client.legacy_visual_fallback(prompt, screenshot_b64)

    async def computer_use_grounding(
        self,
        target: str,
        screenshot_b64: str,
        region: Optional[Dict[str, Any]] = None,
        ui_context: Optional[Dict[str, Any]] = None,
        allowed_actions: Optional[List[str]] = None,
        request_next_action: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """发送结构化桌面元素定位请求。"""
        return await self._mcp_client.computer_use_grounding(
            target=target,
            screenshot_b64=screenshot_b64,
            region=region,
            ui_context=ui_context,
            allowed_actions=allowed_actions,
            request_next_action=request_next_action,
        )

    def get_last_screenshot_info(self) -> Optional[ScreenshotInfo]:
        """获取最后处理的截图信息"""
        return self._mcp_client.get_last_screenshot_info()

    async def get_tools(self) -> List[Dict[str, Any]]:
        """获取可用工具列表"""
        tool_definitions = self.tool_handler.get_tool_definitions()
        tools = []
        for tool in tool_definitions:
            tools.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.inputSchema,
                }
            )
        return tools

    async def execute_tool(
        self, name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行特定工具"""
        return await self.tool_handler.execute_tool(name, arguments)


class LLMProtocolFactory:
    """LLM 协议工厂类，提供便捷的客户端创建方法"""

    @staticmethod
    def create_mcp_llm_client(mcp_server_name: str = "ai") -> MCPBasedLLMClient:
        """创建基于 MCP 的 LLM 客户端"""
        return MCPBasedLLMClient(mcp_server_name)

    @staticmethod
    def create_wechat_viewer_llm_client(
        mcp_server_name: str = "ai",
    ) -> WeChatViewerLLMClient:
        """创建 WeChat Viewer LLM 客户端"""
        return WeChatViewerLLMClient(mcp_server_name)

    @staticmethod
    def create_decision_engine_with_llm(
        mcp_server_name: str = "ai", config: Dict[str, Any] = None
    ):
        """创建带有 LLM 客户端的决策引擎"""
        if config is None:
            config = {}

        try:
            from .decision_engine import DecisionEngineFactory

            llm_client = WeChatViewerLLMClient(mcp_server_name)
            return DecisionEngineFactory.create_decision_engine(llm_client, config)
        except ImportError:
            logger.error("无法导入决策引擎模块")
            return None
        except Exception as e:
            logger.error(f"创建决策引擎失败: {e}")
            return None

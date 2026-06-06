"""
Decision Engine Core

Handles AI decision-making and intelligent task execution using LLM integration.
整合了 llm_protocol.py 中的 LLMClientProtocol 定义。
"""
import logging
import json
from typing import Dict, Any, Optional, List, Protocol, Union
from abc import ABC, abstractmethod

# 导入统一的 LLM 协议定义
from .llm_protocol import LLMClientProtocol, WeChatViewerLLMClient, MCPBasedLLMClient


class DecisionEngine(ABC):
    """Abstract base class for decision engines"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger("mcp-server-wechat-viewer-mcp.decision_engine")
    
    @abstractmethod
    async def analyze_and_decide(self, ui_state, target_mission):
        """Analyze current state and make decisions"""
        pass
    
    @abstractmethod
    def _construct_decision_prompt(self, ui_state, target_mission) -> str:
        """Construct decision prompt"""
        pass
    
    @abstractmethod
    def _parse_llm_response(self, llm_response: str):
        """Parse LLM response"""
        pass


class MCPDecisionEngine(DecisionEngine):
    """Decision engine that uses MCP protocol for LLM integration"""
    
    def __init__(self, llm_client: Union[LLMClientProtocol, WeChatViewerLLMClient, MCPBasedLLMClient], config: Dict[str, Any]):
        super().__init__(config)
        self.llm_client = llm_client
    
    async def analyze_and_decide(self, ui_state, target_mission):
        """通过MCP协议调用AI MCP Server分析当前界面并决定下一步操作"""
        try:
            # 构造决策提示词
            prompt = self._construct_decision_prompt(ui_state, target_mission)
            
            # 通过MCP协议调用AI MCP Server
            llm_response = await self.llm_client.analyze(prompt)
            
            # 解析AI MCP Server响应
            decision = self._parse_llm_response(llm_response)
            
            return decision
            
        except Exception as e:
            self.logger.error(f"AI决策失败: {e}")
            return self._get_fallback_decision()
    
    def _construct_decision_prompt(self, ui_state, target_mission) -> str:
        """构造决策提示词"""
        prompt_template = """
你是一个微信自动化助手。请根据当前界面状态分析下一步应该执行什么操作。

当前任务目标: {mission_target}
当前界面状态: {ui_description}
检测到的UI元素: {ui_elements}

可用的操作类型:
1. click_search - 点击搜索框
2. input_text - 输入文本
3. click_element - 点击特定元素
4. scroll - 滚动页面
5. wait - 等待加载
6. finish - 任务完成

请以JSON格式回复，例如:
{{
    "action": "click_element",
    "target": "搜索框",
    "confidence": 0.9,
    "reason": "需要先点击搜索框才能进行搜索",
    "position_hint": "top_left" // 可选的位置提示
}}

请分析并决定下一步操作:
"""
        ui_elements_str = ", ".join([f"{e['text']}({e['type']})" for e in ui_state["ui_elements"][:10]])
        
        return prompt_template.format(
            mission_target=target_mission,
            ui_description=ui_state["state_description"],
            ui_elements=ui_elements_str
        )
    
    def _parse_llm_response(self, llm_response: str):
        """解析AI MCP Server响应"""
        try:
            # 尝试解析JSON响应
            decision = json.loads(llm_response)
            return decision
        except:
            # 如果JSON解析失败，返回默认决策
            return {
                "action": "wait",
                "target": "",
                "confidence": 0.5,
                "reason": "AI响应解析失败，使用默认等待操作",
                "position_hint": ""
            }
    
    def _get_fallback_decision(self):
        """获取备用决策"""
        return {
            "action": "wait",
            "target": "",
            "confidence": 0.5,
            "reason": "备用决策：等待",
            "position_hint": ""
        }


class RuleBasedDecisionEngine(DecisionEngine):
    """基于规则的决策引擎，用于备用决策"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
    
    async def analyze_and_decide(self, ui_state, target_mission):
        """基于规则的决策"""
        try:
            # 简单的规则引擎
            ui_elements = ui_state.get("ui_elements", [])
            
            # 检查是否有搜索框
            search_widgets = [e for e in ui_elements if e["type"] == "search_widget"]
            if search_widgets:
                return {
                    "action": "click_search",
                    "target": "搜索框",
                    "confidence": 0.8,
                    "reason": "检测到搜索框，应该点击",
                    "position_hint": "top"
                }
            
            # 检查是否有公众号
            account_elements = [e for e in ui_elements if e["type"] == "account_element"]
            if account_elements:
                return {
                    "action": "click_element",
                    "target": account_elements[0]["text"],
                    "confidence": 0.7,
                    "reason": "检测到公众号，应该点击",
                    "position_hint": "center"
                }
            
            # 检查是否有内容元素
            content_elements = [e for e in ui_elements if e["type"] == "content_element"]
            if content_elements:
                return {
                    "action": "click_element",
                    "target": content_elements[0]["text"],
                    "confidence": 0.6,
                    "reason": "检测到内容元素，应该点击",
                    "position_hint": "center"
                }
            
            # 默认等待
            return {
                "action": "wait",
                "target": "",
                "confidence": 0.5,
                "reason": "没有检测到明确的操作目标，等待",
                "position_hint": ""
            }
            
        except Exception as e:
            self.logger.error(f"规则决策失败: {e}")
            return self._get_fallback_decision()
    
    def _construct_decision_prompt(self, ui_state, target_mission) -> str:
        """规则引擎不需要构造提示词"""
        return ""
    
    def _parse_llm_response(self, llm_response: str):
        """规则引擎不需要解析LLM响应"""
        return None
    
    def _get_fallback_decision(self):
        """获取备用决策"""
        return {
            "action": "wait",
            "target": "",
            "confidence": 0.5,
            "reason": "备用决策：等待",
            "position_hint": ""
        }


class DecisionEngineFactory:
    """Factory for creating decision engines"""
    
    @staticmethod
    def create_decision_engine(llm_client: Optional[Union[LLMClientProtocol, WeChatViewerLLMClient, MCPBasedLLMClient]], config: Dict[str, Any]):
        """Create appropriate decision engine based on availability of LLM client"""
        if llm_client:
            return MCPDecisionEngine(llm_client, config)
        else:
            return RuleBasedDecisionEngine(config)
    
    @staticmethod
    def create_mcp_decision_engine(mcp_server_name: str = "ai", config: Dict[str, Any] = None):
        """Create MCP-based decision engine with automatic LLM client initialization"""
        if config is None:
            config = {}
        
        try:
            # 创建 MCP LLM 客户端
            llm_client = WeChatViewerLLMClient(mcp_server_name)
            return MCPDecisionEngine(llm_client, config)
        except Exception as e:
            logging.getLogger("mcp-server-wechat-viewer-mcp.decision_engine").error(f"创建 MCP 决策引擎失败: {e}")
            return RuleBasedDecisionEngine(config)

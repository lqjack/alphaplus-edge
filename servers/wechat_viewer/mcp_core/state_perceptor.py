"""
State Perceptor Core

Handles intelligent state perception and UI element analysis for automation.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime


class StatePerceptor:
    """Intelligent state perception for GUI automation"""
    
    def __init__(self, ocr_processor, dep_manager):
        self.ocr_processor = ocr_processor
        self.dep_manager = dep_manager
        self.logger = logging.getLogger("mcp-server-wechat-viewer-mcp.perceptor")
    
    async def get_current_ui_state(self, bounds) -> Optional[Dict[str, Any]]:
        """获取当前界面状态的多维度信息"""
        try:
            # 1. 全屏截图
            screenshot = self.ocr_processor.capture_screenshot(bounds)
            if not screenshot:
                return None
            
            # 2. OCR识别界面文字
            ocr_results = self.ocr_processor.recognize_text(screenshot)
            
            # 3. 提取关键UI元素
            ui_elements = self._extract_ui_elements(ocr_results, bounds)
            
            # 4. 生成界面状态描述
            state_description = self._generate_state_description(ui_elements)
            
            return {
                "screenshot": screenshot,
                "ocr_results": ocr_results,
                "ui_elements": ui_elements,
                "state_description": state_description,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"获取界面状态失败: {e}")
            return None
    
    def _extract_ui_elements(self, ocr_results: str, bounds) -> List[Dict[str, Any]]:
        """从OCR结果中提取关键UI元素"""
        elements = []
        
        # 简化的元素提取逻辑
        if ocr_results:
            # 按行分割OCR结果
            lines = ocr_results.split('\n')
            for line in lines:
                if line.strip():
                    element = {
                        "text": line.strip(),
                        "position": {"x": 0, "y": 0, "width": 100, "height": 20},  # 简化位置
                        "confidence": 80,  # 简化置信度
                        "type": self._classify_element_type(line.strip())
                    }
                    elements.append(element)
        
        return elements
    
    def _classify_element_type(self, text: str) -> str:
        """根据文字内容分类UI元素类型"""
        search_indicators = ["搜索", "Search", "🔍"]
        article_indicators = ["公众号", "文章", "最新", "推荐", "阅读", "Read"]
        navigation_indicators = ["返回", "首页", "聊天", "通讯录", "Back", "Home"]
        account_indicators = ["公众号", "Official Account", "订阅号", "Service Account"]
        
        text_lower = text.lower()
        if any(indicator.lower() in text_lower for indicator in search_indicators):
            return "search_widget"
        elif any(indicator.lower() in text_lower for indicator in article_indicators):
            return "content_element"
        elif any(indicator.lower() in text_lower for indicator in navigation_indicators):
            return "navigation"
        elif any(indicator.lower() in text_lower for indicator in account_indicators):
            return "account_element"
        else:
            return "unknown"
    
    def _generate_state_description(self, ui_elements: List[Dict[str, Any]]) -> str:
        """生成界面状态描述"""
        search_widgets = [e for e in ui_elements if e["type"] == "search_widget"]
        content_elements = [e for e in ui_elements if e["type"] == "content_element"]
        navigation_elements = [e for e in ui_elements if e["type"] == "navigation"]
        account_elements = [e for e in ui_elements if e["type"] == "account_element"]
        
        description = f"界面状态: "
        if search_widgets:
            description += f"搜索框({len(search_widgets)}) "
        if account_elements:
            description += f"公众号({len(account_elements)}) "
        if content_elements:
            description += f"内容元素({len(content_elements)}) "
        if navigation_elements:
            description += f"导航元素({len(navigation_elements)}) "
        
        return description.strip()


class WeChatStatePerceptor(StatePerceptor):
    """微信特定的状态感知器"""
    
    def __init__(self, ocr_processor, dep_manager):
        super().__init__(ocr_processor, dep_manager)
        self.logger = logging.getLogger("mcp-server-wechat-viewer-mcp.wechat_perceptor")
    
    async def get_current_ui_state(self, bounds) -> Optional[Dict[str, Any]]:
        """获取微信界面状态"""
        try:
            # 调用父类方法获取基础状态
            ui_state = await super().get_current_ui_state(bounds)
            if not ui_state:
                return None
            
            # 添加微信特定的状态分析
            wechat_specific_state = self._analyze_wechat_specific_state(ui_state)
            ui_state.update(wechat_specific_state)
            
            return ui_state
            
        except Exception as e:
            self.logger.error(f"获取微信界面状态失败: {e}")
            return None
    
    def _analyze_wechat_specific_state(self, ui_state: Dict[str, Any]) -> Dict[str, Any]:
        """分析微信特定的状态"""
        ui_elements = ui_state.get("ui_elements", [])
        
        # 检查是否在微信主界面
        is_main_interface = self._is_wechat_main_interface(ui_elements)
        
        # 检查是否有搜索功能
        has_search = any(e["type"] == "search_widget" for e in ui_elements)
        
        # 检查是否有公众号
        has_accounts = any(e["type"] == "account_element" for e in ui_elements)
        
        # 检查是否有文章
        has_articles = any(e["type"] == "content_element" for e in ui_elements)
        
        return {
            "wechat_specific": {
                "is_main_interface": is_main_interface,
                "has_search": has_search,
                "has_accounts": has_accounts,
                "has_articles": has_articles,
                "interface_type": self._determine_interface_type(ui_elements)
            }
        }
    
    def _is_wechat_main_interface(self, ui_elements: List[Dict[str, Any]]) -> bool:
        """判断是否在微信主界面"""
        # 检查是否有微信特有的元素
        wechat_indicators = ["微信", "通讯录", "发现", "我", "WeChat", "Contacts", "Discover", "Me"]
        
        wechat_text = [e["text"] for e in ui_elements]
        wechat_text_lower = [text.lower() for text in wechat_text]
        
        # 如果包含多个微信特有元素，认为在主界面
        wechat_matches = sum(1 for indicator in wechat_indicators 
                           if any(indicator.lower() in text for text in wechat_text_lower))
        
        return wechat_matches >= 2
    
    def _determine_interface_type(self, ui_elements: List[Dict[str, Any]]) -> str:
        """确定界面类型"""
        ui_elements_text = [e["text"].lower() for e in ui_elements]
        
        if any("搜索" in text or "search" in text for text in ui_elements_text):
            return "search_interface"
        elif any("公众号" in text or "official account" in text for text in ui_elements_text):
            return "account_list_interface"
        elif any("文章" in text or "article" in text for text in ui_elements_text):
            return "article_list_interface"
        elif self._is_wechat_main_interface(ui_elements):
            return "main_interface"
        else:
            return "unknown_interface"
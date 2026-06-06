"""
LLM Response Parser

LLM 响应解析的共享模块，提供统一的响应解析逻辑。
被多个 LLM 客户端使用，确保解析一致性。
"""
import re
import logging
from typing import Optional, Union, Dict, Any, List


class LLMResponseParser:
    """LLM 响应解析器"""
    
    # 拒绝关键词列表
    REFUSAL_INDICATORS = [
        "unable", "can't", "cannot", "harmful", "policy", 
        "not allowed", "prohibited", "assistance with that request"
    ]
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        """初始化解析器"""
        self.logger = logger or logging.getLogger(__name__)
    
    def parse(self, content: Any) -> Optional[Union[Dict[str, Any], List[Any], str]]:
        """
        解析 LLM 响应内容
        
        Args:
            content: LLM 响应内容
            
        Returns:
            解析后的结果（dict、list 或 str）
        """
        if content is None:
            return None

        try:
            text = self._extract_text(content)
            if not text:
                # 当 LLM 返回空文本时，返回 found: false 而不是 None
                # 这样可以让上游知道 LLM 确实被调用了，只是没有找到结果
                self.logger.warning("LLM 返回空文本，视为未找到")
                return {"found": False, "error": "EMPTY_RESPONSE", "message": "LLM returned empty text"}
                
            # 检查是否包含拒绝内容
            if self._is_refusal(text):
                return {"found": False, "error": "LLM_REFUSAL", "message": text}
            
            # 尝试解析 JSON
            json_result = self._extract_json(text)
            if json_result is not None:
                return json_result
            
            # 返回纯文本
            return text.strip()
            
        except Exception as e:
            self.logger.error(f"响应解析失败: {e}")
            return None
    
    def _extract_text(self, content: Any) -> str:
        """从各种格式中提取文本"""
        text = ""
        
        if isinstance(content, str):
            text = content
        elif hasattr(content, 'content'):
            # MCP 响应对象
            parts = []
            content_items = content.content if isinstance(content.content, list) else [content.content]
            for p in content_items:
                if hasattr(p, 'text'):
                    parts.append(p.text)
                elif isinstance(p, dict) and 'text' in p:
                    parts.append(p['text'])
                elif hasattr(p, 'type') and p.type == 'text':
                    parts.append(getattr(p, 'text', str(p)))
                else:
                    parts.append(str(p))
            text = "".join(parts)
        elif isinstance(content, dict):
            for key in ["content", "response", "text", "output", "stdout", "result"]:
                if key in content and isinstance(content[key], (str, list)):
                    if isinstance(content[key], list):
                        parts = []
                        for it in content[key]:
                            if isinstance(it, dict) and "text" in it:
                                parts.append(it["text"])
                            else:
                                parts.append(str(it))
                        text = "".join(parts)
                    else:
                        text = str(content[key])
                    break
            if not text:
                if "found" in content or "verified" in content:
                    return str(content)
                text = str(content)
        elif isinstance(content, list):
            parts = []
            for p in content:
                if isinstance(p, dict) and 'text' in p:
                    parts.append(p['text'])
                elif hasattr(p, 'text'):
                    parts.append(p.text)
                else:
                    parts.append(str(p))
            text = "".join(parts)
        else:
            text = str(content)
        
        # 处理被字符串化的 TextContent 对象
        if "TextContent(type='text', text='" in text:
            match = re.search(r"text='({.*?})'", text, re.DOTALL)
            if match:
                text = match.group(1).replace("\\n", "\n").replace("\\\"", "\"")
        
        return text
    
    def _extract_json(self, text: str) -> Optional[Union[Dict[str, Any], List[Any]]]:
        """从文本中提取 JSON"""
        # 从 Markdown 中提取 JSON 块
        if "```" in text:
            blocks = re.findall(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
            if blocks:
                text = blocks[0]
        
        # 寻找最外层的 {} 或 []
        json_match = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
        if json_match:
            text = json_match.group(1)
        
        # 确保以 JSON 符号开始
        if not (text.strip().startswith('{') or text.strip().startswith('[')):
            start_idx = -1
            for i, char in enumerate(text):
                if char in '{[':
                    start_idx = i
                    break
            if start_idx != -1:
                text = text[start_idx:]
        
        # 解析 JSON
        try:
            return self._parse_json_with_refusal_check(text)
        except:
            return None
    
    def _parse_json_with_refusal_check(self, json_str: str) -> Dict[str, Any]:
        """解析 JSON 并检查拒绝内容"""
        import json
        result = json.loads(json_str)
        
        if isinstance(result, dict):
            for val in result.values():
                if isinstance(val, str) and any(x in val.lower() for x in self.REFUSAL_INDICATORS):
                    self.logger.warning(f"检测到 LLM 拒绝: {val[:200]}")
                    return {"found": False, "error": "LLM_REFUSAL", "message": val}
        
        return result
    
    def _is_refusal(self, text: str) -> bool:
        """检查文本是否包含拒绝内容"""
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in self.REFUSAL_INDICATORS)
    
    def parse_coordinate_result(
        self, 
        result: Any, 
        element_type: str
    ) -> Optional[tuple]:
        """
        解析坐标结果
        
        Args:
            result: 解析后的结果
            element_type: 元素类型
            
        Returns:
            (x, y) 元组或 None
        """
        parsed = self.parse(result)
        if not parsed or not isinstance(parsed, dict):
            return None
        
        if not parsed.get('found', False):
            return None
        
        x = parsed.get('center_x')
        y = parsed.get('center_y')
        
        if x is not None and y is not None:
            return (int(x), int(y))
        
        return None


# 全局解析器实例
_default_parser = None

def get_response_parser(logger: Optional[logging.Logger] = None) -> LLMResponseParser:
    """获取全局响应解析器实例"""
    global _default_parser
    if _default_parser is None:
        _default_parser = LLMResponseParser(logger)
    return _default_parser

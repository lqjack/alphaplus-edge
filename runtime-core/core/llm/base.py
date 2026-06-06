"""
Base LLM Client Protocol

Defines the protocol interface for LLM clients.
This ensures consistent interface across different implementations.
"""

from typing import Protocol, Dict, Any, Optional, Union, List
from dataclasses import dataclass
import logging


class LLMClientProtocol(Protocol):
    """Protocol defining the LLM client interface"""

    async def chat(self, messages: List[Dict[str, Any]], **kwargs) -> Any:
        """Send a chat request to LLM"""
        ...

    async def analyze(self, prompt: str) -> str:
        """Analyze text with LLM"""
        ...

    async def analyze_screenshot(
        self, prompt: str, screenshot_b64: str
    ) -> Optional[Union[Dict[str, Any], List[Any], str]]:
        """Analyze screenshot with LLM (multimodal)"""
        ...


@dataclass
class LLMToolResult:
    """Result from LLM tool execution"""

    success: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: float = 0.0


@dataclass
class ChatMessage:
    """Chat message structure"""

    role: str  # "system", "user", "assistant"
    content: str
    name: Optional[str] = None


import abc
from abc import ABC, abstractmethod

class BaseLLMClient(ABC):
    """
    Base LLM client with common functionality.
    Provides shared response parsing logic that can be used by
    different LLM client implementations.
    """

    def __init__(self, logger_instance: Optional[logging.Logger] = None):
        """Initialize base client"""
        self.logger = logger_instance or logging.getLogger(__name__)
        self._response_parser = None

    def _get_response_parser(self):
        """Get response parser (lazy initialization)"""
        if self._response_parser is None:
            # Try to import from wechat_viewer's parser if available
            try:
                from dataproai.src.servers.wechat_viewer.automation.llm_response_parser import (
                    get_response_parser,
                )

                self._response_parser = get_response_parser(self.logger)
            except ImportError:
                # Fallback to simple parser
                self._response_parser = SimpleResponseParser()
        return self._response_parser

    def _parse_response(
        self, content: Any
    ) -> Optional[Union[Dict[str, Any], List[Any], str]]:
        """Parse LLM response using available parser"""
        parser = self._get_response_parser()
        return parser.parse(content)

    @abstractmethod
    async def chat(self, messages: List[Dict[str, Any]], **kwargs) -> Any:
        """Send chat request."""
        pass

    async def analyze(self, prompt: str) -> str:
        """Analyze text with LLM."""
        messages = [{"role": "user", "content": prompt}]
        result = await self.chat(messages)
        parsed = self._parse_response(result)
        return str(parsed) if parsed is not None else ""

    @abstractmethod
    async def analyze_screenshot(
        self, prompt: str, screenshot_b64: str
    ) -> Optional[Union[Dict[str, Any], List[Any], str]]:
        """Analyze screenshot with LLM (multimodal)."""
        pass


class SimpleResponseParser:
    """Simple fallback response parser"""

    def parse(self, content: Any) -> Optional[Union[Dict[str, Any], List[Any], str]]:
        """Parse response content"""
        if content is None:
            return None

        # If already a string, return as-is
        if isinstance(content, str):
            return content.strip()

        # If it's a dict, try to extract content
        if isinstance(content, dict):
            # Common response structures
            if "content" in content:
                return content["content"]
            if "message" in content:
                msg = content["message"]
                if isinstance(msg, dict) and "content" in msg:
                    return msg["content"]
                return str(msg)
            if "choices" in content:
                choices = content["choices"]
                if choices and len(choices) > 0:
                    choice = choices[0]
                    if isinstance(choice, dict):
                        if "message" in choice:
                            return choice["message"].get("content", str(choice))
                        if "text" in choice:
                            return choice["text"]
                        return str(choice)
            return str(content)

        # If it's a list
        if isinstance(content, list):
            if len(content) > 0:
                return self.parse(content[0])
            return None

        # Fallback to string
        return str(content)

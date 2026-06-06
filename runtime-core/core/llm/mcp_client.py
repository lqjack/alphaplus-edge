"""
MCP-based LLM Client

Implementation of LLM client that communicates with AI server via MCP protocol.
Supports both text and multimodal (screenshot) analysis.

NOTE: Uses ServiceGateway for centralized AI service calls instead of direct MCP operations.
"""

import logging
from typing import Dict, Any, Optional, Union, List
import base64
import io

from core.llm.base import BaseLLMClient
from core.service.gateway import get_service_gateway

logger = logging.getLogger(__name__)


class MCPBasedLLMClient(BaseLLMClient):
    """
    LLM client that uses MCP protocol to communicate with AI server.

    This client sends LLM requests through the MCP tool invocation system,
    which can connect to either local or remote AI servers.

    Usage:
        client = MCPBasedLLMClient("ai")
        result = await client.chat([{"role": "user", "content": "Hello"}])
        analysis = await client.analyze("Explain this concept:")
        screenshot_result = await client.analyze_screenshot("What's in this image?", screenshot_b64)
    """

    def __init__(self, mcp_server_name: str = "ai"):
        """
        Initialize MCP-based LLM client.

        Args:
            mcp_server_name: Name of the MCP server to connect to (default: "ai")
        """
        super().__init__(logger)
        self.mcp_server_name = mcp_server_name
        self._gateway = None
        self.logger.info(f"MCP LLM Client initialized for server: {mcp_server_name}")

        # Lazy-load screenshot optimizer when needed
        self._screenshot_optimizer = None
        self._gateway = None

    def _get_gateway(self):
        """Lazy-load ServiceGateway"""
        if self._gateway is None:
            self._gateway = get_service_gateway()
        return self._gateway

    def _get_screenshot_optimizer(self):
        """Get screenshot optimizer (lazy initialization)"""
        if self._screenshot_optimizer is None:
            try:
                from dataproai.src.servers.wechat_viewer.automation.screenshot_optimizer import (
                    ScreenshotOptimizer,
                )

                self._screenshot_optimizer = ScreenshotOptimizer(logger=self.logger)
            except ImportError:
                self.logger.warning(
                    "ScreenshotOptimizer not available, using basic compression"
                )
                self._screenshot_optimizer = BasicScreenshotOptimizer()
        return self._screenshot_optimizer

    async def chat(self, messages: List[Dict[str, Any]], **kwargs) -> Any:
        """
        Send chat request via MCP protocol.

        Args:
            messages: List of message dicts with 'role' and 'content'
                     Content can also be a list for multimodal (text + images)
            **kwargs: Additional parameters:
                - max_tokens: Maximum tokens in response
                - temperature: Sampling temperature (0.0 - 2.0)
                - model: Specific model to use

        Returns:
            Raw LLM response (dict or other format from AI server)
        """
        try:
            # Build tool arguments
            arguments = {"messages": messages}

            # Add optional parameters
            if "max_tokens" in kwargs:
                arguments["max_tokens"] = kwargs["max_tokens"]
            if "temperature" in kwargs:
                arguments["temperature"] = kwargs["temperature"]
            if "model" in kwargs:
                arguments["model"] = kwargs["model"]

            self.logger.debug(
                f"Calling MCP tool 'chat_completion' on server '{self.mcp_server_name}' "
                f"with {len(messages)} messages"
            )

            # Use gateway for centralized AI service calls
            gateway = self._get_gateway()
            result = await gateway.call(
                self.mcp_server_name, "chat_completion", arguments
            )

            return result

        except Exception as e:
            self.logger.error(f"MCP chat request failed: {e}")
            raise

    async def analyze_screenshot(
        self, prompt: str, screenshot_b64: str
    ) -> Optional[Union[Dict[str, Any], List[Any], str]]:
        """
        Analyze screenshot using multimodal LLM.

        Args:
            prompt: Text prompt describing what to analyze in the image
            screenshot_b64: Base64 encoded screenshot image

        Returns:
            Parsed analysis result from LLM
        """
        try:
            # Optimize screenshot if optimizer available
            optimizer = self._get_screenshot_optimizer()
            optimized_b64, screenshot_info = optimizer.optimize(screenshot_b64)

            # Build multimodal message
            # Some models support direct base64, others need specific format
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

            self.logger.info(
                f"Analyzing screenshot ({len(optimized_b64)} chars) with LLM..."
            )

            # Send to LLM
            response = await self.chat(messages)

            if response is None:
                return None

            # Parse response
            parsed_result = self._parse_response(response)
            self.logger.debug(f"Screenshot analysis result: {type(parsed_result)}")

            return parsed_result

        except Exception as e:
            self.logger.error(f"Screenshot analysis failed: {e}")
            return None

    def get_last_screenshot_info(self) -> Optional[Dict[str, Any]]:
        """Get info about last processed screenshot (for coordinate mapping)"""
        optimizer = self._get_screenshot_optimizer()
        if hasattr(optimizer, "get_last_info"):
            return optimizer.get_last_info()
        return None


class BasicScreenshotOptimizer:
    """Basic screenshot compression when ScreenshotOptimizer not available"""

    def __init__(self):
        self._last_info = None

    def optimize(self, screenshot_b64: str) -> tuple[str, Dict[str, Any]]:
        """
        Basic optimization - just returns original with basic info.

        Returns:
            Tuple of (optimized_b64, screenshot_info)
        """
        # Calculate basic info
        try:
            img_data = base64.b64decode(screenshot_b64)
            size_bytes = len(img_data)

            info = {
                "original_size": size_bytes,
                "optimized_size": size_bytes,
                "scale_factor": 1.0,
                "width": None,  # Would need PIL to get actual dimensions
                "height": None,
            }
        except Exception:
            info = {
                "original_size": len(screenshot_b64),
                "optimized_size": len(screenshot_b64),
                "scale_factor": 1.0,
            }

        self._last_info = info
        return screenshot_b64, info

    def get_last_info(self) -> Optional[Dict[str, Any]]:
        """Get last screenshot info"""
        return self._last_info


# Alias for backward compatibility
LLMClient = MCPBasedLLMClient

"""
LLM Client Factory

Factory functions for creating LLM clients.
Provides unified interface for different LLM client implementations.

Supports two modes:
1. MCP mode: Uses MCP protocol to communicate with remote AI server
2. Direct mode: Direct Python calls when AI server is in same process
"""

import os
import logging
from typing import Optional, Union

from core.llm.base import BaseLLMClient, LLMClientProtocol
from core.llm.mcp_client import MCPBasedLLMClient

logger = logging.getLogger(__name__)

# Client instance cache
_client_cache: dict = {}

# Configuration for LLM communication mode
_llm_config = {
    "mode": os.getenv("LLM_CLIENT_MODE", "mcp"),  # "mcp" or "direct"
    "direct_import_path": os.getenv(
        "LLM_DIRECT_IMPORT", None
    ),  # e.g., "servers.ai.mcp_ai.analysis"
}


def set_llm_mode(mode: str) -> None:
    """
    Set the LLM communication mode.

    Args:
        mode: "mcp" for MCP protocol, "direct" for direct Python calls
    """
    global _llm_config
    _llm_config["mode"] = mode
    logger.info(f"LLM client mode set to: {mode}")


def get_llm_mode() -> str:
    """Get the current LLM communication mode"""
    return _llm_config["mode"]


def get_llm_client(
    server_name: str = "ai", force_new: bool = False, mode: Optional[str] = None
) -> BaseLLMClient:
    """
    Get or create an LLM client for the specified server.

    This is the recommended way to get an LLM client. Clients are cached
    by server name for reuse.

    Args:
        server_name: Name of the MCP server (default: "ai")
                    Common values: "ai", "wechat", "youtube"
        force_new: If True, create a new client instead of returning cached
        mode: Override the LLM mode ("mcp" or "direct")

    Returns:
        BaseLLMClient instance (MCPBasedLLMClient or DirectLLMClient)

    Example:
        from core.llm import get_llm_client

        # Get client for AI server
        client = get_llm_client("ai")
        result = await client.chat([{"role": "user", "content": "Hello"}])

        # Get client for WeChat automation
        wechat_client = get_llm_client("wechat")
    """
    global _client_cache

    # Determine mode
    actual_mode = mode or _llm_config["mode"]
    cache_key = f"{actual_mode}_{server_name}"

    if not force_new and cache_key in _client_cache:
        logger.debug(
            f"Returning cached LLM client for server: {server_name} (mode: {actual_mode})"
        )
        return _client_cache[cache_key]

    # Create client based on mode
    if actual_mode == "direct":
        client = _create_direct_client(server_name)
    else:
        client = MCPBasedLLMClient(mcp_server_name=server_name)

    # Cache it
    _client_cache[cache_key] = client
    logger.info(
        f"Created new LLM client for server: {server_name} (mode: {actual_mode})"
    )

    return client


def _create_direct_client(server_name: str) -> BaseLLMClient:
    """
    Create a direct client that imports the AI server module directly.

    This is more efficient when both client and AI server are in the same process.
    """
    try:
        # Try to import the AI server's analysis engine
        from dataproai.src.servers.ai.mcp_ai.analysis import AnalysisEngine

        return DirectLLMClient(analysis_engine_class=AnalysisEngine)
    except ImportError as e:
        logger.warning(
            f"Could not import direct AI engine: {e}, falling back to MCP mode"
        )
        return MCPBasedLLMClient(mcp_server_name=server_name)


def create_llm_client(
    client_type: str = "mcp", server_name: str = "ai", **kwargs
) -> BaseLLMClient:
    """
    Create an LLM client of the specified type.

    Args:
        client_type: Type of client to create:
            - "mcp": MCP-based client (default)
            - "direct": Direct client for same-process communication
        server_name: For MCP type, the server name to connect to
        **kwargs: Additional arguments for specific client types

    Returns:
        BaseLLMClient implementation

    Example:
        from core.llm import create_llm_client

        # Create MCP client
        mcp_client = create_llm_client("mcp", "ai")

        # Create direct client
        direct_client = create_llm_client("direct", "ai")
    """
    if client_type == "mcp":
        return MCPBasedLLMClient(mcp_server_name=server_name)
    elif client_type == "direct":
        return _create_direct_client(server_name)
    else:
        raise ValueError(f"Unknown client type: {client_type}")


def clear_client_cache():
    """Clear the client cache. Useful for testing or reset."""
    global _client_cache
    _client_cache.clear()
    logger.info("LLM client cache cleared")


# Convenience function for simple usage
async def chat_with_llm(prompt: str, server_name: str = "ai", **kwargs) -> str:
    """
    Convenience function for simple LLM chat.

    Args:
        prompt: Text prompt to send
        server_name: MCP server name (default: "ai")
        **kwargs: Additional arguments (max_tokens, temperature, etc.)

    Returns:
        LLM response as string

    Example:
        from core.llm import chat_with_llm

        result = await chat_with_llm("What is the capital of France?")
    """
    client = get_llm_client(server_name)
    return await client.analyze(prompt)


async def analyze_image(
    prompt: str, screenshot_b64: str, server_name: str = "ai"
) -> str:
    """
    Convenience function for screenshot analysis.

    Args:
        prompt: Question about the screenshot
        screenshot_b64: Base64 encoded screenshot
        server_name: MCP server name (default: "ai")

    Returns:
        Analysis result as string

    Example:
        from core.llm import analyze_image

        # Take screenshot and analyze
        result = await analyze_image(
            "What button is highlighted in this UI?",
            screenshot_b64
        )
    """
    client = get_llm_client(server_name)
    result = await client.analyze_screenshot(prompt, screenshot_b64)
    return str(result) if result is not None else ""


class DirectLLMClient(BaseLLMClient):
    """
    Direct LLM client for same-process communication.

    This client directly imports and calls the AI server's AnalysisEngine
    instead of going through MCP protocol. More efficient for local usage.
    """

    def __init__(self, analysis_engine_class=None):
        import logging

        super().__init__(logging.getLogger(__name__))

        self._analysis_engine_class = analysis_engine_class
        self._analysis_engine = None

    def _get_analysis_engine(self):
        """Get or create AnalysisEngine instance"""
        if self._analysis_engine is None and self._analysis_engine_class:
            self._analysis_engine = self._analysis_engine_class()
        return self._analysis_engine

    async def chat(self, messages, **kwargs):
        """Send chat request directly to AI engine"""
        engine = self._get_analysis_engine()
        if not engine:
            raise RuntimeError("Analysis engine not available")

        # Extract text from messages
        content = ""
        for msg in messages:
            if isinstance(msg, dict):
                role = msg.get("role", "user")
                msg_content = msg.get("content", "")
                if isinstance(msg_content, str):
                    content += f"{role}: {msg_content}\n"

        # Call analysis engine
        result = await engine.chat(content)
        return result

    async def analyze(self, prompt: str) -> str:
        """Analyze text directly"""
        engine = self._get_analysis_engine()
        if not engine:
            return "Analysis engine not available"

        result = await engine.chat(prompt)
        return str(result) if result else ""

    async def analyze_screenshot(self, prompt: str, screenshot_b64: str):
        """Analyze screenshot - not supported in direct mode"""
        return {"error": "Screenshot analysis not supported in direct mode"}

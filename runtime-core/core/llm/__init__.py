"""
Core LLM Module

Shared LLM client implementations for DataProAI servers.
Provides unified interface for LLM communication across different servers.

Architecture:
- BaseLLMClient: Protocol defining LLM client interface
- MCPBasedLLMClient: MCP-based implementation for remote LLM calls
- DirectLLMClient: Direct Python calls for same-process communication
- get_llm_client: Factory function to create appropriate client
- set_llm_mode: Configure communication mode (mcp/direct)

Usage:
    from core.llm import get_llm_client, set_llm_mode

    # Set mode (optional - default is "mcp")
    set_llm_mode("direct")  # Use direct calls when AI server is local

    # Create client for AI server
    client = get_llm_client("ai")
    result = await client.chat([{"role": "user", "content": "Hello"}])

    # Or use convenience functions
    from core.llm import chat_with_llm
    result = await chat_with_llm("What is the capital of France?")
"""

from core.llm.base import BaseLLMClient, LLMClientProtocol
from core.llm.mcp_client import MCPBasedLLMClient
from core.llm.factory import (
    get_llm_client,
    create_llm_client,
    chat_with_llm,
    analyze_image,
    set_llm_mode,
    get_llm_mode,
    DirectLLMClient,
    clear_client_cache,
)

__all__ = [
    # Base classes
    "BaseLLMClient",
    "LLMClientProtocol",
    # Implementations
    "MCPBasedLLMClient",
    "DirectLLMClient",
    # Factory functions
    "get_llm_client",
    "create_llm_client",
    "set_llm_mode",
    "get_llm_mode",
    "clear_client_cache",
    # Convenience functions
    "chat_with_llm",
    "analyze_image",
]

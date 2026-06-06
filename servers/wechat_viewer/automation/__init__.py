"""
WeChat Automation Package

This package provides a comprehensive WeChat automation system with the following components:

1. **Main Orchestrator**: WeChatAutomation - High-level API for WeChat operations
2. **Window Management**: WindowManager - Handles WeChat window operations
3. **OCR Processing**: OCRProcessor - Handles image capture and text recognition
4. **Search Navigation**: SearchNavigator - Handles search operations and navigation
5. **Article Reading**: ArticleReader - Handles article reading and content extraction
6. **Performance Monitoring**: PerformanceMonitor - Tracks performance and resource usage
7. **Adaptive OCR**: AdaptiveOCR - Intelligent OCR with fallback strategies
8. **Interfaces**: Defines abstract interfaces for platform independence

Key Features:
- Platform-independent design through interfaces
- Performance monitoring and optimization
- Error handling and retry mechanisms
- Comprehensive logging
- Resource management
- Health checks and diagnostics

Usage:
```python
from wechat_automation import WeChatAutomation, WeChatConfig

# Create configuration
config = WeChatConfig(
    search_timeout=30,
    read_timeout=60,
    enable_performance_monitoring=True
)

# Initialize automation
automation = WeChatAutomation(config)

# Search for public account
success = automation.search_public_account("公众号名称")

# Read an article
article = automation.read_article("文章标题")

# Get performance metrics
metrics = automation.get_performance_summary()

# Run health check
health = automation.run_health_check()
```
"""

from .wechat_automation import WeChatAutomation, WeChatConfig
from .window_manager import WindowManager
from .ocr_processor import OCRProcessor
from .search_navigator import SearchNavigator
from .article_reader import ArticleReader
from .performance_monitor import PerformanceMonitor
from .adaptive_ocr import AdaptiveOCR
# Handle mcp_core imports gracefully
try:
    from mcp_core.interfaces import (
        IWindowManager,
        IGUIAutomation,
        IOCRProcessor,
        WindowBounds
    )
    MCP_CORE_INTERFACES_AVAILABLE = True
except ImportError:
    # Define fallback interfaces if mcp_core is not available
    MCP_CORE_INTERFACES_AVAILABLE = False

    # Define minimal fallback interfaces
    class IWindowManager: pass
    class IGUIAutomation: pass
    class IOCRProcessor: pass

    # Define minimal dataclass
    from dataclasses import dataclass
    @dataclass
    class WindowBounds:
        X: float = 0.0
        Y: float = 0.0
        Width: float = 0.0
        Height: float = 0.0

__all__ = [
    # Main orchestrator
    'WeChatAutomation',
    'WeChatConfig',
    
    # Component managers
    'WindowManager',
    'OCRProcessor',
    'SearchNavigator',
    'ArticleReader',
    'PerformanceMonitor',
    'AdaptiveOCR',
    
    # Interfaces
    'IWindowManager',
    'IGUIAutomation',
    'IOCRProcessor',
    'WindowBounds',
]
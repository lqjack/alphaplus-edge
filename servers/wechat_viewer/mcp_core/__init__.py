"""
Core Module for WeChat Viewer Server

Provides common types, protocols, and base classes for all MCP servers.
"""


from .dependency_types import DependencyInfo, DependencyManagerProtocol
from .window_manager import WindowManager, WindowManagerFactory
from .gui_automation import GUIAutomation, GUIAutomationFactory
from .ocr_processor import OCRProcessor
from .decision_engine import DecisionEngine, DecisionEngineFactory
from .state_perceptor import StatePerceptor, WeChatStatePerceptor
from .task_scheduler import TaskScheduler, SmartTaskScheduler

# Import local modules
from .llm_protocol import LLMClientProtocol

__all__ = [
    # Core types and protocols
    'DependencyInfo',
    'DependencyManagerProtocol', 
    'LLMClientProtocol',
    
    # Window management
    'WindowManager',
    'WindowManagerFactory',
    
    # GUI automation
    'GUIAutomation',
    'GUIAutomationFactory',
    
    # OCR processing
    'OCRProcessor',
    
    # Decision making
    'DecisionEngine',
    'DecisionEngineFactory',
    
    # State perception
    'StatePerceptor',
    'WeChatStatePerceptor',
    
    # Task scheduling
    'TaskScheduler',
    'SmartTaskScheduler'
]

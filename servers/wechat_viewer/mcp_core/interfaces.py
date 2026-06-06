"""
MCP Core Interfaces

Defines the contract for core components including window management,
GUI automation, OCR processing, and cross-platform automation.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass
from enum import Enum

@dataclass
class WindowBounds(dict):
    """Window bounds data structure with dual object/dict access"""
    X: float
    Y: float
    Width: float
    Height: float

    def __init__(self, X: float, Y: float, Width: float, Height: float):
        super().__init__(X=X, Y=Y, Width=Width, Height=Height)
        self.X = X
        self.Y = Y
        self.Width = Width
        self.Height = Height

class AutomationStatus(Enum):
    """Status of an automation operation"""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL_SUCCESS = "partial_success"
    TIMEOUT = "timeout"
    ERROR = "error"

@dataclass
class AutomationResult:
    """Result of an automation operation"""
    status: AutomationStatus
    message: str
    data: Optional[Dict[str, Any]] = None
    execution_time: float = 0.0
    error_details: Optional[str] = None

class IWindowManager(ABC):
    """Interface for window management operations"""
    @abstractmethod
    def bring_to_front(self, app_id: Optional[str] = None) -> bool: pass
    
    @abstractmethod
    def get_window_bounds(self, app_id: Optional[str] = None) -> Optional[Dict[str, float]]: pass
    
    @abstractmethod
    def verify_visibility(self, app_id: Optional[str] = None) -> bool: pass

    @abstractmethod
    def is_frontmost(self, app_id: Optional[str] = None) -> bool: pass

    @abstractmethod
    def ensure_running(self, app_id: Optional[str] = None) -> bool: pass

class IGUIAutomation(ABC):
    """Interface for GUI automation operations"""
    @abstractmethod
    def click_at(self, x: float, y: float) -> bool: pass
    
    @abstractmethod
    def type_text(self, text: str) -> bool: pass
    
    @abstractmethod
    def press_key(self, key: str) -> bool: pass
    
    @abstractmethod
    def scroll_down(self) -> bool: pass
    
    @abstractmethod
    def close_tab(self) -> bool: pass

@dataclass
class TextResult(dict):
    """OCR text recognition result with dual object/dict access for compatibility"""
    text: str
    confidence: float
    position: Dict[str, float]

    def __init__(self, text: str, confidence: float, position: Dict[str, float]):
        # Initializing dict superclass
        super().__init__(text=text, confidence=confidence, position=position)
        # Initializing dataclass attributes
        self.text = text
        self.confidence = confidence
        self.position = position

class IOCRProcessor(ABC):
    """Interface for OCR and image processing operations"""
    @abstractmethod
    def capture_screenshot(self, region: Optional[Tuple[int, int, int, int]] = None) -> Optional[Any]: pass

    @abstractmethod
    def find_text(self, image: Any, text: str, fuzzy_match: bool = False) -> List[TextResult]: pass

    @abstractmethod
    def recognize(self, image: Any) -> List[TextResult]: pass


# Cross-Platform Automation Interfaces

@dataclass
class PlatformCapabilities:
    """Platform-specific capabilities and limitations"""
    supports_accessibility_api: bool = False
    supports_ui_automation: bool = False
    supports_ocr: bool = True
    supports_vision_llm: bool = False
    max_concurrent_operations: int = 1
    requires_permissions: List[str] = None

    def __post_init__(self):
        if self.requires_permissions is None:
            self.requires_permissions = []


@dataclass
class ElementLocation:
    """Represents a located UI element with confidence scoring"""
    x: int
    y: int
    width: int
    height: int
    confidence: float  # 0.0 to 1.0
    strategy_used: str  # e.g., "accessibility", "ocr", "llm_vision"
    element_id: Optional[str] = None
    element_name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class AutomationPlan:
    """Represents a step-by-step automation plan"""
    goal: str
    steps: List[Dict[str, Any]]
    current_step: int = 0
    estimated_duration: float = 0.0
    success_criteria: List[str] = None

    def __post_init__(self):
        if self.success_criteria is None:
            self.success_criteria = []


@dataclass
class ExecutionContext:
    """Context information for automation execution"""
    session_id: str
    start_time: float
    last_checkpoint: float
    retry_count: Dict[str, int] = None
    learned_strategies: Dict[str, Any] = None
    performance_metrics: Dict[str, float] = None

    def __post_init__(self):
        if self.retry_count is None:
            self.retry_count = {}
        if self.learned_strategies is None:
            self.learned_strategies = {}
        if self.performance_metrics is None:
            self.performance_metrics = {}


class IPlatformAdapter(ABC):
    """Interface for platform-specific automation adapters"""

    @abstractmethod
    def get_capabilities(self) -> PlatformCapabilities: pass

    @abstractmethod
    def click_at(self, x: int, y: int) -> bool: pass

    @abstractmethod
    def type_text(self, text: str) -> bool: pass

    @abstractmethod
    def press_key(self, key: str) -> bool: pass

    @abstractmethod
    def scroll_down(self) -> bool: pass

    @abstractmethod
    def close_tab(self) -> bool: pass

    @abstractmethod
    def capture_screenshot(self, region: Optional[Dict[str, int]] = None): pass

    @abstractmethod
    def clear_input(self) -> bool: pass

    @abstractmethod
    def find_element_by_accessibility_id(self, element_id: str, app_name: Optional[str] = None) -> Optional[ElementLocation]: pass

    @abstractmethod
    def find_element_by_name(self, name: str, app_name: Optional[str] = None) -> Optional[ElementLocation]: pass

    @abstractmethod
    def find_elements_by_type(self, element_type: str, app_name: Optional[str] = None) -> List[ElementLocation]: pass

    @abstractmethod
    def get_active_window_info(self) -> Optional[Dict[str, Any]]: pass


class IAdaptiveElementLocator(ABC):
    """Interface for adaptive element locator with multi-modal strategies"""

    @abstractmethod
    def locate_element(self,
                      target_description: str,
                      fallback_strategies: List[str] = None,
                      timeout: float = 10.0) -> Optional[ElementLocation]: pass

    @abstractmethod
    def locate_elements(self,
                       target_description: str,
                       fallback_strategies: List[str] = None,
                       timeout: float = 10.0) -> List[ElementLocation]: pass

    @abstractmethod
    def record_successful_strategy(self,
                                  target_description: str,
                                  strategy_used: str,
                                  location: ElementLocation): pass

    @abstractmethod
    def get_learned_strategies(self) -> Dict[str, List[str]]: pass


class ILLMTaskPlanner(ABC):
    """Interface for LLM-driven task planning"""

    @abstractmethod
    def decompose_goal(self,
                      goal: str,
                      current_state: Dict[str, Any]) -> AutomationPlan: pass

    @abstractmethod
    def adjust_plan(self,
                   plan: AutomationPlan,
                   execution_results: List[Dict[str, Any]]) -> AutomationPlan: pass

    @abstractmethod
    def validate_plan_feasibility(self, plan: AutomationPlan) -> bool: pass

    @abstractmethod
    def get_planning_context(self) -> Dict[str, Any]: pass


class IIntelligentExecutionMonitor(ABC):
    """Interface for intelligent execution monitoring"""

    @abstractmethod
    def execute_step(self,
                    step: Dict[str, Any],
                    context: ExecutionContext) -> Dict[str, Any]: pass

    @abstractmethod
    def validate_step_result(self,
                            step: Dict[str, Any],
                            result: Dict[str, Any]) -> bool: pass

    @abstractmethod
    def detect_error_state(self) -> Optional[str]: pass

    @abstractmethod
    def execute_recovery(self, error_type: str) -> bool: pass

    @abstractmethod
    def should_replan(self, consecutive_failures: int) -> bool: pass


class IStatePersistenceLayer(ABC):
    """Interface for state persistence and checkpointing"""

    @abstractmethod
    def save_checkpoint(self,
                       session_id: str,
                       context: ExecutionContext,
                       metadata: Dict[str, Any] = None) -> str: pass

    @abstractmethod
    def load_checkpoint(self, checkpoint_id: str) -> Optional[ExecutionContext]: pass

    @abstractmethod
    def save_learned_strategy(self,
                             task_type: str,
                             strategy: str,
                             success_rate: float) -> bool: pass

    @abstractmethod
    def get_learned_strategies(self, task_type: str) -> List[Dict[str, Any]]: pass

    @abstractmethod
    def save_session_data(self, session_id: str, data: Dict[str, Any]) -> bool: pass

    @abstractmethod
    def load_session_data(self, session_id: str) -> Optional[Dict[str, Any]]: pass


class IConfigManager(ABC):
    """Interface for configuration management"""

    @abstractmethod
    def load_config(self, config_path: str) -> Dict[str, Any]: pass

    @abstractmethod
    def save_config(self, config_path: str, config_data: Dict[str, Any]) -> bool: pass

    @abstractmethod
    def get_config_value(self, key: str, default: Any = None) -> Any: pass

    @abstractmethod
    def set_config_value(self, key: str, value: Any) -> bool: pass

    @abstractmethod
    def get_platform_config(self, platform: str) -> Dict[str, Any]: pass

    @abstractmethod
    def update_platform_config(self, platform: str, config_data: Dict[str, Any]) -> bool: pass

    @abstractmethod
    def get_tunable_parameter(self, param_name: str, default: Any = None) -> Any: pass

    @abstractmethod
    def set_tunable_parameter(self, param_name: str, value: Any) -> bool: pass

    @abstractmethod
    def reload_config(self) -> bool: pass

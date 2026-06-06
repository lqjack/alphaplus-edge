"""
Cross-Platform Automation Engine (Universal)

Abstracts platform-specific GUI automation details through a unified interface.
Delegates high-level mission planning and execution to the UniversalMissionOrchestrator.
"""
import platform
import logging
import asyncio
from typing import Dict, Optional, Any, Tuple, List
from .interfaces import (
    IPlatformAdapter,
    IAdaptiveElementLocator,
    ILLMTaskPlanner,
    IIntelligentExecutionMonitor,
    IStatePersistenceLayer,
    PlatformCapabilities,
    ElementLocation,
    AutomationPlan,
    ExecutionContext
)
from .dependency_types import (
    MACOS_ADAPTER,
    WINDOWS_ADAPTER,
    ADAPTIVE_ELEMENT_LOCATOR,
    LLM_TASK_PLANNER,
    INTELLIGENT_EXECUTION_MONITOR,
    STATE_PERSISTENCE_LAYER,
    CONFIG_MANAGER,
    WINDOW_MANAGER
)
from .universal_workflow import UniversalMissionOrchestrator

class CrossPlatformAutomationEngine:
    """Universal automation engine that handles both Desktop and Web targets"""

    def __init__(self, dependency_manager):
        self.dep_manager = dependency_manager
        self.logger = logging.getLogger("mcp-server-universal-automation.engine")
        self.platform = platform.system().lower()
        
        # Core components
        self._platform_adapter: Optional[IPlatformAdapter] = None
        self._window_manager: Optional[Any] = None
        self._orchestrator = UniversalMissionOrchestrator(self)
        
        self._initialize_components()

    def _initialize_components(self):
        """Initialize platform-specific adapters and window managers"""
        try:
            if self.platform == "darwin":
                self._platform_adapter = self.dep_manager.get_dependency(MACOS_ADAPTER)
            elif self.platform == "windows":
                self._platform_adapter = self.dep_manager.get_dependency(WINDOWS_ADAPTER)
            
            self._window_manager = self.dep_manager.get_dependency(WINDOW_MANAGER)
            
            if self._platform_adapter:
                self.logger.info(f"Universal automation engine initialized with {type(self._platform_adapter).__name__}")
            else:
                self.logger.warning(f"Universal automation engine initialized WITHOUT platform adapter for {self.platform}")
        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")

    # --- Unified Application Management ---

    def bring_to_front(self, app_name: str) -> bool:
        """Bring any application to front"""
        if self._window_manager:
            return self._window_manager.bring_to_front(app_name)
        return False

    def is_running(self, app_name: str) -> bool:
        """Check if application is running"""
        if self._window_manager:
            return self._window_manager.ensure_running(app_name)
        return False

    def get_window_bounds(self, app_name: str) -> Optional[Dict[str, float]]:
        if self._window_manager:
            return self._window_manager.get_window_bounds(app_name)
        return None

    # --- Low-Level Automation (Delegated) ---

    def click_at(self, x: int, y: int) -> bool:
        return self._platform_adapter.click_at(x, y) if self._platform_adapter else False

    def type_text(self, text: str) -> bool:
        return self._platform_adapter.type_text(text) if self._platform_adapter else False

    def press_key(self, key: str) -> bool:
        return self._platform_adapter.press_key(key) if self._platform_adapter else False

    # --- Mission Execution (Universal Workflow) ---

    async def execute_mission(self, app_name: str, goal: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Execute a high-level goal-driven mission using the LangGraph orchestrator.
        """
        self.logger.info(f"Starting mission on {app_name}: {goal}")
        return await self._orchestrator.run_mission(app_name, goal, context)

    async def read_articles(self, app_name: str, max_articles: int = 5) -> List[Dict[str, Any]]:
        if not self._platform_adapter:
            return []

        try:
            from .dependency_types import OCR_PROCESSOR
            ocr_processor = self.dep_manager.get_dependency(OCR_PROCESSOR)
            if ocr_processor:
                screenshot = ocr_processor.capture_screenshot()
                if screenshot:
                    import pytesseract
                    import numpy as np
                    if hasattr(screenshot, 'convert'):
                        screenshot = screenshot.convert('RGB')
                    img_array = np.array(screenshot)
                    ocr_text = pytesseract.image_to_string(img_array, lang='chi_sim+eng')
                    if ocr_text:
                        lines = [l.strip() for l in ocr_text.split('\n') if l.strip()]
                        articles = []
                        seen = set()
                        for line in lines:
                            if len(line) >= 4 and line not in seen:
                                if any(stop in line for stop in ["搜索", "通讯录", "公众号", "朋友圈", "小程序", "视频号", "游戏"]):
                                    continue
                                articles.append({"title": line})
                                seen.add(line)
                                if len(articles) >= max_articles:
                                    break
                        if articles:
                            self.logger.info(f"OCR extracted {len(articles)} article candidates")
                            return articles
        except Exception as e:
            self.logger.warning(f"OCR extraction failed: {e}")

        texts = self._platform_adapter.extract_text_elements(app_name)
        articles = []
        seen = set()
        for text in texts:
            if len(text) > 5 and text not in seen:
                if not any(stopword in text.lower() for stopword in ["search", "menu", "tab", "profile", "chat"]):
                     articles.append({"title": text})
                     seen.add(text)
                     if len(articles) >= max_articles:
                          break

        return articles

    # Alias for legacy compatibility
    async def execute_smart_mission(self, mission_config: Dict[str, Any]) -> bool:
        goal = mission_config.get("goal") or mission_config.get("name")
        app_name = mission_config.get("app_name", "WeChat")
        result = await self.execute_mission(app_name, goal, mission_config)
        return result.get("success", False)
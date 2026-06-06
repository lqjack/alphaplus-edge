"""
Window Management Bridge

Handles cross-platform window management by delegating to the 
CrossPlatformAutomationEngine while maintaining backward compatibility.
"""
import logging
import time
from typing import Dict, Optional, Any, List
from mcp_core.interfaces import IWindowManager, IGUIAutomation, WindowBounds
from mcp_core.dependency_types import CROSS_PLATFORM_AUTOMATION_ENGINE

class WindowManager(IWindowManager):
    """
    Bridge class that provides unified window management and automation,
    delegating to the CrossPlatformAutomationEngine.
    """

    def __init__(self, window_manager: Optional[IWindowManager] = None, 
                 gui_automation: Optional[IGUIAutomation] = None,
                 dep_manager: Any = None):
        """
        Initialize the bridge.
        """
        self.logger = logging.getLogger("mcp-server-wechat-viewer-mcp.window_manager_bridge")
        self.dep_manager = dep_manager
        
        # Legacy components for fallback
        self._legacy_wm = window_manager
        self._legacy_gui = gui_automation
        
        # Cached engine
        self._engine = None

    def _get_engine(self) -> Optional[Any]:
        """Retrieve the cross-platform automation engine if available"""
        if self._engine is not None:
            return self._engine
            
        if self.dep_manager:
            try:
                self._engine = self.dep_manager.get_dependency(CROSS_PLATFORM_AUTOMATION_ENGINE)
            except:
                pass
        return self._engine

    def _ensure_frontmost(
        self,
        app_id: Optional[str] = None,
        *,
        activate: bool = True,
        attempts: int = 3,
        settle_seconds: float = 0.4,
    ) -> bool:
        """Guard low-level GUI actions so input is only sent to the target app."""
        target = app_id or "WeChat"
        for attempt in range(max(1, attempts)):
            try:
                if self.is_frontmost(target):
                    return True
            except Exception as exc:
                self.logger.warning("Failed to check %s frontmost state: %s", target, exc)

            if not activate:
                break

            try:
                self.logger.info(
                    "Activating %s before GUI action (attempt %s/%s)",
                    target,
                    attempt + 1,
                    attempts,
                )
                self.bring_to_front(target)
            except Exception as exc:
                self.logger.warning("Failed to activate %s before GUI action: %s", target, exc)

            time.sleep(settle_seconds)

        try:
            if self.is_frontmost(target):
                return True
        except Exception as exc:
            self.logger.warning("Final %s frontmost check failed: %s", target, exc)

        self.logger.error("%s is not frontmost; GUI action was blocked", target)
        return False

    def bring_to_front(self, app_id: Optional[str] = None) -> bool:
        """Bring application to front"""
        engine = self._get_engine()
        target = app_id or "WeChat"
        if engine and hasattr(engine, 'bring_to_front'):
            return engine.bring_to_front(target)
        
        if self._legacy_wm and hasattr(self._legacy_wm, 'bring_to_front'):
            return self._legacy_wm.bring_to_front(target)
        return False

    def get_window_bounds(self, app_id: Optional[str] = None) -> Optional[Dict[str, float]]:
        """Get application window bounds"""
        engine = self._get_engine()
        target = app_id or "WeChat"
        if engine and hasattr(engine, 'get_window_bounds'):
            return engine.get_window_bounds(target)
            
        if self._legacy_wm and hasattr(self._legacy_wm, 'get_window_bounds'):
            return self._legacy_wm.get_window_bounds(target)
        return None

    def get_window_info(self, app_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get application window metadata when the underlying manager supports it."""
        engine = self._get_engine()
        target = app_id or "WeChat"
        if engine and hasattr(engine, 'get_window_info'):
            return engine.get_window_info(target)

        if self._legacy_wm and hasattr(self._legacy_wm, 'get_window_info'):
            return self._legacy_wm.get_window_info(target)
        return None

    def verify_visibility(self, app_id: Optional[str] = None) -> bool:
        """Verify application visibility"""
        engine = self._get_engine()
        target = app_id or "WeChat"
        if engine and hasattr(engine, 'verify_visibility'):
            return engine.verify_visibility(target)
            
        if self._legacy_wm and hasattr(self._legacy_wm, 'verify_visibility'):
            return self._legacy_wm.verify_visibility(target)
        return False

    def is_frontmost(self, app_id: Optional[str] = None) -> bool:
        """Check if application is frontmost"""
        engine = self._get_engine()
        target = app_id or "WeChat"
        if engine and hasattr(engine, 'is_frontmost'):
            return engine.is_frontmost(target)
            
        if self._legacy_wm and hasattr(self._legacy_wm, 'is_frontmost'):
            return self._legacy_wm.is_frontmost(target)
        return False

    def ensure_running(self, app_id: Optional[str] = None) -> bool:
        """Ensure application is running"""
        engine = self._get_engine()
        target = app_id or "WeChat"
        if engine and hasattr(engine, 'is_running'):
            return engine.is_running(target)
            
        if self._legacy_wm and hasattr(self._legacy_wm, 'ensure_running'):
            return self._legacy_wm.ensure_running(target)
        return True

    # GUI Automation Methods
    
    def click_at(self, x: float, y: float) -> bool:
        if not self._ensure_frontmost("WeChat", activate=True):
            return False
        engine = self._get_engine()
        if engine: return engine.click_at(int(x), int(y))
        if self._legacy_gui: return self._legacy_gui.click_at(x, y)
        return False

    def type_text(self, text: str) -> bool:
        if not self._ensure_frontmost("WeChat", activate=False):
            return False
        engine = self._get_engine()
        if engine: return engine.type_text(text)
        if self._legacy_gui: return self._legacy_gui.type_text(text)
        return False

    def press_key(self, key: str) -> bool:
        if not self._ensure_frontmost("WeChat", activate=False):
            return False
        engine = self._get_engine()
        if engine: return engine.press_key(key)
        if self._legacy_gui: return self._legacy_gui.press_key(key)
        return False

    def scroll_down(self) -> bool:
        if not self._ensure_frontmost("WeChat", activate=False):
            return False
        engine = self._get_engine()
        if engine: return engine.scroll_down()
        if self._legacy_gui: return self._legacy_gui.scroll_down()
        return False

    def clear_input(self) -> bool:
        if not self._ensure_frontmost("WeChat", activate=False):
            return False
        engine = self._get_engine()
        if engine: return engine.clear_input()
        if self._legacy_gui: return self._legacy_gui.clear_input()
        return False

    def close_tab(self) -> bool:
        if not self._ensure_frontmost("WeChat", activate=True):
            return False
        engine = self._get_engine()
        if engine: return engine.close_tab()
        if self._legacy_gui: return self._legacy_gui.close_tab()
        return False

    # Standard bridge methods (legacy compatibility)
    def ensure_wechat_running(self) -> bool:
        return self.ensure_running("WeChat")

    def bring_to_front_fast(self) -> bool:
        return self.bring_to_front("WeChat")

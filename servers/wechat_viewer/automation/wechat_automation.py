"""
WeChat Automation Orchestrator

Main orchestrator class that coordinates all automation components.
Provides a clean, high-level API for WeChat operations.
"""
import logging
import platform
import sys
import asyncio
import time
import statistics
import os
import re
import json
import html
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*_args, **_kwargs):
        return False

from mcp_core.interfaces import (
    IWindowManager, 
    IGUIAutomation, 
    IOCRProcessor, 
    AutomationStatus, 
    AutomationResult,
    WindowBounds
)
from automation.adaptive_ocr import AdaptiveOCR
from automation.window_manager import WindowManager
from automation.ocr_processor import OCRProcessor
from automation.search_navigator import SearchNavigator
from automation.article_reader import ArticleReader
from automation.performance_monitor import PerformanceMonitor
from automation.window_state_manager import WindowStateManager
from automation.multi_layer_locator import MultiLayerLocator
from automation.config_helper import ConfigHelper
from automation.screenshot_helper import ScreenshotHelper
from automation.accessibility_service import WeChatAccessibilityService
from automation.llm_element_locator import LLMElementLocator
from automation.unified_element_locator import UnifiedElementLocator
try:
    from shared.computer_use import ComputerUseFallbackPromptBuilder
except ImportError:
    try:
        from dataproai.src.servers.shared.computer_use import (
            ComputerUseFallbackPromptBuilder,
        )
    except ImportError:
        ComputerUseFallbackPromptBuilder = None

# Add project root to path
# (Keeping path logic for now to ensure compatibility)
project_src = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
project_root = os.path.dirname(project_src)

if project_src not in sys.path:
    sys.path.insert(0, project_src)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Load environment variables
load_dotenv()

# Older status code referenced this flag without defining it. Keep the field
# stable for API callers while the GUI automation stack is loaded lazily.
MCP_AVAILABLE = True

WECHAT_UNIFIED_LOCATOR_TIMEOUT_SECONDS = float(
    os.getenv("WECHAT_UNIFIED_LOCATOR_TIMEOUT_SECONDS", "4.0")
)
WECHAT_LLM_LOCATOR_TIMEOUT_SECONDS = float(
    os.getenv("WECHAT_LLM_LOCATOR_TIMEOUT_SECONDS", "6.0")
)
WECHAT_ACCOUNT_SEARCH_STAGE_TIMEOUT_SECONDS = float(
    os.getenv("WECHAT_ACCOUNT_SEARCH_STAGE_TIMEOUT_SECONDS", "15.0")
)
WECHAT_ACCOUNT_SEARCH_STAGE_TIMEOUT_SECONDS_READ = float(
    os.getenv("WECHAT_ACCOUNT_SEARCH_STAGE_TIMEOUT_SECONDS_READ", "25.0")
)
WECHAT_WINDOW_PREP_STAGE_TIMEOUT_SECONDS = float(
    os.getenv("WECHAT_WINDOW_PREP_STAGE_TIMEOUT_SECONDS", "18.0")
)
WECHAT_WINDOW_PREP_STAGE_TIMEOUT_SECONDS_READ = float(
    os.getenv("WECHAT_WINDOW_PREP_STAGE_TIMEOUT_SECONDS_READ", "30.0")
)
WECHAT_ACCOUNT_SELECTION_STAGE_TIMEOUT_SECONDS = float(
    os.getenv("WECHAT_ACCOUNT_SELECTION_STAGE_TIMEOUT_SECONDS", "20.0")
)
WECHAT_ACCOUNT_SELECTION_STAGE_TIMEOUT_SECONDS_READ = float(
    os.getenv("WECHAT_ACCOUNT_SELECTION_STAGE_TIMEOUT_SECONDS_READ", "75.0")
)
WECHAT_ACCOUNT_ARTICLE_STAGE_TIMEOUT_SECONDS = float(
    os.getenv("WECHAT_ACCOUNT_ARTICLE_STAGE_TIMEOUT_SECONDS", "25.0")
)
WECHAT_ARTICLE_LIST_SECTION_MARKERS = (
    "今天",
    "昨天",
    "前天",
    "最新消息",
    "文章",
    "全部",
)
WECHAT_ARTICLE_HEADER_BLOCKED_LABELS = {
    "展开",
    "文章",
    "全部",
    "今天",
    "昨天",
    "前天",
    "最新消息",
}
WECHAT_ARTICLE_HEADER_BLOCKED_PHRASES = (
    "朋友关注",
    "发消息",
    "视频号：",
    "查看历史消息",
)
WECHAT_ARTICLE_PROFILE_DESCRIPTOR_MARKERS = (
    "主管主办",
    "定位",
    "账号主体",
    "功能介绍",
    "内容介绍",
    "公众号简介",
)
WECHAT_ARTICLE_OVERVIEW_NOISE_MARKERS = (
    "原创内容",
    "小时前更新",
    "分钟前更新",
    "24小时全球财经快讯",
    "7x24财经快讯",
    "24小时实时财经新闻",
    "今日财经头条",
    "财联社早知道",
    "财联社今日头条",
    "Account",
    "Articles",
    "Related Results",
)
WECHAT_ARTICLE_TRADING_SIGNAL_KEYWORDS = (
    ("涨停", 10),
    ("跌停", 8),
    ("重组", 10),
    ("复牌", 8),
    ("停牌", 5),
    ("并购", 8),
    ("收购", 7),
    ("定增", 7),
    ("回购", 6),
    ("业绩", 5),
    ("预增", 7),
    ("预亏", 5),
    ("特斯拉", 8),
    ("马斯克", 6),
    ("机器人", 7),
    ("人工智能", 7),
    ("ai", 4),
    ("芯片", 7),
    ("半导体", 7),
    ("算力", 6),
    ("新能源车", 9),
    ("新能源汽车", 9),
    ("电动车", 7),
    ("锂电", 7),
    ("电池", 6),
    ("智能驾驶", 8),
    ("自动驾驶", 8),
    ("无人驾驶", 8),
    ("辅助驾驶", 7),
    ("光模块", 10),
    ("cpo", 9),
    ("服务器", 7),
    ("ai服务器", 9),
    ("液冷", 8),
    ("铜缆", 8),
    ("通信", 5),
    ("磷化铟", 10),
    ("铌酸锂", 9),
    ("稀土", 6),
    ("黄金", 6),
    ("军工", 6),
    ("深海", 8),
    ("油气", 9),
    ("油田", 8),
    ("天然气", 8),
    ("海工", 7),
    ("海洋工程", 7),
)
WECHAT_ARTICLE_LOW_CONVICTION_FINANCIAL_KEYWORDS = (
    ("净利润", 5),
    ("归母净利润", 5),
    ("营业收入", 4),
    ("营收", 4),
    ("同比增长", 4),
    ("一季报", 3),
    ("半年报", 3),
    ("年报", 3),
    ("季报", 3),
    ("四大行", 8),
    ("建设银行", 8),
    ("工商银行", 8),
    ("农业银行", 8),
    ("中国银行", 8),
)
WECHAT_ARTICLE_WEAK_SIGNAL_KEYWORDS = frozenset(
    {
        "业绩",
        "一季报",
        "半年报",
        "年报",
        "季报",
    }
)
WECHAT_OG_TITLE_RE = re.compile(
    r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
WECHAT_HTML_TITLE_RE = re.compile(
    r"<title[^>]*>(.*?)</title>",
    re.IGNORECASE | re.DOTALL,
)

# Import MCP components
from mcp_core import (
    WindowManagerFactory,
    GUIAutomationFactory
)


def detect_mcp_server_name(service_name: str = "ai") -> str:
    """
    检测应该使用哪个 MCP 服务器名称

    根据环境变量中的 MCP_{SERVICE}_URL 配置，智能决定使用 stdio 还是 API 模式

    Args:
        service_name: 基础服务名称（如 "ai", "wechat"）

    Returns:
        正确的服务器名称（如 "ai", "ai_api", "wechat", "wechat_api"）
    """
    env_var = f"MCP_{service_name.upper()}_URL"
    remote_url = os.getenv(env_var)

    if remote_url:
        api_server_name = f"{service_name}_api"
        logger = logging.getLogger("mcp-server-detection")
        logger.info(f"检测到远程 API 配置: {env_var}={remote_url}，使用服务器: {api_server_name}")
        return api_server_name

    return service_name


@dataclass
class WeChatConfig:
    """WeChat automation configuration"""
    search_timeout: int = 30
    read_timeout: int = 60
    screenshot_dir: str = "temp_screenshots"
    enable_performance_monitoring: bool = True
    max_retries: int = 3
    wechat_bundle_id: str = "com.tencent.xinWeChat"
    ocr_enabled: bool = True  # OCR 功能开关


class WeChatAutomation:
    """Main WeChat automation orchestrator"""

    _REFERENCE_WINDOW_WIDTH = 900.0
    _REFERENCE_WINDOW_HEIGHT = 760.0
    _WECHAT_ARTICLE_URL_RE = re.compile(r"(https?://)?mp\.weixin\.qq\.com/s[^\s\"'<>]*", re.IGNORECASE)
    _GENERIC_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)

    def __init__(self, config: Optional[WeChatConfig] = None,
                 dep_manager=None, ocr_processor=None, llm_client=None):
        self.config = config or WeChatConfig()
        self.logger = logging.getLogger("mcp-server-wechat-viewer-mcp.wechat_automation")

        # Platform detection
        self.platform = platform.system().lower()
        self.logger.info(f"WeChatAutomation initialized for platform: {self.platform}")

        # Initialize performance monitoring
        self.performance_monitor = PerformanceMonitor()
        if self.config.enable_performance_monitoring:
            self.logger.info("Performance monitoring enabled")

        # Essential components
        self.dep_manager = dep_manager
        self._init_components(dep_manager, ocr_processor, llm_client)

        # Start performance monitoring if enabled
        if self.config.enable_performance_monitoring:
            self.performance_monitor.start_monitoring()

    def _init_components(self, dep_manager, ocr_processor, llm_client):
        """Unified component initialization"""
        self.logger.info("Initializing components using modular architecture")

        # Initialize config helper
        self.config_helper = ConfigHelper(self.logger)

        # Initialize core components using factories or provided instances
        if dep_manager:
            self.window_manager_interface = WindowManagerFactory.create_window_manager(dep_manager)
            self.gui_automation = GUIAutomationFactory.create_gui_automation(dep_manager)
        else:
            self.logger.error("No dependency manager provided, core components may be unavailable")
            self.window_manager_interface = None
            self.gui_automation = None

        self.window_manager = WindowManager(self.window_manager_interface, self.gui_automation)
        self.ocr_processor = ocr_processor
        self.llm_client = llm_client
        self.accessibility_service = WeChatAccessibilityService(dep_manager, self.logger)

        # Initialize helpers
        self.screenshot_helper = ScreenshotHelper(self.logger)
        
        # Load capability flags
        self.ocr_enabled = self.config_helper.load_ocr_enabled(self.config.ocr_enabled)
        self.llm_enabled = self.config_helper.load_llm_enabled(llm_client)

        # Initialize specialized locators
        if self.ocr_enabled and self.ocr_processor:
            self.adaptive_ocr = AdaptiveOCR(self.ocr_processor)
            self.multi_layer_locator = MultiLayerLocator(
                self.adaptive_ocr,
                self.window_manager_interface,
                template_dir="wechat_templates"
            )
        else:
            self.adaptive_ocr = None
            self.multi_layer_locator = None

        # Initialize LLM element locator
        if self.llm_enabled and llm_client:
            self.llm_element_locator = LLMElementLocator(llm_client, self.llm_enabled, self.logger)
            self.llm_element_locator.set_screenshot_helper(self.screenshot_helper)
        else:
            self.llm_element_locator = None

        # Initialize unified element locator — pass the llm_client regardless
        # of whether it exposes `judge_element`; MultimodalJudge can also drive
        # the legacy visual fallback entrypoint when grounding is unavailable.
        self.unified_element_locator = UnifiedElementLocator(
            logger=self.logger,
            ocr_processor=self.ocr_processor,
            ai_client=llm_client,
        )
        self._unified_locator_initialized = False

        # Search navigator and article reader
        self.search_navigator = SearchNavigator(
            self.window_manager,
            self.ocr_processor,
            self.gui_automation,
            self.adaptive_ocr
        )
        self.article_reader = ArticleReader(
            self.window_manager,
            self.ocr_processor,
            self.gui_automation,
            self.adaptive_ocr
        )

    async def _ensure_unified_locator_initialized(self):
        """Ensure the unified element locator is initialized"""
        if not self._unified_locator_initialized:
            try:
                await self.unified_element_locator.initialize()
                self._unified_locator_initialized = True
                self.logger.info("UnifiedElementLocator initialized successfully")
            except Exception as e:
                self.logger.error(f"Failed to initialize UnifiedElementLocator: {e}")
                # Don't raise the exception - we'll fall back to other methods

    async def _await_with_timeout(
        self,
        label: str,
        awaitable,
        timeout_seconds: float,
        *,
        default: Any = None,
    ) -> Any:
        """Bound slow locator/network stages so GUI tools fall back instead of hanging."""
        if timeout_seconds <= 0:
            return await awaitable
        try:
            return await asyncio.wait_for(awaitable, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            self.logger.warning("%s timed out after %.1fs", label, timeout_seconds)
            return default
        except Exception as exc:
            self.logger.warning("%s failed: %s", label, exc)
            return default

    def __del__(self):
        """Cleanup on destruction"""
        config = getattr(self, "config", None)
        if (
            hasattr(self, 'performance_monitor')
            and config is not None
            and getattr(config, "enable_performance_monitoring", False)
        ):
            self.performance_monitor.stop_monitoring()

    # ====== New API methods (from wechat_automation_fixed) ======

    def bring_wechat_to_front(self) -> AutomationResult:
        """Bring WeChat window to front"""
        start_time = time.time()
        try:
            self.logger.info("Bringing WeChat window to front")
            success = self.window_manager.bring_to_front()

            execution_time = time.time() - start_time
            self.performance_monitor.record_operation("bring_wechat_to_front", execution_time, success)

            if success:
                return AutomationResult(
                    status=AutomationStatus.SUCCESS,
                    message="WeChat window brought to front successfully",
                    execution_time=execution_time
                )
            else:
                return AutomationResult(
                    status=AutomationStatus.FAILURE,
                    message="Failed to bring WeChat window to front",
                    execution_time=execution_time
                )
        except Exception as e:
            execution_time = time.time() - start_time
            self.performance_monitor.record_operation("bring_wechat_to_front", execution_time, False)
            self.logger.error(f"Error bringing WeChat to front: {e}")
            return AutomationResult(
                status=AutomationStatus.ERROR,
                message=f"Exception occurred: {e}",
                execution_time=execution_time,
                error_details=str(e)
            )

    def get_wechat_window_bounds(self) -> AutomationResult:
        """Get WeChat window bounds"""
        start_time = time.time()
        try:
            self.logger.info("Getting WeChat window bounds")
            bounds = self.window_manager.get_window_bounds()

            execution_time = time.time() - start_time
            success = bounds is not None

            self.performance_monitor.record_operation("get_wechat_window_bounds", execution_time, success)

            if success:
                # Handle both dict and WindowBounds object
                if isinstance(bounds, dict):
                    bounds_dict = bounds
                else:
                    # WindowBounds object
                    bounds_dict = {
                        'X': bounds.X,
                        'Y': bounds.Y,
                        'Width': bounds.Width,
                        'Height': bounds.Height
                    }

                return AutomationResult(
                    status=AutomationStatus.SUCCESS,
                    message="WeChat window bounds retrieved successfully",
                    data={"bounds": bounds_dict},
                    execution_time=execution_time
                )
            else:
                is_frontmost = False
                is_visible = False
                bring_to_front_result = False
                try:
                    is_frontmost = bool(self.window_manager.is_frontmost())
                except Exception as frontmost_error:
                    self.logger.warning(
                        "Failed to determine whether WeChat is frontmost while diagnosing bounds failure: %s",
                        frontmost_error,
                    )
                try:
                    is_visible = bool(self.window_manager.verify_visibility())
                except Exception as visibility_error:
                    self.logger.warning(
                        "Failed to verify WeChat visibility while diagnosing bounds failure: %s",
                        visibility_error,
                    )
                if not is_frontmost:
                    try:
                        bring_to_front_result = bool(self.window_manager.bring_to_front())
                    except Exception as bring_to_front_error:
                        self.logger.warning(
                            "Failed to bring WeChat to front while diagnosing bounds failure: %s",
                            bring_to_front_error,
                        )

                self.logger.error(
                    "Failed to get WeChat window bounds. frontmost=%s visible=%s bring_to_front_attempted=%s",
                    is_frontmost,
                    is_visible,
                    bring_to_front_result,
                )
                return AutomationResult(
                    status=AutomationStatus.FAILURE,
                    message=(
                        "Failed to get WeChat window bounds "
                        f"(frontmost={is_frontmost}, visible={is_visible}, "
                        f"bring_to_front_attempted={bring_to_front_result})"
                    ),
                    execution_time=execution_time
                )
        except Exception as e:
            execution_time = time.time() - start_time
            self.performance_monitor.record_operation("get_wechat_window_bounds", execution_time, False)
            self.logger.error(f"Error getting WeChat window bounds: {e}")
            return AutomationResult(
                status=AutomationStatus.ERROR,
                message=f"Exception occurred: {e}",
                execution_time=execution_time,
                error_details=str(e)
            )

    def _ensure_wechat_frontmost(
        self,
        *,
        activate: bool = True,
        attempts: int = 3,
        settle_seconds: float = 0.6,
    ) -> bool:
        """Ensure WeChat owns keyboard focus before any click or keyboard action."""
        for attempt in range(max(1, attempts)):
            try:
                if self.window_manager.is_frontmost():
                    return True
            except Exception as e:
                self.logger.warning("Failed to check WeChat frontmost state: %s", e)

            if not activate:
                break

            try:
                self.logger.info("Activating WeChat before UI input (attempt %s/%s)", attempt + 1, attempts)
                self.window_manager.bring_to_front()
            except Exception as e:
                self.logger.warning("Failed to activate WeChat before UI input: %s", e)

            time.sleep(settle_seconds)

        try:
            if self.window_manager.is_frontmost():
                return True
        except Exception as e:
            self.logger.warning("Final WeChat frontmost check failed: %s", e)

        self.logger.error("WeChat is not frontmost; refusing to send click or keyboard input")
        return False

    def _has_recent_wechat_focus(self, *, grace_seconds: float = 1.5) -> bool:
        deadline = float(getattr(self, "_wechat_focus_grace_deadline", 0.0) or 0.0)
        return deadline > time.time()

    def _prime_wechat_for_immediate_action(self, *, settle_seconds: float = 0.18) -> bool:
        """Raise WeChat immediately before a click/keystroke without re-running a long focus loop."""
        for attempt in range(2):
            try:
                self.window_manager.bring_to_front()
            except Exception as exc:
                self.logger.warning("Failed to prime WeChat for immediate action: %s", exc)
                return False

            time.sleep(settle_seconds)
            try:
                if self.window_manager.is_frontmost():
                    self._wechat_focus_grace_deadline = time.time() + 1.5
                    return True
            except Exception as exc:
                self.logger.warning("Failed to verify WeChat focus after priming attempt %s: %s", attempt + 1, exc)

        self.logger.error("WeChat could not be re-activated for immediate UI input")
        return False

    def click_at(self, x: int, y: int) -> AutomationResult:
        """Click at specific coordinates"""
        start_time = time.time()
        try:
            if not self._ensure_wechat_frontmost(activate=False):
                if not self._prime_wechat_for_immediate_action():
                    execution_time = time.time() - start_time
                    self.performance_monitor.record_operation("click_at", execution_time, False)
                    return AutomationResult(
                        status=AutomationStatus.FAILURE,
                        message="WeChat could not be primed for click input",
                        execution_time=execution_time,
                    )
            else:
                self._wechat_focus_grace_deadline = time.time() + 1.0

            # Use GUI automation to click at coordinates
            success = self.gui_automation.click_at(x, y)
            if success:
                self._wechat_focus_grace_deadline = time.time() + 1.5

            execution_time = time.time() - start_time
            self.performance_monitor.record_operation("click_at", execution_time, success)

            if success:
                return AutomationResult(
                    status=AutomationStatus.SUCCESS,
                    message=f"Successfully clicked at ({x}, {y})",
                    execution_time=execution_time
                )
            else:
                return AutomationResult(
                    status=AutomationStatus.FAILURE,
                    message=f"Failed to click at ({x}, {y})",
                    execution_time=execution_time
                )
        except Exception as e:
            execution_time = time.time() - start_time
            self.performance_monitor.record_operation("click_at", execution_time, False)
            self.logger.error(f"Error clicking at coordinates: {e}")
            return AutomationResult(
                status=AutomationStatus.ERROR,
                message=f"Exception occurred: {e}",
                execution_time=execution_time,
                error_details=str(e)
            )

    def _click_at_with_focus_retry(
        self,
        x: int,
        y: int,
        *,
        attempts: int = 2,
    ) -> AutomationResult:
        """Retry a WeChat click after explicit foreground recovery."""
        last_result: Optional[AutomationResult] = None
        for attempt in range(max(1, attempts)):
            last_result = self.click_at(x, y)
            if last_result.status == AutomationStatus.SUCCESS:
                return last_result
            if attempt >= attempts - 1:
                break
            self.logger.info(
                "Click at (%s, %s) failed, reactivating WeChat before retry %s/%s",
                x,
                y,
                attempt + 2,
                attempts,
            )
            if not self._ensure_wechat_frontmost(activate=True, attempts=2, settle_seconds=0.45):
                break

        return last_result or AutomationResult(
            status=AutomationStatus.FAILURE,
            message=f"Failed to click at ({x}, {y}) after foreground recovery retries",
            execution_time=0.0,
        )

    def type_text(self, text: str, ensure_focus: bool = True) -> bool:
        """Type text with optional focus assurance
        
        Args:
            text: Text to type
            ensure_focus: Whether to bring window to front before typing (default: True)
        """
        try:
            if ensure_focus and self._has_recent_wechat_focus():
                success = self.gui_automation.type_text(text)
                if success:
                    self._wechat_focus_grace_deadline = time.time() + 1.0
                return success

            if not self._ensure_wechat_frontmost(activate=False):
                if not ensure_focus or not self._prime_wechat_for_immediate_action():
                    return False
            else:
                self._wechat_focus_grace_deadline = time.time() + 1.0

            success = self.gui_automation.type_text(text)
            if success:
                self._wechat_focus_grace_deadline = time.time() + 1.0
            return success
        except Exception as e:
            self.logger.error(f"Error typing text: {e}")
            return False

    def press_key(self, key: str) -> bool:
        """Press a key with focus assurance"""
        try:
            if not self._ensure_wechat_frontmost(activate=False):
                if not self._prime_wechat_for_immediate_action():
                    return False
            else:
                self._wechat_focus_grace_deadline = time.time() + 0.8
            
            success = self.gui_automation.press_key(key)
            if success:
                self._wechat_focus_grace_deadline = time.time() + 0.8
            return success
        except Exception as e:
            self.logger.error(f"Error pressing key: {e}")
            return False

    def _press_key_with_focus_retry(
        self,
        key: str,
        *,
        attempts: int = 2,
    ) -> bool:
        """Retry a WeChat key press after explicit foreground recovery."""
        for attempt in range(max(1, attempts)):
            if self.press_key(key):
                return True
            if attempt >= attempts - 1:
                break
            self.logger.info(
                "Key '%s' failed, reactivating WeChat before retry %s/%s",
                key,
                attempt + 2,
                attempts,
            )
            if not self._ensure_wechat_frontmost(activate=True, attempts=2, settle_seconds=0.45):
                break
        return False

    def clear_input(self) -> bool:
        """Clear input with focus assurance"""
        try:
            if self._has_recent_wechat_focus():
                success = self.gui_automation.clear_input()
                if success:
                    self._wechat_focus_grace_deadline = time.time() + 0.8
                return success
            if not self._ensure_wechat_frontmost(activate=False):
                if not self._prime_wechat_for_immediate_action():
                    return False
            else:
                self._wechat_focus_grace_deadline = time.time() + 0.8
            success = self.gui_automation.clear_input()
            if success:
                self._wechat_focus_grace_deadline = time.time() + 0.8
            return success
        except Exception as e:
            self.logger.error(f"Error clearing input: {e}")
            return False

    async def search_wechat_account(self, bounds: Dict[str, int], account_name: str) -> AutomationResult:
        """Search for a WeChat public account"""
        start_time = time.time()
        try:
            self.logger.info(f"Searching for WeChat account: {account_name}")

            success = False
            search_bar = await self._locate_search_bar(bounds)
            if search_bar:
                self.logger.info(
                    "Search bar located at (%s, %s) via %s confidence=%s",
                    search_bar["x"],
                    search_bar["y"],
                    search_bar.get("method"),
                    search_bar.get("confidence"),
                )
                click_result = self._click_at_with_focus_retry(search_bar["x"], search_bar["y"])
                if click_result.status == AutomationStatus.SUCCESS:
                    await asyncio.sleep(0.8)
                    success = await self._input_account_name(account_name, time, bounds)
                else:
                    self.logger.error("Failed to click located search bar: %s", click_result.message)
            else:
                self.logger.warning("Accurate search bar locator returned no result")

            # Fallback to basic search if unified locator failed or not available
            if not success:
                self.logger.info("Falling back to basic search method")
                success = await self._basic_search_account(bounds, account_name)

            execution_time = time.time() - start_time
            self.performance_monitor.record_operation("search_wechat_account", execution_time, success)

            if success:
                return AutomationResult(
                    status=AutomationStatus.SUCCESS,
                    message=f"Successfully searched for account: {account_name}",
                    data={"found": True, "account_name": account_name},
                    execution_time=execution_time
                )
            else:
                return AutomationResult(
                    status=AutomationStatus.FAILURE,
                    message=f"Failed to search for account: {account_name}",
                    execution_time=execution_time
                )
        except Exception as e:
            execution_time = time.time() - start_time
            self.performance_monitor.record_operation("search_wechat_account", execution_time, False)
            self.logger.error(f"Error searching WeChat account: {e}")
            return AutomationResult(
                status=AutomationStatus.ERROR,
                message=f"Exception occurred: {e}",
                execution_time=execution_time,
                error_details=str(e)
            )

    async def _basic_search_account(self, bounds: Dict[str, int], account_name: str) -> bool:
        """
        Basic search account implementation using OCR-based intelligent positioning
        不再使用硬编码的坐标偏移
        """
        try:
            if not self._ensure_wechat_frontmost(activate=True):
                self.logger.error("WeChat is not frontmost before locating search bar")
                return False

            # 使用智能定位搜索框
            click_success = await self._locate_and_click_search_bar_simple(bounds)

            if not click_success:
                self.logger.error("无法定位并点击搜索框")
                return False

            # 等待搜索框激活
            await asyncio.sleep(1)

            # 输入公众号名称 - 使用改进的输入方法
            type_result = await self._input_account_name(account_name, time, bounds)

            if not type_result:
                self.logger.error("输入公众号名称失败")
                return False

            # 等待搜索结果
            await asyncio.sleep(2)

            return True
        except Exception as e:
            self.logger.error(f"Basic search failed: {e}")
            return False

    def _get_screen_interaction_bounds(self) -> Optional[Dict[str, int]]:
        """Use the full screen as the interaction region when window bounds are unavailable."""
        ocr_processor = getattr(self, "ocr_processor", None)
        if not ocr_processor:
            try:
                from PIL import ImageGrab

                screenshot = ImageGrab.grab(all_screens=True)
                if screenshot is None:
                    self.logger.error("Failed to capture full-screen screenshot for fallback bounds")
                    return None

                screen_width, screen_height = screenshot.size
                screenshot.close() if hasattr(screenshot, "close") else None
                logical_bounds = {
                    "X": 0,
                    "Y": 0,
                    "Width": max(1, int(screen_width)),
                    "Height": max(1, int(screen_height)),
                }
                self.logger.warning(
                    "OCR unavailable; using ImageGrab primary-screen fallback bounds: %s",
                    logical_bounds,
                )
                return logical_bounds
            except Exception as exc:
                self.logger.warning(
                    "Fallback full-screen bounds via ImageGrab failed: %s",
                    exc,
                )
                self.logger.error("OCR processor unavailable; cannot derive full-screen fallback bounds")
                return None

        screenshot = ocr_processor.capture_screenshot()
        if screenshot is None:
            self.logger.error("Failed to capture full-screen screenshot for fallback bounds")
            return None

        if hasattr(screenshot, "shape"):
            screen_height, screen_width = screenshot.shape[:2]
        elif hasattr(screenshot, "size") and isinstance(screenshot.size, tuple):
            screen_width, screen_height = screenshot.size
        else:
            self.logger.error("Unsupported screenshot type for fallback bounds: %s", type(screenshot))
            return None

        screen_scale = 1.0
        if self.llm_element_locator:
            try:
                screen_scale = self.llm_element_locator._detect_screen_scale(screen_width)
            except Exception as scale_error:
                self.logger.warning("Failed to detect screen scale for fallback bounds: %s", scale_error)

        logical_bounds = {
            "X": 0,
            "Y": 0,
            "Width": max(1, int(screen_width / screen_scale)),
            "Height": max(1, int(screen_height / screen_scale)),
        }
        self.logger.warning(
            "Using full-screen interaction bounds fallback: screenshot=%sx%s scale=%.2f logical_bounds=%s",
            screen_width,
            screen_height,
            screen_scale,
            logical_bounds,
        )
        return logical_bounds

    def _get_interaction_bounds(self) -> Optional[Dict[str, int]]:
        """Return WeChat window bounds, falling back to the full screen."""
        bounds_result = self.get_wechat_window_bounds()
        if bounds_result.status == AutomationStatus.SUCCESS:
            return bounds_result.data["bounds"]

        self.logger.warning(
            "Window bounds unavailable; using full-screen fallback: %s",
            bounds_result.message,
        )
        return self._get_screen_interaction_bounds()

    def _get_frontmost_wechat_window_bounds(self) -> Optional[Dict[str, int]]:
        """Return the bounds of WeChat's current front window, including article windows."""
        dep_manager = getattr(self, "dep_manager", None)
        if not dep_manager:
            return None
        try:
            subprocess = dep_manager.get_dependency("subprocess")
            if not subprocess:
                return None
            script = '''
            tell application "System Events"
                if exists process "WeChat" then
                    tell process "WeChat"
                        if (count of windows) > 0 then
                            set p to position of front window
                            set s to size of front window
                            return (item 1 of p as string) & "," & (item 2 of p as string) & "," & (item 1 of s as string) & "," & (item 2 of s as string)
                        end if
                    end tell
                end if
            end tell
            return ""
            '''
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=5)
            parts = [part.strip() for part in result.stdout.strip().split(",") if part.strip()]
            if len(parts) != 4:
                return None
            x, y, width, height = [int(float(part)) for part in parts]
            if width <= 0 or height <= 0:
                return None
            resolved_bounds = {"X": x, "Y": y, "Width": width, "Height": height}
            quartz_window = self._find_wechat_window_info_by_bounds(resolved_bounds)
            if quartz_window:
                return quartz_window["bounds"]
            return resolved_bounds
        except Exception as exc:
            self.logger.debug("Failed to get frontmost WeChat window bounds: %s", exc)
            return None

    def _attach_window_capture_metadata(
        self,
        bounds: Optional[Dict[str, Any]],
        *,
        window_id: Optional[Any] = None,
        window_bounds: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        normalized_bounds = self._normalize_capture_bounds(bounds)
        if not normalized_bounds:
            return None

        enriched = dict(normalized_bounds)
        numeric_window_id = int(window_id or 0)
        normalized_window_bounds = self._normalize_capture_bounds(window_bounds or bounds)
        if numeric_window_id > 0 and normalized_window_bounds:
            enriched["_window_id"] = numeric_window_id
            enriched["_window_bounds"] = normalized_window_bounds
        return enriched

    def _inherit_window_capture_metadata(
        self,
        region: Optional[Dict[str, Any]],
        source_bounds: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        normalized_region = self._normalize_capture_bounds(region)
        if not normalized_region:
            return None
        if not isinstance(source_bounds, dict):
            return normalized_region

        window_id = source_bounds.get("_window_id") or source_bounds.get("window_id")
        window_bounds = source_bounds.get("_window_bounds") or source_bounds.get("window_bounds") or source_bounds
        enriched = self._attach_window_capture_metadata(
            normalized_region,
            window_id=window_id,
            window_bounds=window_bounds,
        )
        return enriched or normalized_region

    def _collect_wechat_quartz_candidates(
        self,
        *,
        list_option: Optional[int],
        source_label: str,
    ) -> List[Dict[str, Any]]:
        lookup_manager, quartz = self._get_wechat_quartz_lookup_source()
        if not lookup_manager or not quartz:
            return []

        try:
            profile = lookup_manager._get_profile("WeChat")
            return lookup_manager._collect_window_candidates(
                quartz,
                profile,
                list_option,
                source_label,
            ) or []
        except Exception as exc:
            self.logger.debug("Failed to scan Quartz candidates for WeChat %s: %s", source_label, exc)
            return []

    def _get_wechat_quartz_lookup_source(self) -> Tuple[Optional[Any], Optional[Any]]:
        """Resolve the concrete Quartz-capable window manager behind the bridge wrapper."""
        managers: List[Any] = []
        bridge_manager = getattr(self, "window_manager", None)
        if bridge_manager:
            managers.append(bridge_manager)
            legacy_manager = getattr(bridge_manager, "_legacy_wm", None)
            if legacy_manager and legacy_manager is not bridge_manager:
                managers.append(legacy_manager)

        interface_manager = getattr(self, "window_manager_interface", None)
        if interface_manager and interface_manager not in managers:
            managers.append(interface_manager)

        for manager in managers:
            collect_candidates = getattr(manager, "_collect_window_candidates", None)
            get_profile = getattr(manager, "_get_profile", None)
            if not callable(collect_candidates) or not callable(get_profile):
                continue

            dep_managers = [
                getattr(manager, "dep_manager", None),
                getattr(bridge_manager, "dep_manager", None) if bridge_manager else None,
                getattr(interface_manager, "dep_manager", None) if interface_manager else None,
                self.dep_manager,
            ]
            for dep_manager in dep_managers:
                if not dep_manager:
                    continue
                try:
                    quartz = dep_manager.get_dependency("quartz")
                except Exception:
                    quartz = None
                if quartz:
                    return manager, quartz
        return None, None

    def _window_info_from_candidate(self, candidate: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        bounds = self._attach_window_capture_metadata(
            candidate.get("bounds"),
            window_id=candidate.get("window_id"),
            window_bounds=candidate.get("bounds"),
        )
        if not bounds:
            return None
        return {
            "window_id": int(candidate.get("window_id") or 0),
            "bounds": bounds,
            "name": candidate.get("name") or "",
        }

    def _find_wechat_window_info_by_title(self, window_title: Optional[str]) -> Optional[Dict[str, Any]]:
        """Resolve a named WeChat child window from Quartz so region screenshots use the right window id."""
        if not window_title:
            return None
        lookup_manager, quartz = self._get_wechat_quartz_lookup_source()
        if not lookup_manager or not quartz:
            return None
        candidates = self._collect_wechat_quartz_candidates(
            list_option=quartz.kCGWindowListOptionOnScreenOnly | quartz.kCGWindowListExcludeDesktopElements,
            source_label="named_window_lookup",
        )

        matching_candidates = [
            candidate
            for candidate in candidates
            if (candidate.get("name") or "").strip() == (window_title or "").strip()
        ]
        if not matching_candidates:
            matching_candidates = [
                candidate
                for candidate in candidates
                if self._looks_like_target_account_window_title(
                    candidate.get("name"),
                    window_title,
                )
            ]
        if not matching_candidates:
            return None

        def candidate_score(candidate: Dict[str, Any]) -> Tuple[int, float]:
            return (
                1 if candidate.get("layer") == 0 else 0,
                float(candidate.get("area") or 0.0),
            )

        best_candidate = max(matching_candidates, key=candidate_score)
        return self._window_info_from_candidate(best_candidate)

    def _find_wechat_window_info_by_bounds(
        self,
        bounds: Optional[Dict[str, Any]],
        *,
        preferred_name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        normalized_target = self._normalize_capture_bounds(bounds)
        if not normalized_target:
            return None

        lookup_manager, quartz = self._get_wechat_quartz_lookup_source()
        if not lookup_manager or not quartz:
            return None

        candidates = self._collect_wechat_quartz_candidates(
            list_option=quartz.kCGWindowListOptionOnScreenOnly | quartz.kCGWindowListExcludeDesktopElements,
            source_label="bounds_window_lookup",
        )
        if not candidates:
            candidates = self._collect_wechat_quartz_candidates(
                list_option=quartz.kCGWindowListOptionAll,
                source_label="bounds_window_lookup_all",
            )

        matching_candidates = [
            candidate
            for candidate in candidates
            if self._bounds_roughly_match(
                candidate.get("bounds"),
                normalized_target,
                position_tolerance=28,
                size_tolerance=72,
            )
        ]
        if not matching_candidates:
            return None

        preferred_key = (preferred_name or "").strip()

        def candidate_score(candidate: Dict[str, Any]) -> Tuple[int, int, float]:
            candidate_name = (candidate.get("name") or "").strip()
            return (
                1 if preferred_key and candidate_name == preferred_key else 0,
                1 if candidate.get("layer") == 0 else 0,
                float(candidate.get("area") or 0.0),
            )

        best_candidate = max(matching_candidates, key=candidate_score)
        return self._window_info_from_candidate(best_candidate)

    def _applescript_string(self, value: str) -> str:
        escaped = (value or "").replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'

    def _raise_wechat_window_by_title(self, window_title: Optional[str]) -> bool:
        """Raise a specific WeChat child window without forcing the main chat window."""
        if not window_title or not self.dep_manager:
            return False
        try:
            subprocess = self.dep_manager.get_dependency("subprocess")
            if not subprocess:
                return False
            resolved_title = window_title
            quartz_match = self._find_wechat_window_info_by_title(window_title)
            if quartz_match and (quartz_match.get("name") or "").strip():
                resolved_title = (quartz_match.get("name") or "").strip()
            quoted_title = self._applescript_string(resolved_title)
            script = f'''
            tell application "System Events"
                if exists process "WeChat" then
                    tell process "WeChat"
                        set frontmost to true
                        if exists window {quoted_title} then
                            set targetWindow to window {quoted_title}
                            try
                                set value of attribute "AXMain" of targetWindow to true
                            end try
                            try
                                perform action "AXRaise" of targetWindow
                            end try
                            return true
                        end if
                    end tell
                end if
            end tell
            return false
            '''
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=5)
            return "true" in result.stdout.lower()
        except Exception as exc:
            self.logger.debug("Failed to raise WeChat window %r: %s", window_title, exc)
            return False

    def _get_wechat_window_bounds_by_title(self, window_title: Optional[str]) -> Optional[Dict[str, int]]:
        """Return bounds for a named WeChat child window, such as an official account page."""
        dep_manager = getattr(self, "dep_manager", None)
        if not window_title or not dep_manager:
            return None
        quartz_window = self._find_wechat_window_info_by_title(window_title)
        if quartz_window and self._looks_like_article_content_window_bounds(quartz_window["bounds"]):
            return quartz_window["bounds"]
        if quartz_window:
            self.logger.info(
                "Ignoring tiny titled WeChat window for %s: %s",
                window_title,
                quartz_window["bounds"],
            )
        try:
            subprocess = dep_manager.get_dependency("subprocess")
            if not subprocess:
                return None
            quoted_title = self._applescript_string(window_title)
            script = f'''
            tell application "System Events"
                if exists process "WeChat" then
                    tell process "WeChat"
                        if exists window {quoted_title} then
                            set p to position of window {quoted_title}
                            set s to size of window {quoted_title}
                            return (item 1 of p as string) & "," & (item 2 of p as string) & "," & (item 1 of s as string) & "," & (item 2 of s as string)
                        end if
                    end tell
                end if
            end tell
            return ""
            '''
            result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=5)
            parts = [part.strip() for part in result.stdout.strip().split(",") if part.strip()]
            if len(parts) != 4:
                return None
            x, y, width, height = [int(float(part)) for part in parts]
            if width <= 0 or height <= 0:
                return None
            resolved_bounds = {"X": x, "Y": y, "Width": width, "Height": height}
            if not self._looks_like_article_content_window_bounds(resolved_bounds):
                self.logger.info(
                    "Ignoring tiny AppleScript WeChat window for %s: %s",
                    window_title,
                    resolved_bounds,
                )
                return None
            quartz_match = self._find_wechat_window_info_by_bounds(
                resolved_bounds,
                preferred_name=window_title,
            )
            if quartz_match:
                return quartz_match["bounds"]
            return self._attach_window_capture_metadata(resolved_bounds)
        except Exception as exc:
            self.logger.debug("Failed to get WeChat window %r bounds: %s", window_title, exc)
            return None

    def _looks_like_article_content_window_bounds(self, bounds: Optional[Dict[str, Any]]) -> bool:
        normalized = self._normalize_capture_bounds(bounds)
        if not normalized:
            return False
        return normalized["Width"] >= 320 and normalized["Height"] >= 220

    def _official_account_article_list_bounds(self, window_bounds: Dict[str, int]) -> Dict[str, int]:
        """Return the scrollable article-card area inside a public-account child window."""
        top_offset = max(78, int(window_bounds["Height"] * 0.12))
        bottom_offset = max(72, int(window_bounds["Height"] * 0.11))
        usable_height = max(1, window_bounds["Height"] - top_offset - bottom_offset)
        article_bounds = {
            "X": int(window_bounds["X"]),
            "Y": int(window_bounds["Y"] + top_offset),
            "Width": int(window_bounds["Width"]),
            "Height": int(usable_height),
        }
        window_id = window_bounds.get("_window_id") if isinstance(window_bounds, dict) else None
        window_capture_bounds = window_bounds.get("_window_bounds") if isinstance(window_bounds, dict) else None
        return self._attach_window_capture_metadata(
            article_bounds,
            window_id=window_id,
            window_bounds=window_capture_bounds or window_bounds,
        ) or article_bounds

    def _resolve_article_panel_bounds(
        self,
        base_bounds: Dict[str, int],
        account_name: Optional[str] = None,
    ) -> Dict[str, int]:
        """Resolve the real article list bounds after WeChat opens an official-account window."""
        if account_name:
            self._raise_wechat_window_by_title(account_name)
            named_bounds = self._get_wechat_window_bounds_by_title(account_name)
            if named_bounds:
                article_bounds = self._official_account_article_list_bounds(named_bounds)
                self.logger.info(
                    "Using official-account child window for article list: window=%s article_bounds=%s",
                    named_bounds,
                    article_bounds,
                )
                return article_bounds

        front_bounds = self._get_frontmost_wechat_window_bounds()
        if front_bounds and (
            abs(front_bounds["X"] - base_bounds["X"]) > 20
            or abs(front_bounds["Y"] - base_bounds["Y"]) > 20
            or front_bounds["Width"] < int(base_bounds["Width"] * 0.85)
        ):
            article_bounds = self._official_account_article_list_bounds(front_bounds)
            self.logger.info(
                "Using front WeChat child window for article list: window=%s article_bounds=%s",
                front_bounds,
                article_bounds,
            )
            return article_bounds

        article_bounds = self._right_article_panel_bounds(base_bounds)
        self.logger.info("Using main-window article panel fallback: %s", article_bounds)
        return article_bounds

    def _resolve_search_surface_bounds(
        self,
        base_bounds: Dict[str, int],
        *,
        allow_small_child: bool = False,
        account_name: Optional[str] = None,
    ) -> Dict[str, int]:
        """Prefer the current front WeChat child window when search jumps into a dedicated panel."""
        front_bounds = self._get_frontmost_wechat_window_bounds()
        if not front_bounds:
            if allow_small_child:
                candidate_bounds = self._find_wechat_search_panel_window_bounds(base_bounds)
                if candidate_bounds:
                    return candidate_bounds
            return base_bounds

        candidate_bounds = None
        if allow_small_child:
            candidate_bounds = self._find_wechat_search_panel_window_bounds(base_bounds)

        front_window_info = self._find_wechat_window_info_by_bounds(front_bounds)
        front_window_name = (front_window_info or {}).get("name") or ""

        if self._bounds_roughly_match(front_bounds, base_bounds):
            if candidate_bounds:
                return candidate_bounds
            return base_bounds

        if allow_small_child and self._looks_like_official_accounts_entry(front_window_name):
            self.logger.info(
                "Ignoring front WeChat child window as search surface because title looks like an official-accounts surface: %r",
                front_window_name,
            )
            if candidate_bounds:
                return candidate_bounds
            return base_bounds

        if allow_small_child and self._looks_like_opened_account_window_title(
            front_window_name,
            account_name=account_name,
        ):
            self.logger.info(
                "Ignoring front WeChat child window as search surface because title looks like an opened account window: %r",
                front_window_name,
            )
            if candidate_bounds:
                return candidate_bounds
            return base_bounds

        if (
            allow_small_child
            and candidate_bounds
            and self._bounds_roughly_match(candidate_bounds, base_bounds)
        ):
            self.logger.info(
                "Keeping dedicated search surface instead of larger front WeChat window: base=%s front=%s",
                base_bounds,
                front_bounds,
            )
            return candidate_bounds

        if allow_small_child and candidate_bounds:
            front_area = float(front_bounds["Width"]) * float(front_bounds["Height"])
            candidate_area = float(candidate_bounds["Width"]) * float(candidate_bounds["Height"])
            candidate_significantly_larger = (
                candidate_area > (front_area * 1.35)
                and float(candidate_bounds["Width"]) > (float(front_bounds["Width"]) * 1.2)
            )
            if candidate_significantly_larger:
                self.logger.info(
                    "Keeping dedicated search surface instead of smaller front WeChat popup: candidate=%s front=%s",
                    candidate_bounds,
                    front_bounds,
                )
                return candidate_bounds

        min_child_width = max(self._scale_window_x(base_bounds, 260), int(base_bounds["Width"] * 0.42))
        min_child_height = max(self._scale_window_y(base_bounds, 280), int(base_bounds["Height"] * 0.5))
        if (
            not allow_small_child
            and (front_bounds["Width"] < min_child_width or front_bounds["Height"] < min_child_height)
        ):
            self.logger.info(
                "Ignoring front WeChat child window as search surface because it is too small: %s",
                front_bounds,
            )
            return base_bounds

        self.logger.info(
            "Using front WeChat child window as search surface: base=%s child=%s",
            base_bounds,
            front_bounds,
        )
        return front_bounds

    def _find_wechat_search_panel_window_bounds(
        self,
        base_bounds: Dict[str, int],
    ) -> Optional[Dict[str, int]]:
        """Pick a likely dedicated search panel from WeChat's Quartz window candidates."""
        lookup_manager, quartz = self._get_wechat_quartz_lookup_source()
        if not lookup_manager or not quartz:
            return None

        try:
            profile = lookup_manager._get_profile("WeChat")
            candidates = lookup_manager._collect_window_candidates(
                quartz,
                profile,
                quartz.kCGWindowListOptionAll,
                "all_windows_search_panel",
            )
        except Exception as exc:
            self.logger.debug("Failed to scan WeChat child window candidates for search panel: %s", exc)
            return None

        base_x = float(base_bounds["X"])
        base_y = float(base_bounds["Y"])
        base_width = float(base_bounds["Width"])
        base_height = float(base_bounds["Height"])
        min_width = max(self._scale_window_x(base_bounds, 300), int(base_width * 0.34))
        min_height = max(self._scale_window_y(base_bounds, 300), int(base_height * 0.55))
        preferred_right_edge = base_x + (base_width * 0.2)
        preferred_top_edge = base_y + (base_height * 0.18)
        max_width = int(base_width * 0.82)
        max_height = int(base_height * 1.02)

        def overlap_ratio(bounds: Dict[str, float]) -> float:
            left = max(base_x, float(bounds["X"]))
            top = max(base_y, float(bounds["Y"]))
            right = min(base_x + base_width, float(bounds["X"]) + float(bounds["Width"]))
            bottom = min(base_y + base_height, float(bounds["Y"]) + float(bounds["Height"]))
            if right <= left or bottom <= top:
                return 0.0
            overlap_area = (right - left) * (bottom - top)
            candidate_area = max(1.0, float(bounds["Width"]) * float(bounds["Height"]))
            return overlap_area / candidate_area

        viable_candidates: List[Dict[str, Any]] = []
        for candidate in candidates:
            bounds = candidate.get("bounds") or {}
            width = float(bounds.get("Width", 0) or 0)
            height = float(bounds.get("Height", 0) or 0)
            if width < min_width or height < min_height:
                continue
            if width > max_width or height > max_height:
                continue
            if self._bounds_roughly_match(bounds, base_bounds):
                continue
            if overlap_ratio(bounds) < 0.72:
                continue
            viable_candidates.append(candidate)

        if not viable_candidates:
            return None

        def candidate_score(candidate: Dict[str, Any]) -> Tuple[int, int, float, float]:
            bounds = candidate["bounds"]
            top_aligned = 1 if float(bounds["Y"]) <= preferred_top_edge else 0
            right_aligned = 1 if float(bounds["X"]) >= preferred_right_edge else 0
            return (
                top_aligned,
                right_aligned,
                min(float(bounds["Height"]) / max(1.0, base_height), 1.0),
                float(candidate.get("area") or 0.0),
            )

        best_candidate = max(viable_candidates, key=candidate_score)
        self.logger.info(
            "Using Quartz child window candidate as dedicated search surface: owner=%s name=%r id=%s bounds=%s",
            best_candidate.get("owner"),
            best_candidate.get("name"),
            best_candidate.get("window_id"),
            best_candidate.get("bounds"),
        )
        bounds = self._window_info_from_candidate(best_candidate)
        if bounds:
            return bounds["bounds"]
        return self._normalize_capture_bounds(best_candidate.get("bounds"))

    async def _scroll_article_list_to_top(
        self,
        article_window_title: Optional[str] = None,
        bounds: Optional[Dict[str, int]] = None,
    ) -> None:
        """Reset the official-account article list to its latest/top position."""
        try:
            if article_window_title:
                self._raise_wechat_window_by_title(article_window_title)
            elif not self._ensure_wechat_frontmost(activate=False):
                self._ensure_wechat_frontmost(activate=True)
            pyautogui = self.dep_manager.get_dependency("pyautogui") if self.dep_manager else None
            if not pyautogui:
                return
            if bounds:
                pyautogui.moveTo(
                    int(bounds["X"] + bounds["Width"] / 2),
                    int(bounds["Y"] + bounds["Height"] / 2),
                    duration=0.1,
                )
                await asyncio.sleep(0.2)
            for _ in range(8):
                pyautogui.scroll(8)
                await asyncio.sleep(0.12)
            await asyncio.sleep(0.6)
        except Exception as exc:
            self.logger.warning("滚动文章列表到顶部失败: %s", exc)

    def _close_front_auxiliary_wechat_windows(self, max_windows: int = 5) -> None:
        """Close foreground WeChat article/search windows so automation starts from the main window."""
        if not getattr(self, "dep_manager", None):
            return
        try:
            subprocess = self.dep_manager.get_dependency("subprocess")
            if not subprocess:
                return
            script = f'''
            tell application id "{self.config.wechat_bundle_id}" to activate
            delay 0.2
            tell application "System Events"
                if exists process "WeChat" then
                    tell process "WeChat"
                        repeat {max(1, int(max_windows))} times
                            if (count windows) is 0 then exit repeat
                            set frontName to name of front window
                            if frontName is "微信" or frontName is "WeChat" then exit repeat
                            keystroke "w" using command down
                            delay 0.7
                        end repeat
                    end tell
                end if
            end tell
            '''
            subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=8)
        except Exception as exc:
            self.logger.debug("Failed to close auxiliary WeChat windows: %s", exc)

    def _get_screenshot_scale(self, screenshot) -> Tuple[float, float]:
        """Map screenshot pixel coordinates back to pyautogui screen coordinates."""
        try:
            if hasattr(screenshot, "shape"):
                image_height, image_width = screenshot.shape[:2]
            elif hasattr(screenshot, "size") and isinstance(screenshot.size, tuple):
                image_width, image_height = screenshot.size
            else:
                return 1.0, 1.0

            logical_width = None
            logical_height = None
            screenshot_info = getattr(screenshot, "info", None)
            if isinstance(screenshot_info, dict):
                logical_region = screenshot_info.get("_logical_capture_region") or {}
                region_width = logical_region.get("Width")
                region_height = logical_region.get("Height")
                if isinstance(region_width, (int, float)) and isinstance(region_height, (int, float)):
                    if region_width > 0 and region_height > 0:
                        logical_width = float(region_width)
                        logical_height = float(region_height)

                if logical_width is None or logical_height is None:
                    logical_screen = screenshot_info.get("_screen_logical_size") or {}
                    screen_width = logical_screen.get("Width")
                    screen_height = logical_screen.get("Height")
                    if isinstance(screen_width, (int, float)) and isinstance(screen_height, (int, float)):
                        if screen_width > 0 and screen_height > 0:
                            logical_width = float(screen_width)
                            logical_height = float(screen_height)

            if logical_width is None or logical_height is None:
                pyautogui = self.dep_manager.get_dependency("pyautogui") if self.dep_manager else None
                if not pyautogui:
                    return 1.0, 1.0
                screen_width, screen_height = pyautogui.size()
                logical_width = float(screen_width)
                logical_height = float(screen_height)

            if logical_width <= 0 or logical_height <= 0:
                return 1.0, 1.0

            scale_x = image_width / logical_width
            scale_y = image_height / logical_height
            if scale_x < 0.5 or scale_y < 0.5:
                return 1.0, 1.0
            return scale_x, scale_y
        except Exception as exc:
            self.logger.debug("Could not determine screenshot scale: %s", exc)
            return 1.0, 1.0

    def _get_screenshot_origin(self, screenshot) -> Tuple[float, float]:
        """Return the logical top-left origin for a screenshot region."""
        screenshot_info = getattr(screenshot, "info", None)
        if isinstance(screenshot_info, dict):
            logical_region = screenshot_info.get("_logical_capture_region") or {}
            origin_x = logical_region.get("X")
            origin_y = logical_region.get("Y")
            if isinstance(origin_x, (int, float)) and isinstance(origin_y, (int, float)):
                return float(origin_x), float(origin_y)
        return 0.0, 0.0

    def _window_ui_scale(self, bounds: Optional[Dict[str, int]]) -> Tuple[float, float]:
        """Approximate WeChat UI scaling from the current window size."""
        if not bounds:
            return 1.0, 1.0
        width = max(float(bounds.get("Width") or self._REFERENCE_WINDOW_WIDTH), 1.0)
        height = max(float(bounds.get("Height") or self._REFERENCE_WINDOW_HEIGHT), 1.0)
        scale_x = min(1.6, max(0.75, width / self._REFERENCE_WINDOW_WIDTH))
        scale_y = min(1.6, max(0.75, height / self._REFERENCE_WINDOW_HEIGHT))
        return scale_x, scale_y

    def _scale_window_x(self, bounds: Optional[Dict[str, int]], pixels: float) -> int:
        scale_x, _ = self._window_ui_scale(bounds)
        return max(1, int(round(pixels * scale_x)))

    def _scale_window_y(self, bounds: Optional[Dict[str, int]], pixels: float) -> int:
        _, scale_y = self._window_ui_scale(bounds)
        return max(1, int(round(pixels * scale_y)))

    def _image_point_to_screen(self, x: float, y: float, screenshot) -> Tuple[int, int]:
        scale_x, scale_y = self._get_screenshot_scale(screenshot)
        origin_x, origin_y = self._get_screenshot_origin(screenshot)
        return int(round(origin_x + (x / scale_x))), int(round(origin_y + (y / scale_y)))

    def _ocr_position(self, result: Dict[str, Any]) -> Dict[str, float]:
        position = result.get("position") or {}
        return {
            "x": float(result.get("x", result.get("left", position.get("x", position.get("left", 0))) or 0)),
            "y": float(result.get("y", result.get("top", position.get("y", position.get("top", 0))) or 0)),
            "width": float(result.get("width", position.get("width", position.get("w", 1))) or 1),
            "height": float(result.get("height", position.get("height", position.get("h", 1))) or 1),
        }

    def _ocr_center(self, result: Dict[str, Any], screenshot) -> Tuple[int, int]:
        position = self._ocr_position(result)
        center_x = position["x"] + position["width"] / 2
        center_y = position["y"] + position["height"] / 2
        return self._image_point_to_screen(center_x, center_y, screenshot)

    def _point_in_bounds(self, x: int, y: int, bounds: Optional[Dict[str, int]]) -> bool:
        if not bounds:
            return True
        return (
            bounds["X"] <= x <= bounds["X"] + bounds["Width"]
            and bounds["Y"] <= y <= bounds["Y"] + bounds["Height"]
        )

    def _text_similarity(self, candidate: str, target: str) -> float:
        candidate_norm = "".join((candidate or "").split()).lower()
        target_norm = "".join((target or "").split()).lower()
        if not candidate_norm or not target_norm:
            return 0.0
        if candidate_norm == target_norm:
            return 1.0
        if target_norm in candidate_norm:
            return 0.95
        if len(candidate_norm) >= 2 and candidate_norm in target_norm:
            return 0.88
        return SequenceMatcher(None, candidate_norm, target_norm).ratio()

    def _find_best_ocr_text_match(
        self,
        screenshot,
        target: str,
        *,
        bounds: Optional[Dict[str, int]] = None,
        min_similarity: float = 0.68,
        min_confidence: float = 30.0,
        ocr_engine: Optional[AdaptiveOCR] = None,
    ) -> Optional[Dict[str, Any]]:
        engine = ocr_engine or getattr(self, "adaptive_ocr", None)
        if not engine:
            return None

        try:
            results = engine.recognize(screenshot, target_hint=target)
        except TypeError:
            results = engine.recognize(screenshot)
        except Exception as exc:
            self.logger.warning("OCR recognition failed while matching %r: %s", target, exc)
            return None

        candidates: List[Dict[str, Any]] = []
        for result in results:
            text = (result.get("text") or "").strip()
            confidence = float(result.get("confidence") or 0)
            if confidence < min_confidence or not text:
                continue

            position = self._ocr_position(result)
            center_x, center_y = self._ocr_center(result, screenshot)
            if not self._point_in_bounds(center_x, center_y, bounds):
                continue

            candidates.append({
                "text": text,
                "confidence": confidence,
                "position": position,
                "center_x": center_x,
                "center_y": center_y,
                "raw": result,
            })

        best = None
        best_score = 0.0
        best_row_text = ""
        best_has_official_context = False
        best_has_blocked_context = False
        blocked_exact_matches: List[Dict[str, Any]] = []
        rows = self._group_ocr_candidates_by_row(candidates)
        for row in rows:
            row_text = self._ocr_row_text(row["items"])
            has_official_context, has_blocked_context = self._account_result_row_context_flags(row_text)

            for candidate in row["items"]:
                text = candidate["text"]
                confidence = candidate["confidence"]
                similarity = self._text_similarity(text, target)
                if similarity < min_similarity:
                    continue

                if (
                    self._is_exact_account_name_match(text, target)
                    and has_blocked_context
                    and not has_official_context
                ):
                    blocked_exact_matches.append(
                        {
                            "text": text,
                            "x": candidate["center_x"],
                            "y": candidate["center_y"],
                            "row_text": row_text,
                        }
                    )
                    continue

                score = (
                    similarity * 100
                    + confidence * 0.1
                    + (12.0 if has_official_context else 0.0)
                    - (24.0 if has_blocked_context and not has_official_context else 0.0)
                )
                if score > best_score:
                    best = {
                        "text": text,
                        "x": candidate["center_x"],
                        "y": candidate["center_y"],
                        "confidence": confidence,
                        "similarity": similarity,
                        "raw": candidate["raw"],
                        "row_text": row_text,
                    }
                    best_score = score
                    best_row_text = row_text
                    best_has_official_context = has_official_context
                    best_has_blocked_context = has_blocked_context

        line_match = self._find_best_ocr_line_match(
            candidates,
            target,
            screenshot,
            min_similarity=min_similarity,
        )
        if line_match and float(line_match.get("score") or 0) > best_score:
            best = line_match
            best_row_text = line_match.get("row_text", "")
            best_has_official_context = bool(line_match.get("has_official_context"))
            best_has_blocked_context = bool(line_match.get("has_blocked_context"))

        if blocked_exact_matches:
            self.logger.info(
                "Blocked exact OCR match(es) for %r due to non-official row context: %s",
                target,
                blocked_exact_matches,
            )
        if best:
            self.logger.info(
                "Selected OCR match for %r: text=%r at (%s, %s), similarity=%.2f, confidence=%.1f, official_context=%s, blocked_context=%s, row=%r",
                target,
                best.get("text"),
                best.get("x"),
                best.get("y"),
                float(best.get("similarity") or 0.0),
                float(best.get("confidence") or 0.0),
                best_has_official_context,
                best_has_blocked_context,
                best_row_text,
            )

        return best

    def _group_ocr_candidates_by_row(
        self,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not candidates:
            return []

        heights = [max(1.0, float(c["position"].get("height") or 1)) for c in candidates]
        row_threshold = max(10.0, statistics.median(heights) * 0.9)
        rows: List[Dict[str, Any]] = []

        for candidate in sorted(candidates, key=lambda c: (
            c["position"]["y"] + c["position"]["height"] / 2,
            c["position"]["x"],
        )):
            position = candidate["position"]
            center_y = position["y"] + position["height"] / 2
            row = next(
                (
                    item for item in rows
                    if abs(float(item["center_y"]) - center_y) <= row_threshold
                ),
                None,
            )
            if row is None:
                rows.append({"center_y": center_y, "items": [candidate]})
            else:
                row["items"].append(candidate)
                row["center_y"] = statistics.mean(
                    item["position"]["y"] + item["position"]["height"] / 2
                    for item in row["items"]
                )
        return rows

    def _ocr_row_text(self, items: List[Dict[str, Any]]) -> str:
        ordered_items = sorted(items, key=lambda c: c["position"]["x"])
        compact_text = "".join(item["text"] for item in ordered_items)
        spaced_text = " ".join(item["text"] for item in ordered_items)
        return f"{compact_text} {spaced_text}".strip()

    def _account_result_row_context_flags(self, row_text: str) -> Tuple[bool, bool]:
        normalized = (row_text or "").strip().lower()
        if not normalized:
            return False, False

        official_account_terms = (
            "公众号",
            "订阅号",
            "服务号",
            "官方账号",
            "account",
        )
        non_account_result_terms = (
            "文章",
            "视频号",
            "朋友圈",
            "小程序",
            "mini program",
            "encyclopedia",
            "媒体",
            "media",
            "聊天记录",
            "会话记录",
            "发送人",
            "日期",
            "进入聊天",
            "聊天文件",
            "pdf",
            "文件",
        )
        has_official_context = any(term in normalized for term in official_account_terms)
        has_blocked_context = any(term in normalized for term in non_account_result_terms)
        return has_official_context, has_blocked_context

    def _find_best_ocr_line_match(
        self,
        candidates: List[Dict[str, Any]],
        target: str,
        screenshot,
        *,
        min_similarity: float,
    ) -> Optional[Dict[str, Any]]:
        """Match text split across OCR boxes by reconstructing visible result rows."""
        if not candidates:
            return None

        rows = self._group_ocr_candidates_by_row(candidates)
        best = None
        best_score = 0.0

        for row in rows:
            items = sorted(row["items"], key=lambda c: c["position"]["x"])
            compact_text = "".join(item["text"] for item in items)
            spaced_text = " ".join(item["text"] for item in items)
            similarity = max(
                self._text_similarity(compact_text, target),
                self._text_similarity(spaced_text, target),
            )
            if similarity < min_similarity:
                continue

            confidence = statistics.mean(item["confidence"] for item in items)
            row_text = f"{compact_text} {spaced_text}"
            has_official_context, has_blocked_context = self._account_result_row_context_flags(row_text)
            score = (
                similarity * 100
                + confidence * 0.1
                + (12.0 if has_official_context else 0.0)
                - (24.0 if has_blocked_context and not has_official_context else 0.0)
            )

            left = min(item["position"]["x"] for item in items)
            top = min(item["position"]["y"] for item in items)
            right = max(item["position"]["x"] + item["position"]["width"] for item in items)
            bottom = max(item["position"]["y"] + item["position"]["height"] for item in items)
            center_x, center_y = self._image_point_to_screen(
                left + (right - left) / 2,
                top + (bottom - top) / 2,
                screenshot,
            )

            if score > best_score:
                best = {
                    "text": spaced_text,
                    "x": center_x,
                    "y": center_y,
                    "confidence": confidence,
                    "similarity": similarity,
                    "score": score,
                    "raw": [item["raw"] for item in items],
                    "row_text": row_text,
                    "has_official_context": has_official_context,
                    "has_blocked_context": has_blocked_context,
                }
                best_score = score

        return best

    def _account_result_ocr_fallback_enabled(self) -> bool:
        value = os.getenv("WECHAT_RESULT_OCR_FALLBACK", "true").strip().lower()
        return value not in {"0", "false", "no", "off"}

    def _get_account_result_ocr_engine(self) -> Optional[AdaptiveOCR]:
        """Create a scoped OCR engine for exact account-result selection."""
        adaptive_ocr = getattr(self, "adaptive_ocr", None)
        if adaptive_ocr:
            return adaptive_ocr
        ocr_processor = getattr(self, "ocr_processor", None)
        if not ocr_processor or not self._account_result_ocr_fallback_enabled():
            return None

        cached = getattr(self, "_account_result_ocr_engine", None)
        if cached:
            return cached

        try:
            cached = AdaptiveOCR(ocr_processor)
            self._account_result_ocr_engine = cached
            self.logger.info("Initialized scoped OCR fallback for WeChat account result selection")
            return cached
        except Exception as exc:
            self.logger.warning("Could not initialize scoped account-result OCR fallback: %s", exc)
            return None

    def _screenshot_region_changed(
        self,
        before,
        after,
        region: Dict[str, int],
        *,
        mean_threshold: float = 2.0,
        pixel_threshold: float = 0.01,
    ) -> bool:
        """Detect whether a logical screen region changed between screenshots."""
        if before is None or after is None:
            return False
        try:
            import numpy as np

            before_array = np.array(before)
            after_array = np.array(after)
            scale_x, scale_y = self._get_screenshot_scale(after)
            x = max(0, int(round(region["X"] * scale_x)))
            y = max(0, int(round(region["Y"] * scale_y)))
            width = max(1, int(round(region["Width"] * scale_x)))
            height = max(1, int(round(region["Height"] * scale_y)))
            max_height, max_width = after_array.shape[:2]
            right = min(max_width, x + width)
            bottom = min(max_height, y + height)
            if right <= x or bottom <= y:
                return False

            before_crop = before_array[y:bottom, x:right]
            after_crop = after_array[y:bottom, x:right]
            if before_crop.shape != after_crop.shape or before_crop.size == 0:
                return False

            diff = np.abs(after_crop.astype("float32") - before_crop.astype("float32"))
            if diff.ndim == 3:
                pixel_diff = diff.max(axis=2)
            else:
                pixel_diff = diff
            mean_delta = float(pixel_diff.mean())
            changed_ratio = float((pixel_diff > 24).mean())
            self.logger.debug(
                "Search input visual delta: mean=%.2f changed_ratio=%.4f region=%s",
                mean_delta,
                changed_ratio,
                region,
            )
            return mean_delta >= mean_threshold or changed_ratio >= pixel_threshold
        except Exception as exc:
            self.logger.debug("Search input visual-change check failed: %s", exc)
            return False

    def _search_input_text_region(self, bounds: Dict[str, int]) -> Dict[str, int]:
        """Return the visible text area inside WeChat's sidebar search input."""
        region = {
            "X": bounds["X"] + max(self._scale_window_x(bounds, 92), int(bounds["Width"] * 0.10)),
            "Y": bounds["Y"] + self._scale_window_y(bounds, 12),
            "Width": max(
                self._scale_window_x(bounds, 120),
                min(self._scale_window_x(bounds, 320), int(bounds["Width"] * 0.30)),
            ),
            "Height": self._scale_window_y(bounds, 42),
        }
        return self._inherit_window_capture_metadata(region, bounds) or region

    def _search_input_query_pixels_present(
        self,
        screenshot,
        bounds: Dict[str, int],
        account_name: str,
    ) -> bool:
        """Verify the search input contains real typed text, not just placeholder UI."""
        if screenshot is None:
            return False

        try:
            import numpy as np

            region = {
                "X": bounds["X"] + max(self._scale_window_x(bounds, 98), int(bounds["Width"] * 0.104)),
                "Y": bounds["Y"] + self._scale_window_y(bounds, 18),
                "Width": max(
                    self._scale_window_x(bounds, 80),
                    min(self._scale_window_x(bounds, 220), len(account_name.strip()) * self._scale_window_x(bounds, 26)),
                ),
                "Height": self._scale_window_y(bounds, 24),
            }
            x, y, width, height = self._logical_region_to_pixels(region, screenshot)
            image = np.array(screenshot)
            max_height, max_width = image.shape[:2]
            right = min(max_width, x + width)
            bottom = min(max_height, y + height)
            if right <= x or bottom <= y:
                return False

            crop = image[y:bottom, x:right]
            if crop.ndim < 3 or crop.size == 0:
                return False
            if crop.shape[2] > 3:
                crop = crop[:, :, :3]

            rgb = crop.astype("int16")
            red = rgb[:, :, 0]
            green = rgb[:, :, 1]
            blue = rgb[:, :, 2]
            dark_text = (red < 130) & (green < 130) & (blue < 130)
            green_text = (green > 90) & ((green - red) > 18) & ((green - blue) > 12)
            text_pixels = int((dark_text | green_text).sum())
            ratio = text_pixels / max(int(crop.shape[0] * crop.shape[1]), 1)
            min_pixels = max(40, min(260, len(account_name.strip()) * 28))
            self.logger.debug(
                "Search input query pixel verification: pixels=%s ratio=%.4f min=%s region=%s",
                text_pixels,
                ratio,
                min_pixels,
                region,
            )
            return text_pixels >= min_pixels and ratio >= 0.018
        except Exception as exc:
            self.logger.debug("Search input query pixel verification failed: %s", exc)
            return False

    def _refocus_search_input(self, bounds: Optional[Dict[str, int]]) -> bool:
        """Re-focus the WeChat search input using scaled window-relative coordinates."""
        if not bounds:
            return False

        input_region = self._search_input_text_region(bounds)
        click_x = int(
            input_region["X"] + min(
                max(self._scale_window_x(bounds, 24), int(input_region["Width"] * 0.18)),
                max(12, input_region["Width"] - 12),
            )
        )
        click_y = int(input_region["Y"] + input_region["Height"] / 2)
        self.logger.info(
            "Refocusing WeChat search input at (%s, %s) using scaled input region %s",
            click_x,
            click_y,
            input_region,
        )
        click_result = self.click_at(click_x, click_y)
        return click_result.status == AutomationStatus.SUCCESS

    def _logical_region_to_pixels(self, region: Dict[str, int], screenshot) -> Tuple[int, int, int, int]:
        scale_x, scale_y = self._get_screenshot_scale(screenshot)
        origin_x, origin_y = self._get_screenshot_origin(screenshot)
        x = max(0, int(round((region["X"] - origin_x) * scale_x)))
        y = max(0, int(round((region["Y"] - origin_y) * scale_y)))
        width = max(1, int(round(region["Width"] * scale_x)))
        height = max(1, int(round(region["Height"] * scale_y)))
        return x, y, width, height

    def _normalize_capture_bounds(self, bounds: Optional[Dict[str, Any]]) -> Optional[Dict[str, int]]:
        if not isinstance(bounds, dict):
            return None
        try:
            return {
                "X": int(round(float(bounds.get("X", bounds.get("x", 0)) or 0))),
                "Y": int(round(float(bounds.get("Y", bounds.get("y", 0)) or 0))),
                "Width": int(round(float(bounds.get("Width", bounds.get("width", 0)) or 0))),
                "Height": int(round(float(bounds.get("Height", bounds.get("height", 0)) or 0))),
            }
        except Exception:
            return None

    def _bounds_roughly_match(
        self,
        left: Optional[Dict[str, Any]],
        right: Optional[Dict[str, Any]],
        *,
        position_tolerance: int = 48,
        size_tolerance: int = 96,
    ) -> bool:
        normalized_left = self._normalize_capture_bounds(left)
        normalized_right = self._normalize_capture_bounds(right)
        if not normalized_left or not normalized_right:
            return False
        return (
            abs(normalized_left["X"] - normalized_right["X"]) <= position_tolerance
            and abs(normalized_left["Y"] - normalized_right["Y"]) <= position_tolerance
            and abs(normalized_left["Width"] - normalized_right["Width"]) <= size_tolerance
            and abs(normalized_left["Height"] - normalized_right["Height"]) <= size_tolerance
        )

    def _get_wechat_window_capture_info(
        self,
        expected_bounds: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        window_info = None
        try:
            if hasattr(self.window_manager, "get_window_info"):
                window_info = self.window_manager.get_window_info("WeChat")
        except Exception as exc:
            self.logger.debug("Failed to get WeChat window info from bridge: %s", exc)

        if window_info is None:
            legacy_window_manager = getattr(self.window_manager, "_legacy_wm", None)
            try:
                if legacy_window_manager and hasattr(legacy_window_manager, "get_window_info"):
                    window_info = legacy_window_manager.get_window_info("WeChat")
            except Exception as exc:
                self.logger.debug("Failed to get WeChat window info from legacy manager: %s", exc)

        if not window_info:
            return None

        normalized_bounds = self._normalize_capture_bounds(window_info.get("bounds"))
        if not normalized_bounds:
            return None

        if expected_bounds and not self._bounds_roughly_match(normalized_bounds, expected_bounds):
            self.logger.debug(
                "Window capture bounds mismatch; expected=%s actual=%s window_id=%s",
                expected_bounds,
                normalized_bounds,
                window_info.get("window_id"),
            )
            return None

        window_id = int(window_info.get("window_id") or 0)
        if window_id <= 0:
            return None

        return {
            "window_id": window_id,
            "bounds": normalized_bounds,
        }

    def _prepare_window_capture_region(
        self,
        region: Optional[Dict[str, int]],
        *,
        expected_bounds: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, int]]:
        if region is None:
            return None
        capture_region = dict(region)
        existing_window_id = int(capture_region.get("_window_id") or capture_region.get("window_id") or 0)
        existing_window_bounds = self._normalize_capture_bounds(
            capture_region.get("_window_bounds") or capture_region.get("window_bounds")
        )
        if existing_window_id > 0 and existing_window_bounds:
            capture_region["_window_id"] = existing_window_id
            capture_region["_window_bounds"] = existing_window_bounds
            return capture_region
        window_info = self._get_wechat_window_capture_info(expected_bounds)
        if window_info:
            capture_region["_window_id"] = window_info["window_id"]
            capture_region["_window_bounds"] = window_info["bounds"]
        return capture_region

    def _capture_region_screenshot(
        self,
        region: Dict[str, int],
        *,
        expected_bounds: Optional[Dict[str, Any]] = None,
    ):
        ocr_processor = getattr(self, "ocr_processor", None)
        if not ocr_processor:
            return None
        capture_region = self._prepare_window_capture_region(region, expected_bounds=expected_bounds)
        return ocr_processor.capture_screenshot(region=capture_region)

    def _capture_window_screenshot(
        self,
        bounds: Optional[Dict[str, int]] = None,
    ):
        ocr_processor = getattr(self, "ocr_processor", None)
        if not ocr_processor:
            return None
        normalized_bounds = self._normalize_capture_bounds(bounds) if bounds else None
        if normalized_bounds:
            return self._capture_region_screenshot(
                normalized_bounds,
                expected_bounds=normalized_bounds,
            )
        return ocr_processor.capture_screenshot()

    def _official_account_result_region(self, bounds: Dict[str, int]) -> Dict[str, int]:
        """Return the result band for the public-account section only."""
        overlay_bounds = self._search_results_overlay_bounds(bounds)
        x = overlay_bounds["X"] + max(self._scale_window_x(bounds, 28), int(bounds["Width"] * 0.03))
        y = bounds["Y"] + max(self._scale_window_y(bounds, 58), int(bounds["Height"] * 0.075))
        right = min(
            overlay_bounds["X"] + overlay_bounds["Width"],
            x + max(
                self._scale_window_x(bounds, 260),
                min(self._scale_window_x(bounds, 620), int(bounds["Width"] * 0.66)),
            ),
        )
        bottom = min(
            bounds["Y"] + bounds["Height"],
            y + max(
                self._scale_window_y(bounds, 86),
                min(self._scale_window_y(bounds, 148), int(bounds["Height"] * 0.18)),
            ),
        )
        region = {
            "X": int(x),
            "Y": int(y),
            "Width": max(1, int(right - x)),
            "Height": max(1, int(bottom - y)),
        }
        return self._inherit_window_capture_metadata(region, bounds) or region

    def _classify_search_results_section_header(self, text: str) -> Optional[str]:
        snippet = (text or "").strip()
        normalized = snippet.lower()
        if not normalized:
            return None

        if normalized in {"official accounts", "service accounts"} or snippet in {"公众号", "订阅号", "服务号"}:
            return "official_accounts"
        if normalized in {"internet search results"} or snippet in {"搜索结果", "综合搜索"}:
            return "internet_search_results"
        if (
            "recently used mini programs" in normalized
            or "mini programs" in normalized
            or snippet in {"最近使用的小程序", "小程序"}
            or "最近使用" in snippet
        ):
            return "mini_programs"
        if "chat history" in normalized or snippet in {"聊天记录", "会话记录"}:
            return "chat_history"
        return None

    def _resolve_official_accounts_preview_region(
        self,
        bounds: Dict[str, int],
        search_region: Dict[str, int],
        ocr_engine: Optional[AdaptiveOCR] = None,
    ) -> Dict[str, int]:
        """Detect the concrete Official Accounts section inside the mixed search overlay."""
        fallback = self._inherit_window_capture_metadata(dict(search_region), bounds) or dict(search_region)
        screenshot = self._capture_region_screenshot(search_region, expected_bounds=bounds)
        engine = ocr_engine or self._get_account_result_ocr_engine() or getattr(self, "adaptive_ocr", None)
        if screenshot is None or not engine:
            return fallback

        try:
            results = engine.recognize(screenshot, target_hint="Official Accounts")
        except TypeError:
            results = engine.recognize(screenshot)
        except Exception as exc:
            self.logger.warning("Failed to OCR search-result sections: %s", exc)
            return fallback

        headers: List[Dict[str, Any]] = []
        for result in results:
            text = (result.get("text") or "").strip()
            confidence = float(result.get("confidence") or 0.0)
            if confidence < 18.0 or not text:
                continue
            kind = self._classify_search_results_section_header(text)
            if not kind:
                continue
            position = self._ocr_position(result)
            _, top_y = self._image_point_to_screen(position["x"], position["y"], screenshot)
            _, bottom_y = self._image_point_to_screen(
                position["x"] + position["width"],
                position["y"] + position["height"],
                screenshot,
            )
            headers.append(
                {
                    "kind": kind,
                    "text": text,
                    "top": int(top_y),
                    "bottom": int(max(top_y, bottom_y)),
                }
            )

        official_headers = sorted(
            [header for header in headers if header["kind"] == "official_accounts"],
            key=lambda header: (header["top"], header["bottom"]),
        )
        if not official_headers:
            return fallback

        official_header = official_headers[0]
        lower_headers = sorted(
            [
                header
                for header in headers
                if header["top"] > official_header["bottom"]
                and header["kind"] in {"mini_programs", "chat_history"}
            ],
            key=lambda header: (header["top"], header["bottom"]),
        )

        padding_top = max(8, self._scale_window_y(bounds, 6))
        padding_bottom = max(8, self._scale_window_y(bounds, 10))
        top = max(search_region["Y"] + 4, official_header["bottom"] + padding_top)
        bottom = (
            min(search_region["Y"] + search_region["Height"] - 4, lower_headers[0]["top"] - padding_bottom)
            if lower_headers
            else search_region["Y"] + search_region["Height"] - 4
        )
        if bottom <= top:
            return fallback

        region = {
            "X": int(search_region["X"]),
            "Y": int(top),
            "Width": int(search_region["Width"]),
            "Height": int(bottom - top),
        }
        resolved = self._inherit_window_capture_metadata(region, bounds) or region
        self.logger.info("Resolved Official Accounts preview region: %s", resolved)
        return resolved

    def _extract_region_ocr_texts(
        self,
        bounds: Dict[str, int],
        *,
        min_confidence: float = 20.0,
    ) -> List[str]:
        """OCR a logical region and return text snippets that still map inside it."""
        if not getattr(self, "ocr_processor", None):
            return []

        screenshot = self._capture_region_screenshot(bounds)
        if screenshot is None:
            return []

        texts: List[str] = []
        for result in self._recognize_text_regions(screenshot):
            text = (result.get("text") or "").strip()
            confidence = float(result.get("confidence") or 0)
            if confidence < min_confidence or not text:
                continue

            center_x, center_y = self._ocr_center(result, screenshot)
            if not self._point_in_bounds(center_x, center_y, bounds):
                continue
            texts.append(text)
        return texts

    def _has_account_name_evidence(
        self,
        texts: List[str],
        account_name: str,
        *,
        min_similarity: float = 0.68,
    ) -> bool:
        """Check whether OCR/LLM text snippets contain convincing evidence of the target account."""
        target = (account_name or "").strip()
        if not target:
            return False

        for text in texts or []:
            snippet = (text or "").strip()
            if not snippet:
                continue
            if self._is_exact_account_name_match(snippet, target):
                return True
            if target in snippet or self._text_similarity(snippet, target) >= min_similarity:
                return True
        return False

    def _dedupe_surface_texts(self, texts: List[str]) -> List[str]:
        deduped: List[str] = []
        seen = set()
        for text in texts or []:
            snippet = (text or "").strip()
            key = "".join(snippet.split()).lower()
            if not snippet or not key or key in seen:
                continue
            seen.add(key)
            deduped.append(snippet)
        return deduped

    def _classify_search_results_section_header(self, text: str) -> Optional[str]:
        snippet = (text or "").strip()
        normalized = snippet.lower()
        if not normalized:
            return None

        if normalized in {"official accounts", "service accounts"} or snippet in {"公众号", "订阅号", "服务号"}:
            return "official_accounts"
        if normalized in {"internet search results"} or snippet in {"搜索结果", "综合搜索"}:
            return "internet_search_results"
        if (
            "recently used mini programs" in normalized
            or "mini programs" in normalized
            or snippet in {"最近使用的小程序", "小程序"}
            or "最近使用" in snippet
        ):
            return "mini_programs"
        if "chat history" in normalized or snippet in {"聊天记录", "会话记录"}:
            return "chat_history"
        return None

    def _resolve_official_accounts_preview_region(
        self,
        bounds: Dict[str, int],
        search_region: Dict[str, int],
        ocr_engine: Optional[AdaptiveOCR] = None,
    ) -> Dict[str, int]:
        """Detect the concrete Official Accounts section inside the mixed search overlay."""
        fallback = self._inherit_window_capture_metadata(dict(search_region), bounds) or dict(search_region)
        screenshot = self._capture_region_screenshot(search_region, expected_bounds=bounds)
        engine = ocr_engine or self._get_account_result_ocr_engine() or getattr(self, "adaptive_ocr", None)
        if screenshot is None or not engine:
            return fallback

        try:
            results = engine.recognize(screenshot, target_hint="Official Accounts")
        except TypeError:
            results = engine.recognize(screenshot)
        except Exception as exc:
            self.logger.warning("Failed to OCR search-result sections: %s", exc)
            return fallback

        headers: List[Dict[str, Any]] = []
        for result in results:
            text = (result.get("text") or "").strip()
            confidence = float(result.get("confidence") or 0.0)
            if confidence < 18.0 or not text:
                continue
            kind = self._classify_search_results_section_header(text)
            if not kind:
                continue
            position = self._ocr_position(result)
            _, top_y = self._image_point_to_screen(position["x"], position["y"], screenshot)
            _, bottom_y = self._image_point_to_screen(
                position["x"] + position["width"],
                position["y"] + position["height"],
                screenshot,
            )
            headers.append(
                {
                    "kind": kind,
                    "text": text,
                    "top": int(top_y),
                    "bottom": int(max(top_y, bottom_y)),
                }
            )

        official_headers = sorted(
            [header for header in headers if header["kind"] == "official_accounts"],
            key=lambda header: (header["top"], header["bottom"]),
        )
        if not official_headers:
            return fallback

        official_header = official_headers[0]
        lower_headers = sorted(
            [
                header
                for header in headers
                if header["top"] > official_header["bottom"]
                and header["kind"] in {"mini_programs", "chat_history"}
            ],
            key=lambda header: (header["top"], header["bottom"]),
        )

        padding_top = max(8, self._scale_window_y(bounds, 6))
        padding_bottom = max(8, self._scale_window_y(bounds, 10))
        top = max(search_region["Y"] + 4, official_header["bottom"] + padding_top)
        bottom = (
            min(search_region["Y"] + search_region["Height"] - 4, lower_headers[0]["top"] - padding_bottom)
            if lower_headers
            else search_region["Y"] + search_region["Height"] - 4
        )
        if bottom <= top:
            return fallback

        region = {
            "X": int(search_region["X"]),
            "Y": int(top),
            "Width": int(search_region["Width"]),
            "Height": int(bottom - top),
        }
        resolved = self._inherit_window_capture_metadata(region, bounds) or region
        self.logger.info("Resolved Official Accounts preview region: %s", resolved)
        return resolved

    def _collect_region_surface_texts(
        self,
        bounds: Dict[str, int],
        *,
        min_confidence: float = 20.0,
        allowed_roles: Optional[List[str]] = None,
    ) -> List[str]:
        texts: List[str] = []
        accessibility_service = getattr(self, "accessibility_service", None)
        if accessibility_service:
            try:
                texts.extend(
                    accessibility_service.collect_texts(
                        region=bounds,
                        allowed_roles=allowed_roles,
                    )
                )
            except Exception as exc:
                self.logger.debug("Accessibility text collection failed for %s: %s", bounds, exc)

        texts.extend(
            self._extract_region_ocr_texts(
                bounds,
                min_confidence=min_confidence,
            )
        )
        return self._dedupe_surface_texts(texts)

    def _collect_region_ocr_surface_texts(
        self,
        bounds: Dict[str, int],
        *,
        min_confidence: float = 18.0,
    ) -> List[str]:
        """Collect strictly region-bounded OCR texts without accessibility spillover."""
        return self._dedupe_surface_texts(
            self._extract_region_ocr_texts(
                bounds,
                min_confidence=min_confidence,
            )
        )

    def _click_wechat_named_entry(
        self,
        bounds: Dict[str, int],
        labels: List[str],
        *,
        region: Optional[Dict[str, int]] = None,
        ocr_engine: Optional[AdaptiveOCR] = None,
        min_similarity: float = 0.62,
        blocked_terms: Optional[List[str]] = None,
    ) -> bool:
        """Click a named WeChat entry using accessibility first, then OCR."""
        target_region = region or bounds
        blocked_terms = [term for term in (blocked_terms or []) if term]
        normalized_labels = [
            self._normalize_account_name_key(label)
            for label in labels
            if isinstance(label, str) and label.strip()
        ]

        def _entry_is_blocked(text: Any, *, matched_text: Any = None) -> bool:
            snippet = (text or "").strip()
            if not snippet:
                return False
            lowered = snippet.lower()
            normalized_snippet = self._normalize_account_name_key(snippet)
            normalized_match = self._normalize_account_name_key(matched_text)
            looks_like_exact_navigation_entry = (
                bool(normalized_match)
                and normalized_match in normalized_labels
                and normalized_match in normalized_snippet
                and any(
                    marker in snippet
                    for marker in (
                        "公众号",
                        "订阅号",
                        "服务号",
                        "常看的号",
                        "最近阅读",
                        "搜索指定公众号",
                        "Official Accounts",
                        "Service Accounts",
                    )
                )
            )
            if any(term.lower() in lowered for term in blocked_terms):
                if looks_like_exact_navigation_entry:
                    return False
                return True
            if re.search(r"\b\d{1,2}:\d{2}\b", snippet):
                if looks_like_exact_navigation_entry or (
                    normalized_match and normalized_match in normalized_labels
                ):
                    return False
                return True
            return False

        accessibility_service = getattr(self, "accessibility_service", None)
        if accessibility_service:
            match = accessibility_service.find_named_element(
                labels,
                region=target_region,
                allowed_roles=[
                    "axrow",
                    "axstatictext",
                    "axbutton",
                    "axgroup",
                    "row",
                    "text",
                    "button",
                    "group",
                ],
                min_similarity=min_similarity,
                blocked_terms=blocked_terms or None,
            )
            if match:
                if _entry_is_blocked(match.get("text")):
                    self.logger.info(
                        "Skipping blocked accessibility entry match %r for labels=%s",
                        match.get("text"),
                        labels,
                    )
                else:
                    self.logger.info(
                        "Matched WeChat entry '%s' via %s; click=(%s, %s)",
                        match.get("text") or labels[0],
                        match.get("method", "accessibility"),
                        match["x"],
                        match["y"],
                    )
                    invoke_named_element = getattr(accessibility_service, "invoke_named_element", None)
                    if callable(invoke_named_element) and invoke_named_element(
                        labels,
                        region=target_region,
                        allowed_roles=[
                            "axrow",
                            "axstatictext",
                            "axbutton",
                            "axgroup",
                            "row",
                            "text",
                            "button",
                            "group",
                        ],
                        min_similarity=min_similarity,
                        blocked_terms=blocked_terms or None,
                        actions=["AXPress", "AXOpen", "AXConfirm"],
                    ):
                        self.logger.info(
                            "Invoked WeChat entry '%s' via native accessibility action",
                            match.get("text") or labels[0],
                        )
                        return True
                    click_result = self._click_at_with_focus_retry(int(match["x"]), int(match["y"]))
                    return click_result.status == AutomationStatus.SUCCESS

        screenshot = self._capture_region_screenshot(target_region, expected_bounds=bounds)
        if screenshot is None:
            return False

        engine = ocr_engine or self._get_account_result_ocr_engine() or getattr(self, "adaptive_ocr", None)
        if not engine:
            return False

        for label in labels:
            match = self._find_best_ocr_text_match(
                screenshot,
                label,
                bounds=target_region,
                min_similarity=min_similarity,
                min_confidence=18,
                ocr_engine=engine,
            )
            if not match:
                continue
            if _entry_is_blocked(
                match.get("row_text") or match.get("text"),
                matched_text=match.get("text") or label,
            ):
                self.logger.info(
                    "Skipping blocked OCR entry match %r row=%r for labels=%s",
                    match.get("text") or label,
                    match.get("row_text"),
                    labels,
                )
                continue
            self.logger.info(
                "Matched WeChat entry '%s' via ocr; click=(%s, %s)",
                match.get("text") or label,
                match["x"],
                match["y"],
            )
            click_result = self._click_at_with_focus_retry(int(match["x"]), int(match["y"]))
            return click_result.status == AutomationStatus.SUCCESS

        return False

    async def _open_contacts_official_accounts_surface(
        self,
        bounds: Dict[str, int],
        ocr_engine: Optional[AdaptiveOCR],
    ) -> bool:
        """Navigate via Contacts/Official Accounts instead of relying on the mixed search overlay."""
        self.logger.info("尝试通过通讯录/订阅号专用导航进入公众号面")
        sidebar_region = {
            "X": bounds["X"],
            "Y": bounds["Y"],
            "Width": max(120, int(bounds["Width"] * 0.28)),
            "Height": bounds["Height"],
        }
        if self._click_wechat_named_entry(
            bounds,
            ["通讯录", "Contacts"],
            region=sidebar_region,
            ocr_engine=ocr_engine,
        ):
            await asyncio.sleep(0.9)

        directory_region = {
            "X": bounds["X"],
            "Y": bounds["Y"] + max(self._scale_window_y(bounds, 52), int(bounds["Height"] * 0.07)),
            "Width": min(
                max(int(bounds["Width"] * 0.42), self._scale_window_x(bounds, 280)),
                self._scale_window_x(bounds, 430),
            ),
            "Height": max(
                120,
                bounds["Height"] - max(self._scale_window_y(bounds, 52), int(bounds["Height"] * 0.07)),
            ),
        }
        if self._click_wechat_named_entry(
            bounds,
            ["订阅号", "公众号", "Service Accounts", "Official Accounts"],
            region=directory_region,
            ocr_engine=ocr_engine,
            blocked_terms=[
                "常看的号",
                "直播中",
                "最近阅读",
                "Minimized Groups",
                "Yesterday",
                "Today",
                "昨天",
                "今天",
            ],
        ):
            await asyncio.sleep(1.2)
            return True
        return False

    def _official_accounts_entry_click_point(
        self,
        bounds: Dict[str, int],
        region: Dict[str, int],
        match: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, int]:
        """Click inside the entry body, not on the OCR text baseline."""
        default_x = region["X"] + min(
            max(self._scale_window_x(bounds, 150), int(region["Width"] * 0.24)),
            max(24, region["Width"] - 24),
        )
        default_y = region["Y"] + min(
            max(self._scale_window_y(bounds, 42), int(region["Height"] * 0.42)),
            max(18, region["Height"] - 18),
        )
        if not match:
            return int(default_x), int(default_y)

        raw = match.get("raw") if isinstance(match, dict) else None
        raw_position = self._ocr_position(raw) if isinstance(raw, dict) else {}
        match_height = int(
            raw_position.get("height")
            or match.get("height")
            or self._scale_window_y(bounds, 18)
        )
        vertical_offset = max(
            8,
            min(
                max(int(round(match_height * 0.4)), self._scale_window_y(bounds, 8)),
                self._scale_window_y(bounds, 18),
            ),
        )
        click_x = min(
            max(int(match["x"]), region["X"] + 24),
            region["X"] + region["Width"] - 24,
        )
        click_y = min(
            max(int(match["y"]) + vertical_offset, region["Y"] + 18),
            region["Y"] + region["Height"] - 18,
        )
        return click_x, click_y

    def _search_result_row_click_point(
        self,
        bounds: Dict[str, int],
        region: Dict[str, int],
        match: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, int]:
        """Click the left-side body of a search-result row instead of the matched preview text."""
        default_x = region["X"] + min(
            max(self._scale_window_x(bounds, 150), int(region["Width"] * 0.22)),
            max(32, region["Width"] - 32),
        )
        default_y = region["Y"] + min(
            max(self._scale_window_y(bounds, 42), int(region["Height"] * 0.14)),
            max(18, region["Height"] - 18),
        )
        if not match:
            return int(default_x), int(default_y)

        raw = match.get("raw") if isinstance(match, dict) else None
        raw_position = self._ocr_position(raw) if isinstance(raw, dict) else {}
        match_height = int(
            raw_position.get("height")
            or match.get("height")
            or self._scale_window_y(bounds, 18)
        )
        vertical_offset = max(
            8,
            min(
                max(int(round(match_height * 0.45)), self._scale_window_y(bounds, 8)),
                self._scale_window_y(bounds, 18),
            ),
        )
        click_x = min(
            max(int(default_x), region["X"] + 24),
            region["X"] + region["Width"] - 24,
        )
        click_y = min(
            max(int(match["y"]) + vertical_offset, region["Y"] + 18),
            region["Y"] + region["Height"] - 18,
        )
        return click_x, click_y

    def _official_accounts_result_labels(self) -> Tuple[str, ...]:
        return (
            "Official Accounts",
            "Service Accounts",
            "公众号",
            "订阅号",
            "服务号",
        )

    def _looks_like_official_accounts_entry(self, text: str) -> bool:
        normalized = (text or "").strip().lower()
        if not normalized:
            return False
        if normalized in {"official accounts", "service accounts"}:
            return True
        return any(label in (text or "").strip() for label in ("公众号", "订阅号", "服务号"))

    def _looks_like_search_result_preview(self, text: str, account_name: str) -> bool:
        snippet = (text or "").strip()
        target = (account_name or "").strip()
        if not snippet or not target:
            return False
        if self._looks_like_account_landing_header(snippet, target):
            return False
        if target not in snippet and self._text_similarity(snippet, target) < 0.78:
            return False
        preview_markers = ("：", ":", "…", "...", "，", ",")
        return any(marker in snippet for marker in preview_markers) and snippet != target

    def _extract_search_result_account_owner(self, text: str) -> str:
        snippet = (text or "").strip()
        if not snippet:
            return ""

        separators = (
            "：",
            ":",
            "，",
            ",",
            "…",
            "...",
            "|",
            "｜",
            "-",
            "—",
            "–",
            ".",
            "。",
            "(",
            "（",
            ")",
            "）",
            "[",
            "]",
            "【",
            "】",
            "《",
            "》",
        )
        for separator in separators:
            if separator in snippet:
                return snippet.split(separator, 1)[0].strip()

        return ""

    def _is_target_account_preview_match(self, text: str, account_name: str) -> bool:
        if not self._looks_like_search_result_preview(text, account_name):
            return False
        if self._is_exact_account_name_match(text, account_name):
            return True
        preview_owner = self._extract_search_result_account_owner(text)
        if not preview_owner:
            return False
        return self._is_exact_account_name_match(preview_owner, account_name)

    def _looks_like_mini_program_text(self, text: str) -> bool:
        snippet = (text or "").strip().lower()
        if not snippet:
            return False
        mini_program_terms = (
            "小程序",
            "mini program",
            "小游戏",
            "最近使用",
            "添加到我的小程序",
            "进入小程序",
            "打开小程序",
            "体验版",
            "去使用",
            "立即打开",
        )
        return any(term in snippet for term in mini_program_terms)

    def _canonical_account_identity_key(self, account_name: Any) -> str:
        normalized = self._normalize_account_name_key(account_name)
        if not normalized:
            return ""
        normalized = re.sub(r"[\-–—_:：\.\(\)\[\]<>]+", "", normalized)
        previous = None
        while normalized and previous != normalized:
            previous = normalized
            normalized = re.sub(
                r"(公众号|订阅号|服务号|account|accounts|article|articles|profile|媒体|officialaccount)+$",
                "",
                normalized,
            )
            normalized = re.sub(r"^(account|accounts|article|articles|profile)+", "", normalized)
            normalized = normalized.strip()
        return normalized

    def _looks_like_target_account_window_title(self, candidate_title: Any, account_name: str) -> bool:
        snippet = (candidate_title or "").strip()
        if not snippet or not account_name:
            return False
        lowered = snippet.lower()
        if not self._is_exact_account_name_match(snippet, account_name):
            return False
        return any(
            marker in lowered
            for marker in ("account", "article", "articles", "profile")
        ) or any(marker in snippet for marker in ("公众号", "订阅号", "服务号", "媒体"))

    def _looks_like_opened_account_window_title(
        self,
        candidate_title: Any,
        *,
        account_name: Optional[str] = None,
    ) -> bool:
        snippet = (candidate_title or "").strip()
        if not snippet:
            return False
        lowered = snippet.lower()
        if snippet in {"微信", "WeChat"}:
            return False
        if snippet in self._official_accounts_result_labels():
            return False
        if any(term in lowered for term in ("search", "result", "results")):
            return False
        if any(term in snippet for term in ("搜索", "搜一搜", "结果", "查找", "通讯录")):
            return False
        if account_name and self._is_exact_account_name_match(snippet, account_name):
            return True
        if account_name and self._looks_like_target_account_window_title(snippet, account_name):
            return True
        return False

    def _looks_like_account_landing_header(self, text: str, account_name: str) -> bool:
        snippet = (text or "").strip()
        if not snippet or not account_name:
            return False
        if not self._is_exact_account_name_match(snippet, account_name):
            return False
        lowered = snippet.lower()
        return any(
            marker in lowered
            for marker in ("account", "article", "articles", "profile")
        ) or any(marker in snippet for marker in ("公众号", "订阅号", "服务号", "媒体"))

    def _is_exact_account_name_match(self, candidate_text: Any, account_name: str) -> bool:
        candidate = self._normalize_account_name_key(candidate_text)
        target = self._normalize_account_name_key(account_name)
        if not candidate or not target:
            return False
        candidate_identity = self._canonical_account_identity_key(candidate_text)
        target_identity = self._canonical_account_identity_key(account_name)
        if candidate_identity and target_identity and candidate_identity == target_identity:
            return True
        return candidate == target

    def _find_official_accounts_entry_click_target(
        self,
        bounds: Dict[str, int],
        search_results_region: Dict[str, int],
        ocr_engine: Optional[AdaptiveOCR],
        *,
        official_account_region: Optional[Dict[str, int]] = None,
        detected_texts: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Return a click target for the official-account result container row."""
        search_regions: List[Dict[str, int]] = []
        if official_account_region:
            search_regions.append(official_account_region)
        if not search_regions or search_regions[-1] != search_results_region:
            search_regions.append(search_results_region)

        accessibility_service = getattr(self, "accessibility_service", None)
        entry_labels = list(self._official_accounts_result_labels())
        if accessibility_service:
            for region in search_regions:
                match = accessibility_service.find_named_element(
                    entry_labels,
                    region=region,
                    allowed_roles=[
                        "axbutton",
                        "axrow",
                        "axstatictext",
                        "axgroup",
                        "button",
                        "row",
                        "text",
                    ],
                )
                if not match:
                    continue
                click_x, click_y = self._official_accounts_entry_click_point(bounds, region, match)
                return {
                    "x": int(click_x),
                    "y": int(click_y),
                    "text": match.get("text") or "",
                    "region": region,
                    "method": "accessibility_snapshot",
                }

        ocr_processor = getattr(self, "ocr_processor", None)
        if ocr_processor and ocr_engine:
            for region in search_regions:
                results_screenshot = self._capture_region_screenshot(
                    region,
                    expected_bounds=bounds,
                )
                if results_screenshot is None:
                    continue

                for label in entry_labels:
                    match = self._find_best_ocr_text_match(
                        results_screenshot,
                        label,
                        bounds=region,
                        min_similarity=0.72,
                        min_confidence=18,
                        ocr_engine=ocr_engine,
                    )
                    if not match:
                        continue

                    click_x, click_y = self._official_accounts_entry_click_point(
                        bounds,
                        region,
                        match,
                    )
                    return {
                        "x": int(click_x),
                        "y": int(click_y),
                        "text": match.get("text") or label,
                        "region": region,
                        "method": "ocr_match",
                    }

        fallback_region = official_account_region or search_results_region
        if detected_texts and any(
            self._looks_like_official_accounts_entry(text)
            for text in detected_texts
        ):
            click_x, click_y = self._official_accounts_entry_click_point(
                bounds,
                fallback_region,
            )
            return {
                "x": int(click_x),
                "y": int(click_y),
                "text": "official_accounts_entry",
                "region": fallback_region,
                "method": "scaled_fallback",
            }

        return None

    def _search_sidebar_bounds(self, bounds: Dict[str, int]) -> Dict[str, int]:
        region = {
            "X": bounds["X"],
            "Y": bounds["Y"],
            "Width": max(120, int(bounds["Width"] * 0.48)),
            "Height": max(80, int(bounds["Height"] * 0.25)),
        }
        return self._inherit_window_capture_metadata(region, bounds) or region

    def _search_results_overlay_bounds(self, bounds: Dict[str, int]) -> Dict[str, int]:
        """Approximate WeChat's mixed-search overlay below the search box."""
        dedicated_surface_cutoff = int(self._REFERENCE_WINDOW_WIDTH * 0.72)
        if bounds["Width"] <= dedicated_surface_cutoff:
            region = {
                "X": bounds["X"],
                "Y": bounds["Y"],
                "Width": bounds["Width"],
                "Height": bounds["Height"],
            }
            return self._inherit_window_capture_metadata(region, bounds) or region

        search_input = self._search_input_text_region(bounds)
        left_padding = max(
            self._scale_window_x(bounds, 24),
            int(bounds["Width"] * 0.025),
        )
        x = max(bounds["X"], search_input["X"] - left_padding)
        overlay_width = min(
            bounds["X"] + bounds["Width"] - x,
            max(
                int(bounds["Width"] * 0.72),
                self._scale_window_x(bounds, 500),
            ),
        )
        region = {
            "X": int(x),
            "Y": bounds["Y"],
            "Width": max(120, int(overlay_width)),
            "Height": bounds["Height"],
        }
        return self._inherit_window_capture_metadata(region, bounds) or region

    def _collect_official_accounts_surface_texts(
        self,
        bounds: Dict[str, int],
        search_results_region: Dict[str, int],
        official_account_region: Optional[Dict[str, int]] = None,
    ) -> List[str]:
        texts: List[str] = []
        if official_account_region:
            texts.extend(self._collect_region_ocr_surface_texts(official_account_region, min_confidence=18.0))
        texts.extend(
            self._collect_region_ocr_surface_texts(
                search_results_region,
                min_confidence=18.0,
            )
        )
        return self._dedupe_surface_texts(texts)

    def _collect_current_official_accounts_surface_texts(
        self,
        bounds: Dict[str, int],
    ) -> Tuple[List[str], bool]:
        """Collect texts from the active Official Accounts surface, falling back to the main window when needed."""
        resolved_bounds = self._resolve_search_surface_bounds(bounds, allow_small_child=True)
        resolved_search_region = self._search_results_panel_bounds(resolved_bounds)
        resolved_official_region = self._official_account_result_region(resolved_bounds)
        texts = self._collect_official_accounts_surface_texts(
            resolved_bounds,
            resolved_search_region,
            official_account_region=resolved_official_region,
        )
        used_main_window_fallback = False
        if texts or self._bounds_roughly_match(resolved_bounds, bounds):
            return texts, used_main_window_fallback

        fallback_search_region = self._search_results_panel_bounds(bounds)
        fallback_official_region = self._official_account_result_region(bounds)
        texts = self._collect_official_accounts_surface_texts(
            bounds,
            fallback_search_region,
            official_account_region=fallback_official_region,
        )
        used_main_window_fallback = True
        return texts, used_main_window_fallback

    def _looks_like_targeted_official_accounts_context(
        self,
        texts: List[str],
        account_name: str,
    ) -> bool:
        """Detect a target-related Official Accounts context even if it is not yet the final dedicated page."""
        normalized = [(text or "").strip() for text in texts if (text or "").strip()]
        if not normalized:
            return False
        if self._looks_like_account_directory_panel(normalized, account_name):
            return True
        return (
            self._has_account_name_evidence(normalized, account_name)
            and any(self._looks_like_official_accounts_entry(text) for text in normalized)
        )

    def _looks_like_dedicated_official_accounts_surface(
        self,
        texts: List[str],
        account_name: str,
    ) -> bool:
        normalized = [(text or "").strip() for text in texts if (text or "").strip()]
        if not normalized:
            return False

        if any("Minimized Groups" in text for text in normalized):
            return False
        if self._looks_like_chat_conversation_panel(normalized):
            return False
        if self._looks_like_account_directory_panel(normalized, account_name):
            return False

        target = (account_name or "").strip()
        if not target:
            return False

        strong_target_hit = any(
            (target in text or self._text_similarity(text, target) >= 0.88)
            and not self._looks_like_search_result_preview(text, target)
            for text in normalized
        )
        if strong_target_hit:
            return True

        target_preview_hits = [
            text for text in normalized
            if target in text or self._text_similarity(text, target) >= 0.72
        ]
        if not target_preview_hits:
            return False

        return not any(
            any(term in text for term in ("Minimized Groups", "微信ClawBot AI", "定时任务", "腾讯会议"))
            for text in normalized
        )

    def _looks_like_misfocused_search_results_surface(self, texts: List[str]) -> bool:
        normalized = [(text or "").strip() for text in texts if (text or "").strip()]
        if not normalized:
            return False
        if any("Minimized Groups" in text for text in normalized):
            return True
        if any(
            any(term.lower() in text.lower() for term in ("yesterday", "photo", "jack", "聊天", "会话"))
            for text in normalized
        ) and self._looks_like_chat_conversation_panel(normalized):
            return True
        return self._looks_like_chat_conversation_panel(normalized)

    async def _ensure_official_accounts_surface_open(
        self,
        bounds: Dict[str, int],
        search_results_region: Dict[str, int],
        account_name: str,
        *,
        official_account_region: Optional[Dict[str, int]] = None,
        baseline_texts: Optional[List[str]] = None,
        press_enter_after_click: bool = False,
    ) -> bool:
        if press_enter_after_click:
            self.press_key("enter")
        await asyncio.sleep(1.2)

        texts, used_main_window_fallback = self._collect_current_official_accounts_surface_texts(bounds)
        if texts:
            log_label = "Official Accounts 主窗口校验文本" if used_main_window_fallback else "Official Accounts 切面校验文本"
            self.logger.info("%s: %s", log_label, texts[:16])
        elif used_main_window_fallback:
            self.logger.info(
                "Dedicated search surface produced no OCR text; falling back to main-window surface validation"
            )

        if baseline_texts:
            baseline_keys = {self._article_title_key(text) for text in baseline_texts if text}
            current_keys = {self._article_title_key(text) for text in texts if text}
            if baseline_keys and current_keys and baseline_keys == current_keys:
                return False

        return self._looks_like_dedicated_official_accounts_surface(texts, account_name)

    async def _open_official_accounts_search_entry(
        self,
        bounds: Dict[str, int],
        search_results_region: Dict[str, int],
        ocr_engine: Optional[AdaptiveOCR],
        account_name: str = "",
        official_account_region: Optional[Dict[str, int]] = None,
        detected_texts: Optional[List[str]] = None,
    ) -> bool:
        """Click the `Official Accounts/公众号` function entry in search results."""
        click_target = self._find_official_accounts_entry_click_target(
            bounds,
            search_results_region,
            ocr_engine,
            official_account_region=official_account_region,
            detected_texts=detected_texts,
        )
        if click_target:
            self.logger.info(
                "Matched official-accounts entry '%s' via %s; click=(%s, %s) within %s",
                click_target.get("text"),
                click_target.get("method"),
                click_target["x"],
                click_target["y"],
                click_target.get("region"),
            )
            baseline_texts = list(detected_texts or [])
            retry_points = [
                (int(click_target["x"]), int(click_target["y"]), False),
                (int(click_target["x"]), int(click_target["y"]), True),
            ]
            fallback_x, fallback_y = self._official_accounts_entry_click_point(
                bounds,
                click_target.get("region") or official_account_region or search_results_region,
            )
            if (fallback_x, fallback_y) != (int(click_target["x"]), int(click_target["y"])):
                retry_points.append((int(fallback_x), int(fallback_y), False))
                retry_points.append((int(fallback_x), int(fallback_y), True))

            for click_x, click_y, press_enter in retry_points:
                click_result = self._click_at_with_focus_retry(click_x, click_y)
                if click_result.status != AutomationStatus.SUCCESS:
                    continue
                if not account_name:
                    await asyncio.sleep(1.5)
                    return True
                opened = await self._ensure_official_accounts_surface_open(
                    bounds,
                    search_results_region,
                    account_name,
                    official_account_region=official_account_region,
                    baseline_texts=baseline_texts,
                    press_enter_after_click=press_enter,
                )
                if opened:
                    return True
                current_texts, _ = self._collect_current_official_accounts_surface_texts(bounds)
                if self._looks_like_targeted_official_accounts_context(current_texts, account_name):
                    if await self._open_target_account_from_directory_panel(bounds, account_name):
                        return True
                    if await self._open_target_account_from_official_accounts_preview(bounds, account_name):
                        return True
                    self.logger.info(
                        "Official Accounts 入口已切换到目标相关上下文，但仍未打开目标账号，停止继续重试入口: %s",
                        account_name,
                    )
                    return False
        return False

    async def _open_official_accounts_container_result(
        self,
        bounds: Dict[str, int],
        search_results_region: Dict[str, int],
        account_name: str,
        ocr_engine: Optional[AdaptiveOCR],
        *,
        official_account_region: Optional[Dict[str, int]] = None,
        detected_texts: Optional[List[str]] = None,
        allow_retry: bool = True,
    ) -> bool:
        """Open the official-account container row when the target only appears in its snippet."""
        click_target = self._find_official_accounts_entry_click_target(
            bounds,
            search_results_region,
            ocr_engine,
            official_account_region=official_account_region,
            detected_texts=detected_texts,
        )
        if not click_target:
            return False

        self.logger.info(
            "Target '%s' appears inside official-account container '%s'; clicking row via %s at (%s, %s)",
            account_name,
            click_target.get("text"),
            click_target.get("method"),
            click_target["x"],
            click_target["y"],
        )
        click_result = self._click_at_with_focus_retry(click_target["x"], click_target["y"])
        if click_result.status != AutomationStatus.SUCCESS:
            return False

        if await self._ensure_account_page_open(
            bounds,
            account_name,
            click_target["x"],
            click_target["y"],
        ):
            return True

        if not allow_retry:
            return False

        await asyncio.sleep(1.2)
        retry_bounds = self._resolve_search_surface_bounds(bounds)
        return await self._find_and_click_account_in_results(
            retry_bounds,
            account_name,
            retry_bounds,
            allow_official_accounts_retry=False,
            allow_search_commit_retry=False,
            allow_container_result_click=False,
        )

    async def _prefer_official_accounts_surface_for_preview_match(
        self,
        search_surface_bounds: Dict[str, int],
        effective_region: Dict[str, int],
        account_name: str,
        ocr_engine: Optional[AdaptiveOCR],
        *,
        official_account_region: Optional[Dict[str, int]] = None,
        detected_texts: Optional[List[str]] = None,
        allow_container_result_click: bool = True,
    ) -> bool:
        """When the match is only a mixed-search preview, switch to the dedicated official-account surface first."""
        self.logger.info(
            "命中公众号预览结果而非精确账号名，优先进入 Official Accounts 专用结果面后再重试: %s",
            account_name,
        )
        opened = await self._open_official_accounts_search_entry(
            search_surface_bounds,
            effective_region,
            ocr_engine,
            account_name=account_name,
            official_account_region=official_account_region,
            detected_texts=detected_texts,
        )
        if not opened:
            opened = await self._reset_search_and_open_official_accounts_surface(
                search_surface_bounds,
                account_name,
                ocr_engine,
            )
        if not opened:
            return await self._open_target_account_from_official_accounts_preview(
                search_surface_bounds,
                account_name,
            )

        await asyncio.sleep(1.2)
        retry_bounds = self._resolve_search_surface_bounds(
            search_surface_bounds,
            allow_small_child=True,
        )
        return await self._find_and_click_account_in_results(
            retry_bounds,
            account_name,
            retry_bounds,
            allow_official_accounts_retry=False,
            allow_search_commit_retry=False,
            allow_container_result_click=False,
            allow_preview_row_click=False,
            prefer_small_child_surface=True,
        )

    async def _reset_search_and_open_official_accounts_surface(
        self,
        base_bounds: Dict[str, int],
        account_name: str,
        ocr_engine: Optional[AdaptiveOCR],
    ) -> bool:
        """Reset the current search state, commit a fresh query, then reopen Official Accounts."""
        self.logger.info(
            "Official Accounts 专用结果面未稳定打开，重置搜索态后再试: %s",
            account_name,
        )
        if not self._ensure_wechat_frontmost(activate=True):
            return False

        self.press_key("escape")
        await asyncio.sleep(0.35)

        if await self._open_contacts_official_accounts_surface(base_bounds, ocr_engine):
            if await self._open_target_account_from_directory_panel(base_bounds, account_name):
                self.logger.info("通讯录/订阅号导航后已直接打开目标公众号: %s", account_name)
                return True
            if await self._open_target_account_from_official_accounts_preview(base_bounds, account_name):
                self.logger.info("通讯录/订阅号导航后已通过 Official Accounts 预览打开目标公众号: %s", account_name)
                return True
            if not self._refocus_search_input(base_bounds):
                self.logger.warning("通讯录/订阅号导航成功，但重新聚焦搜索框失败: %s", account_name)
                return False
            if not await self._input_account_name(account_name, time, base_bounds):
                self.logger.warning("通讯录/订阅号导航成功，但重新输入公众号失败: %s", account_name)
                return False
            if self.press_key("enter"):
                await asyncio.sleep(1.0)
            return True

        refocused = self._refocus_search_input(base_bounds)
        if not refocused:
            search_bar = await self._locate_search_bar(base_bounds)
            if not search_bar:
                self.logger.warning("重置搜索态后仍无法重新定位搜索框: %s", account_name)
                return False
            click_result = self.click_at(search_bar["x"], search_bar["y"])
            if click_result.status != AutomationStatus.SUCCESS:
                self.logger.warning("重置搜索态后点击搜索框失败: %s", account_name)
                return False
            await asyncio.sleep(0.4)

        if not await self._input_account_name(account_name, time, base_bounds):
            self.logger.warning("重置搜索态后重新输入公众号失败: %s", account_name)
            return False

        if not self.press_key("enter"):
            self.logger.warning("重置搜索态后发送 Enter 失败: %s", account_name)
            return False
        await asyncio.sleep(1.2)
        return True

    def _looks_like_official_account_panel(self, texts: List[str], account_name: str) -> bool:
        """Heuristically determine whether the panel is an account article page."""
        normalized = [(text or "").strip() for text in texts if (text or "").strip()]
        if not normalized:
            return False

        if self._looks_like_official_account_search_results_page(normalized, account_name):
            return False

        target = (account_name or "").strip()
        landing_header_hits = sum(
            1 for text in normalized
            if self._looks_like_account_landing_header(text, target)
        )

        strong_profile_markers = (
            "发消息",
            "已关注",
            "视频号：",
            "文章",
            "全部",
            "朋友关注",
            "原创内容",
        )
        strong_profile_marker_hits = sum(
            1
            for text in normalized
            if any(marker.lower() in text.lower() for marker in strong_profile_markers)
        )

        if (
            self._looks_like_account_directory_panel(normalized, account_name)
            and landing_header_hits == 0
            and strong_profile_marker_hits < 3
        ):
            return False

        mini_program_terms = (
            "小程序",
            "Mini Program",
            "小游戏",
            "最近使用",
            "添加到我的小程序",
            "进入小程序",
            "打开小程序",
            "体验版",
            "去使用",
            "立即打开",
        )
        has_mini_program_tabs = any(
            any(term.lower() in text.lower() for term in mini_program_terms)
            for text in normalized
        )
        if has_mini_program_tabs and landing_header_hits == 0 and not self._has_account_name_evidence(normalized, target):
            return False

        workspace_terms = (
            "元宝",
            "会议",
            "共享屏幕",
            "加入会议",
            "我的 Bot",
            "Bot",
            "Claude",
            "Clauc",
            "session",
            "任务wx_",
            "当前步骤",
            "正在执行",
            "微信连接",
        )
        if any(any(term.lower() in text.lower() for term in workspace_terms) for text in normalized):
            return False

        if self._looks_like_chat_conversation_panel(normalized):
            return False

        article_titles = [
            text for text in normalized
            if self._is_probable_article_title(text)
            and not self._looks_like_account_landing_header(text, target)
        ]
        official_account_terms = ("公众号", "订阅号", "服务号", "account", "articles", "article")
        profile_markers = (
            "发消息",
            "朋友关注",
            "视频号：",
            "文章",
            "全部",
            "最新消息",
            "展开",
            "Account",
            "Articles",
            "Article",
            "Profile",
            "媒体",
            "Related Results",
            "More〉",
            "More",
        )
        exact_target_hits = sum(
            1 for text in normalized
            if self._is_exact_account_name_match(text, target)
        )
        has_target_evidence = self._has_account_name_evidence(normalized, target)
        relaxed_target_evidence = has_target_evidence or any(
            self._proxy_account_match_score(text, target) >= 80.0
            for text in normalized
        )
        weak_target_evidence = relaxed_target_evidence or any(
            target
            and len(target) >= 3
            and (
                target[1:] in text
                or target[:-1] in text
            )
            for text in normalized
        )
        has_official_account_marker = any(
            any(term.lower() in text.lower() for term in official_account_terms)
            for text in normalized
        )
        profile_marker_hits = sum(
            1
            for text in normalized
            if any(marker.lower() in text.lower() for marker in profile_markers)
        )
        informative_lines = [
            text
            for text in normalized
            if len(text) >= 6
            and not any(term.lower() in text.lower() for term in official_account_terms)
            and text != target
            and not self._looks_like_search_result_preview(text, account_name)
        ]
        article_body_lines = [
            text
            for text in normalized
            if len(text) >= 12
            and sum(1 for char in text if "\u4e00" <= char <= "\u9fff") >= 6
            and not self._looks_like_search_result_preview(text, account_name)
            and not self._looks_like_chart_or_numeric_line(text)
        ]
        datetime_or_views_hits = sum(
            1
            for text in normalized
            if (
                re.search(r"\d{4}年\d{1,2}月\d{1,2}日", text)
                or re.search(r"\d{1,2}:\d{2}", text)
                or re.search(r"\d+\s*人", text)
            )
        )
        if landing_header_hits >= 1 and article_titles and profile_marker_hits >= 1:
            return True

        if landing_header_hits >= 2 and (profile_marker_hits >= 1 or informative_lines):
            return True

        if exact_target_hits >= 1 and article_titles and has_official_account_marker:
            return True

        if exact_target_hits >= 1 and target and has_official_account_marker and informative_lines:
            return True

        if exact_target_hits >= 1 and target and article_titles:
            title_hits = sum(1 for text in article_titles if len(text) >= 8)
            if title_hits >= 1:
                return True

        if relaxed_target_evidence and profile_marker_hits >= 3:
            return True

        if weak_target_evidence and datetime_or_views_hits >= 1 and len(article_body_lines) >= 4:
            return True

        return False

    def _looks_like_official_account_search_results_page(
        self,
        texts: List[str],
        account_name: str,
    ) -> bool:
        """Reject WeChat's account search results page, which is not the account article feed."""
        normalized = [(text or "").strip() for text in texts if (text or "").strip()]
        if not normalized:
            return False

        lowered = [text.lower() for text in normalized]
        if any("related results" in text or "相关结果" in text for text in lowered):
            return True

        search_surface_markers = (
            "ai chatting",
            "underline",
            "video",
            "all",
            "search",
            "搜索",
        )
        marker_hits = sum(
            1
            for text in lowered
            if any(marker in text for marker in search_surface_markers)
        )
        target = (account_name or "").strip()
        target_hits = sum(
            1
            for text in normalized
            if target
            and (target in text or self._text_similarity(text, target) >= 0.72)
        )
        landing_header_hits = sum(
            1 for text in normalized
            if self._looks_like_account_landing_header(text, target)
        )
        if marker_hits >= 3 and target_hits >= 2 and landing_header_hits >= 1:
            return True

        return False

    def _looks_like_titled_account_article_window(self, texts: List[str], account_name: str) -> bool:
        """Accept named account windows that contain article-list evidence without explicit account labels."""
        normalized = [(text or "").strip() for text in texts if (text or "").strip()]
        if not normalized:
            return False
        if self._looks_like_official_account_search_results_page(normalized, account_name):
            return False
        target = (account_name or "").strip()
        landing_header_hits = sum(
            1 for text in normalized
            if self._looks_like_account_landing_header(text, target)
        )
        if self._looks_like_account_directory_panel(normalized, account_name) and landing_header_hits == 0:
            return False
        if self._looks_like_chat_conversation_panel(normalized):
            return False
        if any(self._looks_like_mini_program_text(text) for text in normalized) and landing_header_hits == 0:
            return False

        workspace_terms = (
            "元宝",
            "会议",
            "共享屏幕",
            "加入会议",
            "我的 Bot",
            "Bot",
            "Claude",
            "Clauc",
            "session",
            "任务wx_",
            "当前步骤",
            "正在执行",
            "微信连接",
        )
        if any(any(term.lower() in text.lower() for term in workspace_terms) for text in normalized):
            return False

        article_titles = [
            text for text in normalized
            if self._is_probable_article_title(text)
            and not self._looks_like_account_landing_header(text, target)
        ]
        timestamp_lines = sum(1 for text in normalized if re.search(r"\b\d{1,2}:\d{2}\b", text))
        informative_lines = [
            text for text in normalized
            if len(text) >= 8
            and not self._looks_like_search_result_preview(text, account_name)
            and not self._looks_like_chart_or_numeric_line(text)
        ]
        return (
            (landing_header_hits >= 1 and len(article_titles) >= 1)
            or (landing_header_hits >= 2 and len(informative_lines) >= 2)
            or
            len(article_titles) >= 2
            or (len(article_titles) >= 1 and len(informative_lines) >= 2)
            or (len(article_titles) >= 1 and timestamp_lines >= 1)
        )

    def _looks_like_chart_or_numeric_line(self, text: str) -> bool:
        normalized = (text or "").strip()
        if not normalized:
            return False

        stripped = normalized.lstrip("•●· ").strip()
        if not stripped:
            return False

        if re.fullmatch(r"[\d\s\.\,\-\+\:\%\$\/]+", stripped):
            return True

        chart_terms = (
            "plots",
            "candles",
            "volume",
            "indicator",
            "macd",
            "rsi",
            "kdj",
            "boll",
            "ma5",
            "ma10",
            "ma20",
            "ma30",
            "ma60",
        )
        lowered = stripped.lower()
        if lowered in chart_terms:
            return True
        if lowered.startswith("plot ") or lowered.startswith("plots"):
            return True

        return False

    def _looks_like_chat_conversation_panel(self, texts: List[str]) -> bool:
        normalized = [(text or "").strip() for text in texts if (text or "").strip()]
        if not normalized:
            return False

        official_markers = ("公众号", "订阅号", "服务号", "常看的号", "最近阅读", "搜索指定公众号")
        if any(any(marker in text for marker in official_markers) for text in normalized):
            return False

        timestamp_lines = sum(1 for text in normalized if re.search(r"\b\d{1,2}:\d{2}\b", text))
        date_marker_lines = sum(
            1
            for text in normalized
            if (
                re.search(r"\b\d{1,2}/\d{1,2}\b", text)
                or re.search(r"\b\d{4}-\d{1,2}-\d{1,2}\b", text)
                or any(marker in text for marker in ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日", "星期天", "昨天", "今天", "前天"))
            )
        )
        dialogue_markers = sum(
            1
            for text in normalized
            if (
                text.startswith(("我", "你", "他", "她", "它", "@", "|"))
                or "@" in text
                or (
                    ("：" in text or ":" in text)
                    and not re.fullmatch(r"\d{1,2}:\d{2}", text.strip())
                    and not self._is_probable_article_title(text)
                )
            )
        )
        chat_terms = (
            "看多看空",
            "我问下",
            "毛利率",
            "利润",
            "解释",
            "不太懂",
            "共享屏幕",
            "加入会议",
            "微信元宝",
            "Bot",
            "Claude",
            "折叠的聊天",
            "聊天记录",
            "进入聊天",
            "文件",
            "社区党员群",
        )
        chat_term_hits = sum(
            1 for text in normalized if any(term.lower() in text.lower() for term in chat_terms)
        )
        short_message_rows = sum(
            1
            for text in normalized
            if 3 <= len(text) <= 24 and not self._is_probable_article_title(text)
                and not self._looks_like_chart_or_numeric_line(text)
        )

        return (
            (timestamp_lines >= 1 or date_marker_lines >= 2)
            and (
                dialogue_markers >= 2
                or chat_term_hits >= 2
                or short_message_rows >= 4
            )
        )

    def _looks_like_account_directory_panel(self, texts: List[str], account_name: str) -> bool:
        """Detect WeChat's account-directory/recommendation panel, not the article history page."""
        normalized = [(text or "").strip() for text in texts if (text or "").strip()]
        if not normalized:
            return False

        target = (account_name or "").strip()
        has_target = any(
            target and (target in text or self._text_similarity(text, target) >= 0.72)
            for text in normalized
        )
        if not has_target:
            return False

        if any("常看的号" in text for text in normalized):
            return True

        directory_markers = ("直播中", "最近阅读", "更多", "推荐", "搜索指定公众号")
        marker_hits = sum(1 for text in normalized if any(marker in text for marker in directory_markers))
        bullet_rows = sum(1 for text in normalized if text.lstrip().startswith(("•", "●", "·")))
        short_account_rows = sum(
            1
            for text in normalized
            if 2 <= len(text) <= 12
            and any("\u4e00" <= char <= "\u9fff" for char in text)
            and not self._is_probable_article_title(text)
            and not any(marker in text for marker in directory_markers)
        )
        article_titles = [text for text in normalized if self._is_probable_article_title(text)]
        return marker_hits >= 1 and (bullet_rows >= 2 or (short_account_rows >= 3 and not article_titles))

    def _looks_like_generic_official_accounts_panel(self, texts: List[str]) -> bool:
        """Detect the generic Official Accounts category panel before a concrete account page opens."""
        normalized = [(text or "").strip() for text in texts if (text or "").strip()]
        if not normalized:
            return False
        if self._looks_like_chat_conversation_panel(normalized):
            return False

        generic_markers = (
            "official accounts",
            "service accounts",
            "account",
            "articles",
            "article",
            "公众号",
            "服务号",
            "订阅号",
            "视频号",
            "小程序",
            "all",
            "不限",
        )
        marker_hits = sum(
            1
            for text in normalized
            if any(marker in text.lower() for marker in generic_markers)
        )
        article_titles = [text for text in normalized if self._is_probable_article_title(text)]
        landing_headers = sum(
            1 for text in normalized
            if any(marker in text.lower() for marker in ("account", "articles", "official accounts"))
        )
        return marker_hits >= 4 and landing_headers >= 2 and len(article_titles) <= 1

    def _resolve_account_discovery_panel_bounds(
        self,
        base_bounds: Dict[str, int],
    ) -> Dict[str, int]:
        """Use the full front child window when WeChat opens a category/discovery surface."""
        front_bounds = self._get_frontmost_wechat_window_bounds()
        min_child_width = max(self._scale_window_x(base_bounds, 430), int(base_bounds["Width"] * 0.45))
        min_child_height = max(self._scale_window_y(base_bounds, 420), int(base_bounds["Height"] * 0.55))
        if front_bounds and (
            abs(front_bounds["X"] - base_bounds["X"]) > 20
            or abs(front_bounds["Y"] - base_bounds["Y"]) > 20
            or front_bounds["Width"] < int(base_bounds["Width"] * 0.95)
        ):
            if front_bounds["Width"] < min_child_width or front_bounds["Height"] < min_child_height:
                self.logger.info(
                    "Ignoring small front WeChat child window for account discovery and using main article panel instead: child=%s base=%s",
                    front_bounds,
                    base_bounds,
                )
                return self._resolve_article_panel_bounds(base_bounds)
            self.logger.info("Using front WeChat child window for account discovery: %s", front_bounds)
            return front_bounds
        return self._resolve_article_panel_bounds(base_bounds)

    def _account_panel_click_point(
        self,
        region: Dict[str, int],
        match: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, int]:
        """Click the matched account text center inside the right-side panel when available."""
        default_x = region["X"] + min(max(32, int(region["Width"] * 0.18)), max(32, region["Width"] - 32))
        default_y = region["Y"] + min(max(24, int(region["Height"] * 0.14)), max(18, region["Height"] - 18))
        if not match:
            return int(default_x), int(default_y)

        raw = match.get("raw") if isinstance(match, dict) else None
        raw_position = self._ocr_position(raw) if isinstance(raw, dict) else {}
        if raw_position.get("width") and raw_position.get("height"):
            match_x = raw_position["x"] + raw_position["width"] / 2
            match_y = raw_position["y"] + raw_position["height"] / 2
        else:
            match_x = float(match.get("x", default_x) or default_x)
            match_y = float(match.get("y", default_y) or default_y)

        click_x = min(
            max(int(round(match_x)), region["X"] + 24),
            region["X"] + region["Width"] - 24,
        )
        click_y = min(
            max(int(round(match_y)), region["Y"] + 18),
            region["Y"] + region["Height"] - 18,
        )
        return int(click_x), int(click_y)

    def _account_panel_anchor_click_point(
        self,
        region: Dict[str, int],
        match: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, int]:
        """Fallback row-anchor click used when text-center clicks do not open the account page."""
        anchor_x = region["X"] + min(max(32, int(region["Width"] * 0.18)), max(32, region["Width"] - 32))
        if not match:
            anchor_y = region["Y"] + min(max(24, int(region["Height"] * 0.14)), max(18, region["Height"] - 18))
            return int(anchor_x), int(anchor_y)

        raw = match.get("raw") if isinstance(match, dict) else None
        raw_position = self._ocr_position(raw) if isinstance(raw, dict) else {}
        if raw_position.get("height"):
            anchor_y = raw_position["y"] + raw_position["height"] / 2
        else:
            anchor_y = float(match.get("y") or (region["Y"] + region["Height"] / 2))

        click_y = min(
            max(int(round(anchor_y)), region["Y"] + 18),
            region["Y"] + region["Height"] - 18,
        )
        return int(anchor_x), int(click_y)

    def _find_target_account_click_target_in_panel(
        self,
        panel_bounds: Dict[str, int],
        account_name: str,
        *,
        strict_exact: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Find the target account row inside the right-side directory panel."""
        target = (account_name or "").strip()
        if not target:
            return None

        candidates: List[Dict[str, Any]] = []

        accessibility_service = getattr(self, "accessibility_service", None)
        if accessibility_service:
            match = accessibility_service.find_named_element(
                target,
                region=panel_bounds,
                allowed_roles=[
                    "axrow",
                    "axbutton",
                    "axgroup",
                    "axstatictext",
                    "row",
                    "button",
                    "group",
                    "text",
                ],
                min_similarity=0.72,
                blocked_terms=["文章", "视频号", "朋友圈"],
            )
            if match:
                matched_text = match.get("text") or target
                if strict_exact and not self._is_exact_account_name_match(matched_text, target):
                    match = None
                elif not strict_exact and self._proxy_account_match_score(matched_text, target) <= 0:
                    match = None
            if match:
                click_x, click_y = self._account_panel_click_point(panel_bounds, match)
                anchor_x, anchor_y = self._account_panel_anchor_click_point(panel_bounds, match)
                matched_text = match.get("text") or target
                candidates.append({
                    "x": click_x,
                    "y": click_y,
                    "text": matched_text,
                    "method": "accessibility_panel_match",
                    "alternate_clicks": [(anchor_x, anchor_y)],
                    "match_score": self._proxy_account_match_score(matched_text, target),
                    "confidence": float(match.get("confidence") or 0.0),
                })

        ocr_engine = self._get_account_result_ocr_engine()
        ocr_processor = getattr(self, "ocr_processor", None)
        if ocr_processor and ocr_engine:
            screenshot = self._capture_region_screenshot(panel_bounds, expected_bounds=panel_bounds)
            if screenshot is not None:
                try:
                    ocr_results = ocr_engine.recognize(screenshot, target_hint=target)
                except TypeError:
                    ocr_results = ocr_engine.recognize(screenshot)
                except Exception as exc:
                    self.logger.warning("OCR recognition failed while matching account panel %r: %s", target, exc)
                    ocr_results = []

                for result in ocr_results:
                    text = (result.get("text") or "").strip()
                    confidence = float(result.get("confidence") or 0.0)
                    if confidence < 18 or not text:
                        continue

                    center_x, center_y = self._ocr_center(result, screenshot)
                    if not self._point_in_bounds(center_x, center_y, panel_bounds):
                        continue

                    match_score = self._proxy_account_match_score(text, target)
                    if match_score <= 0:
                        continue
                    if strict_exact and not self._is_exact_account_name_match(text, target):
                        continue

                    click_x, click_y = self._account_panel_click_point(
                        panel_bounds,
                        {"x": center_x, "y": center_y, "height": self._ocr_position(result)["height"]},
                    )
                    anchor_x, anchor_y = self._account_panel_anchor_click_point(
                        panel_bounds,
                        {"x": center_x, "y": center_y, "height": self._ocr_position(result)["height"]},
                    )
                    candidates.append({
                        "x": click_x,
                        "y": click_y,
                        "text": text,
                        "method": "ocr_panel_match",
                        "alternate_clicks": [(anchor_x, anchor_y)],
                        "match_score": match_score,
                        "confidence": confidence,
                    })

        if not candidates:
            return None

        return max(
            candidates,
            key=lambda candidate: (
                float(candidate.get("match_score") or 0.0),
                float(candidate.get("confidence") or 0.0),
                1 if candidate.get("method") == "accessibility_panel_match" else 0,
            ),
        )

    async def _open_target_account_from_directory_panel(
        self,
        base_bounds: Dict[str, int],
        account_name: str,
    ) -> bool:
        """When WeChat lands on a recommendation/directory panel, click the actual account card once more."""
        panel_bounds = self._resolve_account_discovery_panel_bounds(base_bounds)
        panel_texts = self._collect_region_surface_texts(
            panel_bounds,
            min_confidence=20.0,
            allowed_roles=[
                "axstatictext",
                "axlink",
                "axbutton",
                "text",
                "link",
                "button",
                "row",
            ],
        )
        generic_panel = self._looks_like_generic_official_accounts_panel(panel_texts)
        has_target_evidence = self._has_account_name_evidence(panel_texts, account_name)
        if not (
            self._looks_like_account_directory_panel(panel_texts, account_name)
            or generic_panel
            or has_target_evidence
        ):
            if panel_texts:
                self.logger.info(
                    "Account discovery panel did not look like a directory surface for '%s'; texts=%s",
                    account_name,
                    panel_texts[:12],
                )
            return False

        accessibility_service = getattr(self, "accessibility_service", None)
        invoke_named_element = getattr(accessibility_service, "invoke_named_element", None)
        exact_accessibility_match = None
        if accessibility_service:
            exact_accessibility_match = accessibility_service.find_named_element(
                account_name,
                region=panel_bounds,
                allowed_roles=[
                    "axrow",
                    "axbutton",
                    "axgroup",
                    "axstatictext",
                    "row",
                    "button",
                    "group",
                    "text",
                ],
                min_similarity=0.72,
                blocked_terms=["文章", "视频号", "朋友圈"],
            )
            if exact_accessibility_match and not (
                self._is_exact_account_name_match(
                    exact_accessibility_match.get("text"),
                    account_name,
                )
                or (
                    (generic_panel or has_target_evidence)
                    and self._proxy_account_match_score(
                        exact_accessibility_match.get("text"),
                        account_name,
                    ) > 0
                )
            ):
                exact_accessibility_match = None
        if callable(invoke_named_element) and exact_accessibility_match and invoke_named_element(
            account_name,
            region=panel_bounds,
            allowed_roles=[
                "axrow",
                "axbutton",
                "axgroup",
                "axstatictext",
                "row",
                "button",
                "group",
                "text",
            ],
            min_similarity=0.72,
            blocked_terms=["文章", "视频号", "朋友圈"],
            actions=["AXPress", "AXOpen", "AXConfirm"],
        ):
            self.logger.info("公众号目录页通过 native accessibility action 打开目标账号: %s", account_name)
            await asyncio.sleep(1.2)
            if self._panel_looks_like_official_account_page(base_bounds, account_name):
                return True

        click_target = self._find_target_account_click_target_in_panel(
            panel_bounds,
            account_name,
            strict_exact=not (generic_panel or has_target_evidence),
        )
        if not click_target:
            self.logger.warning(
                "公众号目录页已识别，但未能定位目标账号 '%s' 的卡片；texts=%s",
                account_name,
                panel_texts[:12],
            )
            return False

        self.logger.info(
            "公众号目录页匹配到目标账号 '%s' via %s; click=(%s, %s)",
            click_target.get("text"),
            click_target.get("method"),
            click_target["x"],
            click_target["y"],
        )
        click_result = self.click_at(click_target["x"], click_target["y"])
        if click_result.status != AutomationStatus.SUCCESS:
            return False

        await asyncio.sleep(1.2)
        if self._panel_looks_like_official_account_page(base_bounds, account_name):
            return True

        self.logger.info(
            "公众号目录页首次点击未打开，尝试双击目标账号 '%s' at (%s, %s)",
            account_name,
            click_target["x"],
            click_target["y"],
        )
        self._click_at_with_focus_retry(int(click_target["x"]), int(click_target["y"]))
        await asyncio.sleep(0.18)
        self._click_at_with_focus_retry(int(click_target["x"]), int(click_target["y"]))
        await asyncio.sleep(1.0)
        if self._panel_looks_like_official_account_page(base_bounds, account_name):
            return True

        for alt_x, alt_y in click_target.get("alternate_clicks") or []:
            if abs(int(alt_x) - int(click_target["x"])) <= 4 and abs(int(alt_y) - int(click_target["y"])) <= 4:
                continue
            self.logger.info(
                "公众号目录页首次点击未打开，尝试行锚点恢复点击 '%s' at (%s, %s)",
                account_name,
                alt_x,
                alt_y,
            )
            click_result = self._click_at_with_focus_retry(int(alt_x), int(alt_y))
            if click_result.status != AutomationStatus.SUCCESS:
                continue
            await asyncio.sleep(1.2)
            if self._panel_looks_like_official_account_page(base_bounds, account_name):
                return True

            self.logger.info(
                "公众号目录页行锚点单击未打开，尝试双击 '%s' at (%s, %s)",
                account_name,
                alt_x,
                alt_y,
            )
            self._click_at_with_focus_retry(int(alt_x), int(alt_y))
            await asyncio.sleep(0.18)
            self._click_at_with_focus_retry(int(alt_x), int(alt_y))
            await asyncio.sleep(1.0)
            if self._panel_looks_like_official_account_page(base_bounds, account_name):
                return True

        self.logger.info("公众号目录页首次点击未打开，尝试发送 Enter 打开 '%s'", account_name)
        self.press_key("enter")
        await asyncio.sleep(1.0)
        return self._panel_looks_like_official_account_page(base_bounds, account_name)

    def _find_target_account_click_targets_in_search_preview(
        self,
        base_bounds: Dict[str, int],
        account_name: str,
    ) -> List[Tuple[int, int, str]]:
        """Find target-specific click points inside the mixed-search preview row."""
        search_surface_bounds = self._resolve_search_surface_bounds(
            base_bounds,
            allow_small_child=True,
            account_name=account_name,
        )
        search_region = self._search_results_panel_bounds(search_surface_bounds)
        preview_region = self._resolve_official_accounts_preview_region(
            search_surface_bounds,
            search_region,
            self._get_account_result_ocr_engine(),
        )
        surface_texts = self._collect_region_ocr_surface_texts(
            search_region,
            min_confidence=18.0,
        )
        if not self._has_account_name_evidence(surface_texts, account_name):
            return []
        if not any(self._looks_like_official_accounts_entry(text) for text in surface_texts):
            return []

        click_targets: List[Tuple[int, int, str]] = []
        match: Optional[Dict[str, Any]] = None
        accessibility_service = getattr(self, "accessibility_service", None)
        if accessibility_service:
            match = accessibility_service.find_named_element(
                account_name,
                region=preview_region,
                allowed_roles=[
                    "axrow",
                    "axbutton",
                    "axgroup",
                    "axstatictext",
                    "row",
                    "button",
                    "group",
                    "text",
                ],
                min_similarity=0.72,
                blocked_terms=["文章", "视频号", "朋友圈", "Minimized Groups"],
            )

        if not match and self.ocr_processor:
            ocr_engine = self._get_account_result_ocr_engine()
            screenshot = self._capture_region_screenshot(
                preview_region,
                expected_bounds=search_surface_bounds,
            )
            if screenshot is not None and ocr_engine:
                match = self._find_best_ocr_text_match(
                    screenshot,
                    account_name,
                    bounds=preview_region,
                    min_similarity=0.68,
                    min_confidence=18,
                    ocr_engine=ocr_engine,
                )

        if match:
            text_x = int(match.get("x") or preview_region["X"] + preview_region["Width"] // 2)
            text_y = int(match.get("y") or preview_region["Y"] + preview_region["Height"] // 2)
            row_x, row_y = self._search_result_row_click_point(
                search_surface_bounds,
                preview_region,
                match,
            )
            icon_x = preview_region["X"] + min(
                max(self._scale_window_x(search_surface_bounds, 70), int(preview_region["Width"] * 0.16)),
                max(24, preview_region["Width"] - 24),
            )
            match_text = (match.get("text") or "").strip()
            if self._looks_like_account_landing_header(match_text, account_name):
                return []
            exact_account_label = (
                self._is_exact_account_name_match(match_text, account_name)
                and not self._looks_like_search_result_preview(match_text, account_name)
                and not self._looks_like_mini_program_text(match_text)
            )
            if exact_account_label:
                click_targets.append((text_x, text_y, "preview_target_label"))
                click_targets.append((int(row_x), int(row_y), "preview_target_row"))
                click_targets.append((int(icon_x), int(row_y), "preview_target_icon"))
            elif self._is_target_account_preview_match(match_text, account_name):
                click_targets.append((int(row_x), int(row_y), "preview_target_row"))
                click_targets.append((int(icon_x), int(row_y), "preview_target_icon"))

        deduped: List[Tuple[int, int, str]] = []
        seen_points = set()
        for click_x, click_y, label in click_targets:
            key = (int(click_x), int(click_y))
            if key in seen_points:
                continue
            seen_points.add(key)
            deduped.append((int(click_x), int(click_y), label))
        return deduped

    async def _open_target_account_from_official_accounts_preview(
        self,
        base_bounds: Dict[str, int],
        account_name: str,
    ) -> bool:
        """Open the concrete target account from the Official Accounts preview row."""
        search_surface_bounds = self._resolve_search_surface_bounds(
            base_bounds,
            allow_small_child=True,
            account_name=account_name,
        )
        search_region = self._search_results_panel_bounds(search_surface_bounds)
        preview_region = self._resolve_official_accounts_preview_region(
            search_surface_bounds,
            search_region,
            self._get_account_result_ocr_engine(),
        )
        surface_texts = self._collect_region_ocr_surface_texts(
            search_region,
            min_confidence=18.0,
        )
        click_targets = self._find_target_account_click_targets_in_search_preview(
            base_bounds,
            account_name,
        )
        if not click_targets:
            if self._looks_like_generic_official_accounts_panel(surface_texts):
                return await self._open_target_account_from_directory_panel(base_bounds, account_name)
            return False

        accessibility_service = getattr(self, "accessibility_service", None)
        invoke_named_element = getattr(accessibility_service, "invoke_named_element", None)
        exact_accessibility_match = None
        if accessibility_service:
            exact_accessibility_match = accessibility_service.find_named_element(
                account_name,
                region=preview_region,
                allowed_roles=[
                    "axrow",
                    "axbutton",
                    "axgroup",
                    "axstatictext",
                    "row",
                    "button",
                    "group",
                    "text",
                ],
                min_similarity=0.9,
                blocked_terms=[
                    "文章",
                    "视频号",
                    "朋友圈",
                    "Minimized Groups",
                    "小程序",
                    "Mini Program",
                ],
            )

        can_use_native_action = (
            callable(invoke_named_element)
            and exact_accessibility_match is not None
            and self._is_exact_account_name_match(exact_accessibility_match.get("text"), account_name)
            and not any(self._looks_like_mini_program_text(text) for text in surface_texts)
        )
        if can_use_native_action and invoke_named_element(
            account_name,
            region=preview_region,
            allowed_roles=[
                "axrow",
                "axbutton",
                "axgroup",
                "axstatictext",
                "row",
                "button",
                "group",
                "text",
            ],
            min_similarity=0.9,
            blocked_terms=[
                "文章",
                "视频号",
                "朋友圈",
                "Minimized Groups",
                "小程序",
                "Mini Program",
            ],
            actions=["AXPress", "AXOpen", "AXConfirm"],
        ):
            self.logger.info("公众号预览行通过 native accessibility action 打开精确目标账号: %s", account_name)
            await asyncio.sleep(1.0)
            if self._panel_looks_like_official_account_page(base_bounds, account_name):
                return True

        for click_x, click_y, label in click_targets:
            self.logger.info(
                "公众号预览行命中目标账号 '%s'，尝试 %s 打开 at (%s, %s)",
                account_name,
                label,
                click_x,
                click_y,
            )
            click_result = self._click_at_with_focus_retry(int(click_x), int(click_y))
            if click_result.status != AutomationStatus.SUCCESS:
                continue
            await asyncio.sleep(1.0)
            if self._panel_looks_like_official_account_page(base_bounds, account_name):
                return True

            self.logger.info(
                "公众号预览行单击未打开，尝试双击 %s for '%s' at (%s, %s)",
                label,
                account_name,
                click_x,
                click_y,
            )
            self._click_at_with_focus_retry(int(click_x), int(click_y))
            await asyncio.sleep(0.18)
            self._click_at_with_focus_retry(int(click_x), int(click_y))
            await asyncio.sleep(1.0)
            if self._panel_looks_like_official_account_page(base_bounds, account_name):
                return True

            self.logger.info("公众号预览行双击未打开，发送 Enter 确认 '%s'", account_name)
            self._press_key_with_focus_retry("enter")
            await asyncio.sleep(0.9)
            if self._panel_looks_like_official_account_page(base_bounds, account_name):
                return True

        return False

    def _panel_looks_like_official_account_page(
        self,
        base_bounds: Dict[str, int],
        account_name: str,
    ) -> bool:
        """Check whether the click actually opened the target official-account page."""
        named_window_bounds = None
        if account_name:
            named_window_bounds = self._get_wechat_window_bounds_by_title(account_name)

        panel_bounds = self._resolve_article_panel_bounds(base_bounds, account_name)
        accessibility_service = getattr(self, "accessibility_service", None)
        if accessibility_service:
            try:
                accessibility_texts = self._dedupe_surface_texts(
                    accessibility_service.collect_texts(
                        region=panel_bounds,
                        allowed_roles=[
                            "axstatictext",
                            "axlink",
                            "axbutton",
                            "text",
                            "link",
                            "button",
                            "row",
                        ],
                    )
                )
            except Exception as exc:
                self.logger.debug("Accessibility article-panel collection failed for %s: %s", panel_bounds, exc)
                accessibility_texts = []
            if accessibility_texts:
                self.logger.info("公众号页 Accessibility 文本: %s", accessibility_texts[:12])
                if self._looks_like_official_account_panel(accessibility_texts, account_name):
                    return True
                if named_window_bounds and self._looks_like_titled_account_article_window(
                    accessibility_texts,
                    account_name,
                ):
                    self.logger.info(
                        "Window title + article-list accessibility evidence matched official-account page: %s",
                        account_name,
                    )
                    return True

        texts = self._collect_region_surface_texts(
            panel_bounds,
            min_confidence=20.0,
            allowed_roles=[
                "axstatictext",
                "axlink",
                "axbutton",
                "text",
                "link",
                "button",
                "row",
            ],
        )
        if texts:
            self.logger.info("公众号页校验文本: %s", texts[:12])
        if self._looks_like_official_account_panel(texts, account_name):
            return True
        if named_window_bounds and self._looks_like_titled_account_article_window(texts, account_name):
            self.logger.info(
                "Window title + OCR article-list evidence matched official-account page: %s",
                account_name,
            )
            return True

        if named_window_bounds:
            self.logger.info(
                "Window title matched %s but article panel evidence was insufficient; treating as unopened official-account page",
                account_name,
            )
        return False

    async def _ensure_account_page_open(
        self,
        base_bounds: Dict[str, int],
        account_name: str,
        click_x: int,
        click_y: int,
        alternate_clicks: Optional[List[Tuple[int, int]]] = None,
    ) -> bool:
        """Retry the result-opening gesture until the account page is really visible."""
        recovery_steps = ("wait", "alternate_click", "double_click", "repeat_click", "keyboard_open", "enter")
        remaining_alternate_clicks = [
            (int(x), int(y))
            for x, y in (alternate_clicks or [])
            if abs(int(x) - int(click_x)) > 4 or abs(int(y) - int(click_y)) > 4
        ]
        double_click_target = remaining_alternate_clicks[0] if remaining_alternate_clicks else (int(click_x), int(click_y))
        preview_target_attempted = False
        for step in recovery_steps:
            await asyncio.sleep(1.2)
            if self._panel_looks_like_official_account_page(base_bounds, account_name):
                return True

            if await self._open_target_account_from_directory_panel(base_bounds, account_name):
                return True

            if not preview_target_attempted:
                preview_target_attempted = True
                if await self._open_target_account_from_official_accounts_preview(base_bounds, account_name):
                    return True

            if step == "alternate_click" and remaining_alternate_clicks:
                alt_x, alt_y = remaining_alternate_clicks.pop(0)
                self.logger.info(
                    "公众号页仍未打开，尝试点击搜索结果文本中心: %s at (%s, %s)",
                    account_name,
                    alt_x,
                    alt_y,
                )
                self._click_at_with_focus_retry(alt_x, alt_y)
            elif step == "double_click":
                self.logger.info(
                    "公众号页仍未打开，尝试双击搜索结果: %s at (%s, %s)",
                    account_name,
                    double_click_target[0],
                    double_click_target[1],
                )
                self._click_at_with_focus_retry(double_click_target[0], double_click_target[1])
                await asyncio.sleep(0.18)
                self._click_at_with_focus_retry(double_click_target[0], double_click_target[1])
            elif step == "repeat_click":
                self.logger.info("公众号页未打开，重试点击搜索结果: %s", account_name)
                self._click_at_with_focus_retry(click_x, click_y)
            elif step == "keyboard_open":
                self.logger.info("公众号页仍未打开，尝试键盘选中首个搜索结果并打开: %s", account_name)
                self._press_key_with_focus_retry("tab")
                await asyncio.sleep(0.18)
                self._press_key_with_focus_retry("down")
                await asyncio.sleep(0.18)
                self._press_key_with_focus_retry("enter")
            elif step == "enter":
                self.logger.info("公众号页仍未打开，发送 Enter 确认打开: %s", account_name)
                self._press_key_with_focus_retry("enter")

        await asyncio.sleep(1.2)
        return self._panel_looks_like_official_account_page(base_bounds, account_name)

    def _find_account_result_by_visual_layout(
        self,
        screenshot,
        bounds: Dict[str, int],
        account_name: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Locate the first public-account result row from the real search popover.

        This is a last-resort visual fallback for environments without OCR and
        with empty LLM responses. It clicks the first highlighted title row in
        the public-account section, not the lower chat-history or web-search
        rows. The target is derived from the current screenshot and WeChat
        window bounds, not from a fixed account name or default account.
        """
        try:
            import cv2
            import numpy as np

            image = np.array(screenshot)
            if image.ndim < 3:
                return None
            if image.shape[2] > 3:
                image = image[:, :, :3]

            official_account_region = self._official_account_result_region(bounds)
            x, y, width, height = self._logical_region_to_pixels(official_account_region, screenshot)
            max_height, max_width = image.shape[:2]
            right = min(max_width, x + width)
            bottom = min(max_height, y + height)
            if right <= x or bottom <= y:
                return None

            crop = image[y:bottom, x:right]
            rgb = crop.astype("int16")
            red = rgb[:, :, 0]
            green = rgb[:, :, 1]
            blue = rgb[:, :, 2]
            mask = (
                (green > 115)
                & ((green - red) > 24)
                & ((green - blue) > 18)
            ).astype("uint8")

            kernel = np.ones((2, 2), dtype="uint8")
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
            num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
            scale_x, scale_y = self._get_screenshot_scale(screenshot)

            components: List[Dict[str, float]] = []

            for label in range(1, num_labels):
                comp_x, comp_y, comp_w, comp_h, area = stats[label]
                if area < 8 or comp_w < 2 or comp_h < 2:
                    continue
                if comp_w > 80 * scale_x or comp_h > 36 * scale_y:
                    continue

                centroid_x, centroid_y = centroids[label]
                components.append({
                    "center_x": (x + centroid_x) / scale_x,
                    "center_y": (y + centroid_y) / scale_y,
                    "left": (x + comp_x) / scale_x,
                    "top": (y + comp_y) / scale_y,
                    "right": (x + comp_x + comp_w) / scale_x,
                    "bottom": (y + comp_y + comp_h) / scale_y,
                    "area": float(area),
                })

            red_badge_mask = (
                (red > 150)
                & ((red - green) > 45)
                & ((red - blue) > 35)
            ).astype("uint8")
            red_badge_mask = cv2.morphologyEx(red_badge_mask, cv2.MORPH_CLOSE, kernel, iterations=1)
            badge_labels, _, badge_stats, badge_centroids = cv2.connectedComponentsWithStats(red_badge_mask, 8)
            badge_candidates: List[Dict[str, float]] = []
            for label in range(1, badge_labels):
                comp_x, comp_y, comp_w, comp_h, area = badge_stats[label]
                if area < 10 or comp_w < 3 or comp_h < 3:
                    continue
                if comp_w > 28 * scale_x or comp_h > 28 * scale_y:
                    continue
                centroid_x, centroid_y = badge_centroids[label]
                badge_candidates.append({
                    "center_x": (x + centroid_x) / scale_x,
                    "center_y": (y + centroid_y) / scale_y,
                    "left": (x + comp_x) / scale_x,
                    "top": (y + comp_y) / scale_y,
                    "right": (x + comp_x + comp_w) / scale_x,
                    "bottom": (y + comp_y + comp_h) / scale_y,
                    "area": float(area),
                })

            if badge_candidates and not components:
                badge_candidates.sort(key=lambda item: (item["center_y"], -item["area"]))
                badge = badge_candidates[0]
                row_components = [
                    component for component in components
                    if abs(float(component["center_y"]) - float(badge["center_y"])) <= max(10.0, 6.0 * scale_y)
                    and float(component["right"]) <= float(badge["right"]) + 8
                ]
                if row_components:
                    left = min(float(item["left"]) for item in row_components)
                    right = max(float(item["right"]) for item in row_components)
                    top = min(float(item["top"]) for item in row_components)
                    bottom = max(float(item["bottom"]) for item in row_components)
                    click_x = int(round((left + right) / 2))
                    click_y = int(round((top + bottom) / 2))
                else:
                    click_x = int(round(float(badge["center_x"])))
                    click_y = int(round(float(badge["center_y"])))

                if self._point_in_bounds(click_x, click_y, bounds):
                    self.logger.info(
                        "Visual layout matched official-account verified badge row for '%s' at (%s, %s), badge=(%.1f, %.1f) area=%s",
                        account_name,
                        click_x,
                        click_y,
                        badge["center_x"],
                        badge["center_y"],
                        int(round(badge["area"])),
                    )
                    return {
                        "x": click_x,
                        "y": click_y,
                        "row_top": int(round(float(badge["top"]))),
                        "row_span": int(round(float(badge["right"]) - float(badge["left"]))),
                        "component_count": len(row_components) or 1,
                        "area": int(round(float(badge["area"]))),
                        "method": "visual_official_account_verified_badge",
                    }

            if not components:
                return None

            rows: List[Dict[str, Any]] = []
            row_threshold = max(8.0, 5.0 * scale_y)
            for component in sorted(components, key=lambda item: (item["center_y"], item["left"])):
                row = next(
                    (
                        item for item in rows
                        if abs(float(item["center_y"]) - float(component["center_y"])) <= row_threshold
                    ),
                    None,
                )
                if row is None:
                    rows.append({"center_y": component["center_y"], "components": [component]})
                else:
                    row["components"].append(component)
                    row["center_y"] = statistics.mean(
                        float(item["center_y"]) for item in row["components"]
                    )

            candidates: List[Dict[str, Any]] = []
            for row in rows:
                row_components = row["components"]
                left = min(float(item["left"]) for item in row_components)
                right = max(float(item["right"]) for item in row_components)
                top = min(float(item["top"]) for item in row_components)
                bottom = max(float(item["bottom"]) for item in row_components)
                total_area = sum(float(item["area"]) for item in row_components)
                span = right - left
                if span < 22 or total_area < 40:
                    continue

                click_x = int(round((left + right) / 2))
                click_y = int(round((top + bottom) / 2))
                if not self._point_in_bounds(click_x, click_y, bounds):
                    continue
                candidates.append({
                    "x": click_x,
                    "y": click_y,
                    "row_top": int(round(top)),
                    "row_span": int(round(span)),
                    "component_count": len(row_components),
                    "area": int(round(total_area)),
                    "method": "visual_official_account_title_row",
                })

            if not candidates:
                return None

            candidates.sort(key=lambda item: (item["row_top"], -item["area"]))
            match = candidates[0]
            self.logger.info(
                "Visual layout matched official-account name text row for '%s' at (%s, %s), row_top=%s span=%s components=%s area=%s",
                account_name,
                match["x"],
                match["y"],
                match["row_top"],
                match["row_span"],
                match["component_count"],
                match["area"],
            )
            return match
        except Exception as exc:
            self.logger.debug("Visual account-result locator failed: %s", exc)
            return None

    async def _locate_search_bar_by_accessibility(
        self, bounds: Dict[str, int]
    ) -> Optional[Dict[str, Any]]:
        """Use macOS/Windows accessibility metadata before visual heuristics."""
        accessibility_service = getattr(self, "accessibility_service", None)
        if accessibility_service:
            search_region = self._search_sidebar_bounds(bounds)
            match = accessibility_service.find_named_element(
                ["搜索", "Search"],
                region=search_region,
                allowed_roles=[
                    "axsearchfield",
                    "axtextfield",
                    "axtextfield",
                    "axgroup",
                    "textfield",
                    "searchfield",
                    "group",
                ],
                min_similarity=0.68,
            )
            if match and self._point_in_bounds(int(match["x"]), int(match["y"]), bounds):
                return {
                    "x": int(match["x"]),
                    "y": int(match["y"]),
                    "method": match.get("method", "accessibility"),
                    "confidence": float(match.get("confidence", 0.9)),
                    "label": match.get("text") or match.get("matched_target") or "搜索",
                }
        return None

    async def _locate_search_bar_by_ocr(self, bounds: Dict[str, int]) -> Optional[Dict[str, Any]]:
        if not self.ocr_enabled or not self.ocr_processor or not self.adaptive_ocr:
            return None

        screenshot = self._capture_window_screenshot(bounds)
        if screenshot is None:
            return None

        # WeChat desktop search sits in the upper-left navigation/sidebar area.
        search_bounds = self._search_sidebar_bounds(bounds)
        for label in ("搜索", "Search"):
            match = self._find_best_ocr_text_match(
                screenshot,
                label,
                bounds=search_bounds,
                min_similarity=0.6,
                min_confidence=20,
            )
            if match:
                match.update({"method": "ocr", "label": label})
                return match
        return None

    async def _locate_search_bar_by_unified(self, bounds: Dict[str, int]) -> Optional[Dict[str, Any]]:
        if not getattr(self, "ocr_processor", None) or not getattr(self, "unified_element_locator", None):
            return None

        screenshot = self._capture_window_screenshot(bounds)
        if screenshot is None:
            return None

        try:
            await self._await_with_timeout(
                "UnifiedElementLocator initialization",
                self._ensure_unified_locator_initialized(),
                WECHAT_UNIFIED_LOCATOR_TIMEOUT_SECONDS,
                default=None,
            )
            if not self._unified_locator_initialized:
                return None
            element_result = await self._await_with_timeout(
                "UnifiedElementLocator search bar lookup",
                self.unified_element_locator.locate_element(
                    screenshot,
                    "搜索框",
                    None,
                ),
                WECHAT_UNIFIED_LOCATOR_TIMEOUT_SECONDS,
                default=None,
            )
        except Exception as exc:
            self.logger.warning("UnifiedElementLocator search bar lookup failed: %s", exc)
            return None

        if not element_result:
            return None

        center_x, center_y = element_result.bbox.center
        screen_x, screen_y = self._image_point_to_screen(center_x, center_y, screenshot)
        if not self._point_in_bounds(screen_x, screen_y, bounds):
            return None

        return {
            "x": screen_x,
            "y": screen_y,
            "method": element_result.strategy_used.value,
            "confidence": element_result.confidence.value,
        }

    def _locate_search_bar_by_layout(self, bounds: Dict[str, int]) -> Optional[Dict[str, Any]]:
        """Last-resort deterministic WeChat layout estimate inside the sidebar."""
        candidates = [
            (bounds["X"] + int(bounds["Width"] * 0.18), bounds["Y"] + self._scale_window_y(bounds, 28)),
            (bounds["X"] + int(bounds["Width"] * 0.22), bounds["Y"] + self._scale_window_y(bounds, 28)),
            (bounds["X"] + int(bounds["Width"] * 0.16), bounds["Y"] + self._scale_window_y(bounds, 32)),
        ]
        for x, y in candidates:
            if self._point_in_bounds(x, y, bounds):
                return {
                    "x": x,
                    "y": y,
                    "method": "wechat_sidebar_layout",
                    "confidence": 0.35,
                }
        return None

    def _search_bar_click_target(
        self,
        bounds: Dict[str, int],
        candidate: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Move a visual search-bar hit to a stable point inside the input field."""
        raw_x = int(candidate.get("x", bounds["X"] + 120))
        raw_y = int(candidate.get("y", bounds["Y"] + 52))

        sidebar_limit = bounds["X"] + min(
            max(int(bounds["Width"] * 0.38), self._scale_window_x(bounds, 240)),
            self._scale_window_x(bounds, 430),
        )
        min_x = bounds["X"] + self._scale_window_x(bounds, 72)
        max_x = max(min_x, sidebar_limit - 24)
        click_x = max(min_x, min(raw_x, max_x))

        top_min = bounds["Y"] + self._scale_window_y(bounds, 28)
        top_max = bounds["Y"] + max(
            self._scale_window_y(bounds, 72),
            min(self._scale_window_y(bounds, 120), int(bounds["Height"] * 0.18)),
        )
        layout_y = bounds["Y"] + min(
            max(self._scale_window_y(bounds, 50), int(bounds["Height"] * 0.07)),
            self._scale_window_y(bounds, 78),
        )

        method = candidate.get("method")
        if method == "wechat_sidebar_layout":
            click_y = raw_y
        elif top_min <= raw_y <= top_max:
            click_y = raw_y
        else:
            click_y = layout_y

        adjusted = dict(candidate)
        adjusted.update({
            "x": int(click_x),
            "y": int(click_y),
            "raw_x": raw_x,
            "raw_y": raw_y,
        })
        if (raw_x, raw_y) != (adjusted["x"], adjusted["y"]):
            self.logger.info(
                "Adjusted search bar click target from (%s, %s) to (%s, %s)",
                raw_x,
                raw_y,
                adjusted["x"],
                adjusted["y"],
            )
        return adjusted

    async def _locate_search_bar(self, bounds: Dict[str, int]) -> Optional[Dict[str, Any]]:
        """Locate WeChat's search box with explicit, ordered strategies."""
        for strategy in (
            self._locate_search_bar_by_accessibility,
            self._locate_search_bar_by_ocr,
            lambda current_bounds: asyncio.sleep(0, result=self._locate_search_bar_by_layout(current_bounds)),
            self._locate_search_bar_by_unified,
        ):
            result = await strategy(bounds)
            if result:
                return self._search_bar_click_target(bounds, result)
        return None

    def _search_results_panel_bounds(
        self,
        bounds: Dict[str, int],
        region: Optional[Dict[str, int]] = None,
    ) -> Dict[str, int]:
        """Return the result-list area below the search input, excluding the query field."""
        overlay_bounds = self._search_results_overlay_bounds(bounds)
        base = region or overlay_bounds
        clamp_to_overlay = region is None or base["Width"] >= int(bounds["Width"] * 0.6)
        if clamp_to_overlay:
            base = overlay_bounds
        top_cutoff = bounds["Y"] + max(self._scale_window_y(bounds, 86), int(bounds["Height"] * 0.12))
        x = max(bounds["X"], base["X"])
        y = max(base["Y"], top_cutoff)
        right = min(bounds["X"] + bounds["Width"], base["X"] + base["Width"])
        if clamp_to_overlay:
            right = min(right, overlay_bounds["X"] + overlay_bounds["Width"])
        bottom = min(bounds["Y"] + bounds["Height"], base["Y"] + base["Height"])
        result = {
            "X": int(x),
            "Y": int(y),
            "Width": max(1, int(right - x)),
            "Height": max(1, int(bottom - y)),
        }
        return self._inherit_window_capture_metadata(result, bounds) or result

    def _right_article_panel_bounds(self, bounds: Dict[str, int]) -> Dict[str, int]:
        """Limit article extraction to the public-account content panel."""
        panel_x = bounds["X"] + int(bounds["Width"] * 0.36)
        panel_y = bounds["Y"] + max(self._scale_window_y(bounds, 60), int(bounds["Height"] * 0.08))
        region = {
            "X": panel_x,
            "Y": panel_y,
            "Width": max(1, bounds["X"] + bounds["Width"] - panel_x),
            "Height": max(1, bounds["Y"] + bounds["Height"] - panel_y - self._scale_window_y(bounds, 20)),
        }
        return self._inherit_window_capture_metadata(region, bounds) or region

    async def run_cycle(self, account_ids: List[str], max_articles: int = 3) -> AutomationResult:
        """Run automation cycle for multiple accounts"""
        start_time = time.time()
        try:

            self.logger.info(f"Running automation cycle for accounts: {account_ids}")

            results = []
            for account_id in account_ids:
                try:
                    self._close_front_auxiliary_wechat_windows()
                    await asyncio.sleep(0.5)
                    # Search for account
                    interaction_bounds = self._get_interaction_bounds()

                    if interaction_bounds:
                        search_result = await self.search_wechat_account(interaction_bounds, account_id)
                        if search_result.status == AutomationStatus.SUCCESS:
                            selected = await self.select_account_from_search_results(interaction_bounds, account_id)
                            if not selected:
                                results.append({
                                    "account": account_id,
                                    "search_success": True,
                                    "account_open_success": False,
                                    "articles_read": 0,
                                    "articles": [],
                                    "error": "Search succeeded but the matching official-account result was not clicked"
                                })
                                continue

                            self.logger.info(f"Successfully opened account: {account_id}, now reading articles")
                            await asyncio.sleep(2.0)
                            article_bounds = self._resolve_article_panel_bounds(interaction_bounds, account_id)
                            await self._scroll_article_list_to_top(account_id, article_bounds)
                            visible_articles = await self.list_latest_articles(
                                article_bounds,
                                max_articles=max_articles,
                            )
                            visible_titles = [
                                article.get("title", "").strip()
                                for article in visible_articles
                                if isinstance(article, dict) and article.get("title", "").strip()
                            ]
                            articles_result = await self.read_latest_articles(
                                article_bounds,
                                max_articles=max_articles,
                                article_window_title=account_id,
                            )

                            if articles_result or visible_titles:
                                articles_data: List[Dict[str, Any]] = []
                                if isinstance(articles_result, list):
                                    articles_data = self._merge_article_records(
                                        visible_articles,
                                        articles_result,
                                        max_articles,
                                    )
                                else:
                                    articles_data = self._merge_article_records(
                                        visible_articles,
                                        [],
                                        max_articles,
                                    )
                                    if not articles_data and articles_result:
                                        articles_data = [{
                                            "title": f"Article from {account_id}",
                                            "content": "",
                                            "read_success": bool(articles_result),
                                            "url": "",
                                            "link": "",
                                        }]
                                read_titles = [
                                    article.get("title", "").strip()
                                    for article in articles_data
                                    if article.get("title", "").strip()
                                ]
                                titles = self._merge_article_titles(read_titles, visible_titles, max_articles)

                                result_item = {
                                    "account": account_id,
                                    "search_success": True,
                                    "account_open_success": True,
                                    "title_list_success": bool(visible_titles),
                                    "titles": titles,
                                    "visible_articles": visible_articles,
                                    "visible_titles": visible_titles,
                                    "read_titles": read_titles,
                                    "articles_read": len(articles_data),
                                    "articles": articles_data
                                }
                                if visible_titles and not articles_data:
                                    result_item["warning"] = "Article titles were listed, but article reading returned no content"
                                results.append(result_item)
                            else:
                                results.append({
                                    "account": account_id,
                                    "search_success": True,
                                    "account_open_success": True,
                                    "title_list_success": False,
                                    "titles": [],
                                    "visible_titles": [],
                                    "read_titles": [],
                                    "articles_read": 0,
                                    "articles": [],
                                    "error": "No article titles found and failed to read articles"
                                })
                        else:
                            results.append({
                                "account": account_id,
                                "search_success": False,
                                "error": f"Search failed: {search_result.message}"
                            })
                    else:
                        results.append({
                            "account": account_id,
                            "search_success": False,
                            "error": "Failed to get window bounds and full-screen fallback bounds"
                        })
                except Exception as e:
                    results.append({
                        "account": account_id,
                        "search_success": False,
                        "error": str(e)
                    })

            execution_time = time.time() - start_time
            success_count = sum(1 for r in results if r.get("search_success", False) and not r.get("error"))
            overall_success = success_count == len(account_ids)
            total_articles = sum(r.get("articles_read", 0) for r in results)

            self.performance_monitor.record_operation("run_cycle", execution_time, overall_success)

            return AutomationResult(
                status=AutomationStatus.SUCCESS if overall_success else AutomationStatus.PARTIAL_SUCCESS,
                message=f"Automation cycle completed. Success: {success_count}/{len(account_ids)}, Articles read: {total_articles}",
                data={"results": results, "success_count": success_count, "total_articles_read": total_articles},
                execution_time=execution_time
            )
        except Exception as e:
            execution_time = time.time() - start_time
            self.performance_monitor.record_operation("run_cycle", execution_time, False)
            self.logger.error(f"Error running automation cycle: {e}")
            return AutomationResult(
                status=AutomationStatus.ERROR,
                message=f"Exception occurred: {e}",
                execution_time=execution_time,
                error_details=str(e)
            )

    # ====== Original API methods ======

    def search_public_account(self, account_name: str) -> bool:
        """Search for a public account (original API)"""
        with self.performance_monitor.measure_operation("search_public_account"):
            self.logger.info(f"Starting search for public account: {account_name}")

            if hasattr(self, 'search_navigator'):
                return self.search_navigator.search_public_account(account_name)
            else:
                self.logger.warning("SearchNavigator not available")
                return False

    def read_article(self, article_title: str) -> Optional[Dict[str, Any]]:
        """Read an article by title (original API)"""
        with self.performance_monitor.measure_operation("read_article"):
            self.logger.info(f"Starting article reading: {article_title}")

            if hasattr(self, 'article_reader'):
                article_content = self.article_reader.read_article(article_title)
                if article_content:
                    return {
                        "title": article_content.title,
                        "content": article_content.content,
                        "author": article_content.author,
                        "publish_time": article_content.publish_time,
                        "read_count": article_content.read_count
                    }
            return None

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance monitoring summary"""
        return self.performance_monitor.get_performance_summary()

    def cleanup_temp_files(self):
        """Clean up temporary files"""
        with self.performance_monitor.measure_operation("cleanup_temp_files"):
            self.logger.info("Cleaning up temporary files")
            if hasattr(self.ocr_processor, 'cleanup_all_screenshots'):
                self.ocr_processor.cleanup_all_screenshots()

    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status"""
        try:
            import psutil

            # Get process information
            process = psutil.Process()
            memory_info = process.memory_info()
            cpu_percent = process.cpu_percent()

            # Get system information
            system_memory = psutil.virtual_memory()
            system_cpu = psutil.cpu_percent()

            return {
                "process": {
                    "memory_mb": memory_info.rss / 1024 / 1024,
                    "cpu_percent": cpu_percent,
                    "pid": process.pid
                },
                "system": {
                    "memory_total_mb": system_memory.total / 1024 / 1024,
                    "memory_available_mb": system_memory.available / 1024 / 1024,
                    "memory_percent": system_memory.percent,
                    "cpu_percent": system_cpu
                },
                "automation": {
                    "config": {
                        "search_timeout": self.config.search_timeout,
                        "read_timeout": self.config.read_timeout,
                        "screenshot_dir": self.config.screenshot_dir,
                        "enable_performance_monitoring": self.config.enable_performance_monitoring
                    },
                    "mcp_available": MCP_AVAILABLE
                }
            }
        except Exception as e:
            self.logger.error(f"Error getting system status: {e}")
            return {"error": str(e)}

    def get_accessibility_status(self) -> Dict[str, Any]:
        """Return the current accessibility/assistive-access runtime status."""
        default_status = {
            "platform": platform.system().lower(),
            "adapter": None,
            "app_name": "WeChat",
            "ax_runtime_available": False,
            "native_ax_trusted": False,
            "native_ax_ready": False,
            "system_events_accessible": False,
            "system_events_ui_enabled": False,
            "system_events_ready": False,
            "assistive_access_denied": False,
            "system_events_error": "",
            "accessibility_available": False,
            "permission_required": False,
            "recommended_backend": "ocr_only",
            "settings_hint": None,
            "settings_url": None,
        }
        service = getattr(self, "accessibility_service", None)
        getter = getattr(service, "get_accessibility_status", None)
        if not callable(getter):
            return default_status
        try:
            status = getter(app_name="WeChat")
        except Exception as exc:
            self.logger.error("Error checking accessibility status: %s", exc)
            merged = dict(default_status)
            merged["error"] = str(exc)
            return merged
        if not isinstance(status, dict):
            return default_status
        merged = dict(default_status)
        merged.update(status)
        return merged

    def request_accessibility_permission(self) -> Dict[str, Any]:
        """Open the macOS Accessibility settings page and return current status."""
        default_response = {
            "success": False,
            "action_taken": "unsupported",
            "settings_opened": False,
            "status": self.get_accessibility_status(),
            "message": "Accessibility permission request is unavailable.",
        }
        service = getattr(self, "accessibility_service", None)
        requester = getattr(service, "request_accessibility_permission", None)
        if not callable(requester):
            return default_response
        try:
            response = requester(app_name="WeChat")
        except Exception as exc:
            self.logger.error("Error requesting accessibility permission: %s", exc)
            merged = dict(default_response)
            merged["message"] = str(exc)
            return merged
        if not isinstance(response, dict):
            return default_response
        merged = dict(default_response)
        merged.update(response)
        if not isinstance(merged.get("status"), dict):
            merged["status"] = self.get_accessibility_status()
        return merged

    def verify_environment(self) -> Dict[str, Any]:
        """Verify that the automation environment is properly configured"""
        try:
            # Check if WeChat is running
            wechat_running = self.window_manager.ensure_wechat_running()

            # Check if window is accessible
            window_accessible = self.window_manager.verify_visibility()

            # Check OCR capabilities
            ocr_working = self._test_ocr_capabilities()

            # Check GUI automation
            gui_working = self._test_gui_automation()

            accessibility_status = self.get_accessibility_status()
            accessibility_ready = bool(accessibility_status.get("accessibility_available"))

            return {
                "wechat_running": wechat_running,
                "window_accessible": window_accessible,
                "ocr_working": ocr_working,
                "gui_working": gui_working,
                "accessibility": accessibility_status,
                "accessibility_ready": accessibility_ready,
                "all_components_ready": all([
                    wechat_running,
                    window_accessible,
                    ocr_working,
                    gui_working,
                    accessibility_ready,
                ])
            }
        except Exception as e:
            self.logger.error(f"Error verifying environment: {e}")
            return {"error": str(e)}

    def _test_ocr_capabilities(self) -> bool:
        """Test OCR functionality"""
        try:
            # Try to capture a screenshot
            screenshot = self.ocr_processor.capture_screenshot()
            if screenshot is None:
                return False

            # Try to perform OCR recognition
            results = self.adaptive_ocr.recognize(screenshot)
            return len(results) > 0
        except Exception as e:
            self.logger.error(f"OCR test failed: {e}")
            return False

    def _test_gui_automation(self) -> bool:
        """Test GUI automation capabilities"""
        try:
            # Try to get window bounds
            bounds_result = self.get_wechat_window_bounds()
            if bounds_result.status != AutomationStatus.SUCCESS:
                return False

            bounds = bounds_result.data["bounds"]

            # Try a simple click operation
            click_result = self.click_at(bounds['X'] + 10, bounds['Y'] + 10)
            return click_result.status == AutomationStatus.SUCCESS
        except Exception as e:
            self.logger.error(f"GUI automation test failed: {e}")
            return False

    def run_health_check(self) -> Dict[str, Any]:
        """Run comprehensive health check"""
        try:
            self.logger.info("Running health check")

            # Environment verification
            env_status = self.verify_environment()

            # Performance metrics
            perf_summary = self.get_performance_summary()

            # System status
            system_status = self.get_system_status()

            # Health check results
            health_status = {
                "timestamp": time.time(),
                "environment": env_status,
                "performance": perf_summary,
                "system": system_status,
                "overall_status": "HEALTHY" if env_status.get("all_components_ready", False) else "UNHEALTHY"
            }

            self.logger.info(f"Health check completed: {health_status['overall_status']}")
            return health_status
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return {"error": str(e), "overall_status": "ERROR"}

    # ====== OCR/LLM Intelligent Methods ======

    async def _locate_and_click_search_bar_simple(self, bounds: Dict[str, int]) -> bool:
        """
        使用统一的 OCR+LLM 智能定位并点击搜索框

        Args:
            bounds: 窗口边界 {'X': x, 'Y': y, 'Width': w, 'Height': h}

        Returns:
            bool: 是否成功定位并点击搜索框
        """
        try:
            await asyncio.sleep(0.3)

            search_bar = await self._locate_search_bar(bounds)
            if search_bar:
                self.logger.info(
                    "搜索框定位成功: (%s, %s), 方法: %s, 置信度: %s",
                    search_bar["x"],
                    search_bar["y"],
                    search_bar.get("method"),
                    search_bar.get("confidence"),
                )
                click_result = self.click_at(search_bar["x"], search_bar["y"])
                if click_result.status == AutomationStatus.SUCCESS:
                    await asyncio.sleep(1.0)
                    return True
                self.logger.error("点击搜索框失败: %s", click_result.message)

            self.logger.error("无法定位搜索框")
            return False

        except Exception as e:
            self.logger.error(f"定位搜索框失败: {e}")
            return False

    def _verify_search_query_visible(
        self,
        account_name: str,
        bounds: Optional[Dict[str, int]] = None,
    ) -> bool:
        """Verify that the typed query is visible in the search UI."""
        if not bounds or not self.ocr_processor:
            return True

        input_region = self._search_input_text_region(bounds)
        input_texts = self._collect_region_surface_texts(
            input_region,
            min_confidence=12.0,
            allowed_roles=[
                "axstatictext",
                "axtextfield",
                "axgroup",
                "text",
                "textfield",
                "group",
            ],
        )
        if input_texts and self._has_account_name_evidence(
            input_texts,
            account_name,
            min_similarity=0.82,
        ):
            self.logger.info("搜索输入验证成功: 搜索框文本=%s", input_texts[:6])
            return True

        input_screenshot = self._capture_region_screenshot(
            input_region,
            expected_bounds=bounds,
        )
        screenshot = self._capture_window_screenshot(bounds)
        if input_screenshot is None and screenshot is None:
            self.logger.warning("无法截图验证搜索输入，跳过严格校验")
            return True

        if self.adaptive_ocr and input_screenshot is not None:
            exact_match = self._find_best_ocr_text_match(
                input_screenshot,
                account_name,
                bounds=input_region,
                min_similarity=0.72,
                min_confidence=15,
            )
            if exact_match:
                self.logger.info(
                    "搜索输入验证成功: OCR saw '%s' for '%s'",
                    exact_match["text"],
                    account_name,
                )
                return True

            try:
                ocr_results = self.adaptive_ocr.recognize(input_screenshot)
            except Exception as exc:
                self.logger.warning("搜索输入验证 OCR 失败: %s", exc)
                ocr_results = []

            recognized_text = " ".join((r.get("text") or "") for r in ocr_results)
            compact = "".join(recognized_text.split())
            query = "".join(account_name.split())
            if query and query in compact:
                self.logger.info("搜索输入验证成功: %s", account_name)
                return True

        if screenshot is not None and self._search_input_query_pixels_present(screenshot, bounds, account_name):
            self.logger.info("搜索输入验证成功: 像素校验命中")
            return True

        self.logger.warning(
            "搜索输入验证失败: 未在搜索区域看到 '%s'，输入框文本=%s",
            account_name,
            input_texts[:8],
        )
        return False

    async def _input_account_name(
        self,
        account_name: str,
        time_module,
        bounds: Optional[Dict[str, int]] = None,
    ) -> bool:
        """
        输入公众号名称并触发搜索

        Args:
            account_name: 公众号名称
            time_module: time 模块

        Returns:
            bool: 是否成功输入
        """
        try:
            self.logger.info(f"输入公众号名称: {account_name}")

            # The search field should already be focused by the preceding click.
            # Do not activate the app again here because that can move focus away
            # from the field; only verify WeChat still owns the keyboard.
            if not self._has_recent_wechat_focus() and not self._ensure_wechat_frontmost(activate=False):
                self.logger.info("Typing step lost WeChat focus; reactivating before input")
                if not self._ensure_wechat_frontmost(activate=True):
                    return False
                if bounds and not self._refocus_search_input(bounds):
                    self.logger.error("重新聚焦微信搜索输入框失败")
                    return False
            time_module.sleep(0.2)

            for attempt in range(2):
                if attempt > 0:
                    self.logger.warning("搜索词校验失败，重试输入公众号名称: %s", account_name)
                    if bounds and not self._refocus_search_input(bounds):
                        self.logger.error("重试前重新聚焦微信搜索输入框失败")
                        return False
                    time_module.sleep(0.2)

                # 清空搜索框 - 通过统一包装复用 recent-focus 宽限和前台恢复逻辑
                self.logger.debug("清空搜索框...")
                if not self.clear_input():
                    return False
                time_module.sleep(0.25)

                if not self._has_recent_wechat_focus() and not self._ensure_wechat_frontmost(activate=False):
                    self.logger.info("Search input lost WeChat focus after clear; reactivating before typing")
                    if not self._ensure_wechat_frontmost(
                        activate=True,
                        attempts=2,
                        settle_seconds=0.45,
                    ):
                        self.logger.error("清空后重新激活微信失败")
                        return False
                    if bounds and not self._refocus_search_input(bounds):
                        self.logger.error("清空后重新聚焦微信搜索输入框失败")
                        return False
                    time_module.sleep(0.15)

                # 输入公众号名称 - 使用粘贴方式输入中文，避免输入法冲突
                self.logger.debug(f"开始输入: {account_name}")
                type_result = self.type_text(account_name, ensure_focus=True)
                if not type_result:
                    self.logger.error("type_text 返回失败")
                    return False

                # 等待一下让输入稳定
                time_module.sleep(0.8)
                if self._verify_search_query_visible(account_name, bounds):
                    break
            else:
                self.logger.error("输入后没有看到对应搜索文字，停止后续结果点击")
                return False
            
            self.logger.info(f"成功输入: {account_name}")
            
            # 微信搜索框输入后会自动显示搜索结果，不需要按回车
            # 按回车反而会导致搜索内容消失或页面跳转
            
            # 等待搜索结果显示
            time_module.sleep(2.0)
            return True

        except Exception as e:
            self.logger.error(f"输入公众号名称失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False

    async def _capture_search_results(self, bounds: Dict[str, int], time_module) -> Optional[Dict[str, int]]:
        """
        捕获搜索结果区域（使用 OCR 智能识别，如果启用）

        Args:
            bounds: 窗口边界
            time_module: time 模块

        Returns:
            搜索结果区域的边界，或 None
        """
        try:
            if not self.ocr_enabled:
                self.logger.warning("OCR is disabled, using default search results region")
                # 使用默认搜索结果区域
                default_region = {
                    'X': bounds['X'],
                    'Y': bounds['Y'],
                    'Width': bounds['Width'],
                    'Height': bounds['Height']
                }
                return default_region

            self.logger.info("使用 OCR 智能识别搜索结果区域")

            # 等待搜索结果加载
            time_module.sleep(1)

            # 捕获截图
            screenshot = self._capture_window_screenshot(bounds)
            if screenshot is None:
                self.logger.error("无法获取截图")
                return None

            # 使用 OCR 识别搜索结果
            ocr_results = self.adaptive_ocr.recognize(screenshot)

            # 查找搜索结果相关的关键词
            result_keywords = ["公众号", "文章", "联系人", "Official Account"]

            # 找到搜索结果区域的边界
            min_x = float('inf')
            min_y = float('inf')
            max_x = float('-inf')
            max_y = float('-inf')
            found = False

            for result in ocr_results:
                text = result.get('text', '')
                for keyword in result_keywords:
                    if keyword in text:
                        found = True
                        position = self._ocr_position(result)
                        left = position["x"]
                        top = position["y"]
                        right = left + position["width"]
                        bottom = top + position["height"]

                        min_x = min(min_x, left)
                        min_y = min(min_y, top)
                        max_x = max(max_x, right)
                        max_y = max(max_y, bottom)
                        self.logger.debug(f"找到搜索结果关键词: {text} at ({left}, {top})")

            if found:
                # 扩展边界以包含整个搜索结果区域
                padding = 20
                search_results_region = {
                    'X': max(bounds['X'], int(min_x) - padding),
                    'Y': max(bounds['Y'], int(min_y) - padding),
                    'Width': min(bounds['Width'], int(max_x - min_x) + 2 * padding),
                    'Height': min(bounds['Height'], int(max_y - min_y) + 2 * padding)
                }
                self.logger.info(f"OCR 识别搜索结果区域: {search_results_region}")
                return search_results_region

            self.logger.warning("未通过 OCR 识别到搜索结果区域")
            return None

        except Exception as e:
            self.logger.error(f"OCR 识别搜索结果区域失败: {e}")
            return None

    async def _find_and_click_account_in_results(
        self,
        search_results_region: Dict[str, int],
        account_name: str,
        bounds: Dict[str, int],
        allow_official_accounts_retry: bool = True,
        allow_search_commit_retry: bool = True,
        allow_container_result_click: bool = True,
        allow_preview_row_click: bool = True,
        prefer_small_child_surface: bool = False,
        base_window_bounds: Optional[Dict[str, int]] = None,
    ) -> bool:
        """
        在搜索结果中查找并点击指定的公众号

        Args:
            search_results_region: 搜索结果区域边界
            account_name: 公众号名称
            bounds: 窗口边界

        Returns:
            bool: 是否成功点击
        """
        try:
            self.logger.info(f"在搜索结果中查找公众号: {account_name}")
            root_window_bounds = base_window_bounds or bounds
            search_surface_bounds = self._resolve_search_surface_bounds(
                bounds,
                allow_small_child=prefer_small_child_surface,
                account_name=account_name,
            )
            region_hint = (
                search_results_region
                if self._bounds_roughly_match(search_surface_bounds, bounds)
                else None
            )
            effective_region = self._search_results_panel_bounds(search_surface_bounds, region_hint)
            self.logger.info("搜索结果点击区域: %s", effective_region)
            account_result_ocr = self._get_account_result_ocr_engine()
            official_account_region = self._resolve_official_accounts_preview_region(
                search_surface_bounds,
                effective_region,
                account_result_ocr,
            )
            self.logger.info("公众号分组点击区域: %s", official_account_region)
            accessibility_service = getattr(self, "accessibility_service", None)
            result_texts: List[str] = []
            scoped_texts: List[str] = []
            has_target_evidence = False
            accessibility_texts: List[str] = []

            if accessibility_service:
                for region in (official_account_region, effective_region):
                    accessibility_texts.extend(
                        accessibility_service.collect_texts(
                            region=region,
                            allowed_roles=[
                                "axrow",
                                "axstatictext",
                                "axbutton",
                                "axgroup",
                                "row",
                                "text",
                                "button",
                                "group",
                            ],
                        )
                    )
                accessibility_texts = self._dedupe_surface_texts(accessibility_texts)
                if accessibility_texts:
                    self.logger.info("搜索结果 Accessibility 文本: %s", accessibility_texts[:20])
                has_target_evidence = self._has_account_name_evidence(accessibility_texts, account_name)

                for region in (official_account_region, effective_region):
                    match = accessibility_service.find_named_element(
                        account_name,
                        region=region,
                        allowed_roles=[
                            "axrow",
                            "axstatictext",
                            "axbutton",
                            "axgroup",
                            "row",
                            "text",
                            "button",
                            "group",
                        ],
                        min_similarity=0.62,
                        blocked_terms=["文章", "视频号", "朋友圈"],
                    )
                    if not match:
                        continue
                    self.logger.info(
                        "Accessibility matched account '%s' at (%s, %s) confidence=%.2f region=%s",
                        match.get("text") or account_name,
                        match["x"],
                        match["y"],
                        float(match.get("confidence", 0.0)),
                        region,
                    )
                    click_x = int(match["x"])
                    click_y = int(match["y"])
                    alternate_clicks: List[Tuple[int, int]] = []
                    matched_text = match.get("text") or ""
                    if not self._is_exact_account_name_match(matched_text, account_name):
                        if not self._is_target_account_preview_match(matched_text, account_name):
                            self.logger.info(
                                "Skipping non-exact accessibility account match for '%s': %s",
                                account_name,
                                matched_text,
                            )
                            continue
                    if self._is_target_account_preview_match(matched_text, account_name):
                        preferred_attempted = False
                        if allow_official_accounts_retry:
                            preferred_attempted = True
                            preferred = await self._prefer_official_accounts_surface_for_preview_match(
                                search_surface_bounds,
                                effective_region,
                                account_name,
                                account_result_ocr,
                                official_account_region=official_account_region,
                                detected_texts=accessibility_texts + result_texts + scoped_texts,
                                allow_container_result_click=allow_container_result_click,
                            )
                            if preferred:
                                return True
                        if preferred_attempted:
                            self.logger.info(
                                "Official Accounts 专用结果面重试未打开目标账号，跳过原始 Accessibility 预览命中: %s",
                                match.get("text") or account_name,
                            )
                            continue
                        if not allow_preview_row_click:
                            if await self._open_target_account_from_official_accounts_preview(
                                search_surface_bounds,
                                account_name,
                            ):
                                return True
                            self.logger.info(
                                "当前重试阶段禁止直接点击预览型结果，跳过 Accessibility 预览命中: %s",
                                match.get("text") or account_name,
                            )
                            continue
                        alternate_clicks.append((int(match["x"]), int(match["y"])))
                        click_x, click_y = self._search_result_row_click_point(
                            search_surface_bounds,
                            region,
                            match,
                        )
                        self.logger.info(
                            "Accessibility account preview '%s' adjusted to row click (%s, %s)",
                            match.get("text"),
                            click_x,
                            click_y,
                        )
                    click_result = self.click_at(click_x, click_y)
                    if click_result.status == AutomationStatus.SUCCESS:
                        return await self._ensure_account_page_open(
                            search_surface_bounds,
                            account_name,
                            click_x,
                            click_y,
                            alternate_clicks=alternate_clicks,
                        )

            official_retry_attempted = False
            if account_result_ocr:
                results_screenshot = self._capture_region_screenshot(
                    effective_region,
                    expected_bounds=search_surface_bounds,
                )
                if results_screenshot is not None:
                    result_texts = self._extract_region_ocr_texts(effective_region, min_confidence=18.0)
                    if result_texts:
                        self.logger.info("搜索结果 OCR 文本: %s", result_texts[:20])
                    has_target_evidence = self._has_account_name_evidence(result_texts, account_name)
                    surface_looks_misfocused = self._looks_like_misfocused_search_results_surface(result_texts)
                    if (
                        allow_official_accounts_retry
                        and account_result_ocr
                        and surface_looks_misfocused
                    ):
                        self.logger.info(
                            "搜索结果区域疑似聊天列表/错误前台面板%s，通过公众号目录重试: %s",
                            "（即使已识别到目标词）" if has_target_evidence else "",
                            account_name,
                        )
                        opened_official_accounts = await self._reset_search_and_open_official_accounts_surface(
                            search_surface_bounds,
                            account_name,
                            account_result_ocr,
                        )
                        if not opened_official_accounts:
                            opened_official_accounts = await self._open_official_accounts_search_entry(
                                search_surface_bounds,
                                effective_region,
                                account_result_ocr,
                                account_name=account_name,
                                official_account_region=official_account_region,
                                detected_texts=accessibility_texts + result_texts,
                            )
                        official_retry_attempted = True
                        if opened_official_accounts:
                            await asyncio.sleep(1.2)
                            retry_bounds = self._resolve_search_surface_bounds(
                                search_surface_bounds,
                                allow_small_child=True,
                                account_name=account_name,
                            )
                            return await self._find_and_click_account_in_results(
                                retry_bounds,
                                account_name,
                                retry_bounds,
                                allow_official_accounts_retry=False,
                                allow_search_commit_retry=False,
                                allow_container_result_click=allow_container_result_click,
                                allow_preview_row_click=False,
                                prefer_small_child_surface=True,
                                base_window_bounds=root_window_bounds,
                            )
                    match = self._find_best_ocr_text_match(
                        results_screenshot,
                        account_name,
                        bounds=effective_region,
                        min_similarity=0.58,
                        min_confidence=18,
                        ocr_engine=account_result_ocr,
                    )
                    if match:
                        self.logger.info(
                            "Search-results OCR matched account '%s' for '%s' at (%s, %s), similarity=%.2f confidence=%.1f",
                            match["text"],
                            account_name,
                            match["x"],
                            match["y"],
                            match["similarity"],
                            match["confidence"],
                        )
                        click_x = match["x"]
                        click_y = match["y"]
                        alternate_clicks: List[Tuple[int, int]] = []
                        if not self._is_exact_account_name_match(match["text"], account_name):
                            if not self._is_target_account_preview_match(match["text"], account_name):
                                self.logger.info(
                                    "Skipping non-exact OCR account match for '%s': %s",
                                    account_name,
                                    match["text"],
                                )
                                match = None
                        if match and self._is_target_account_preview_match(match["text"], account_name):
                            preferred_attempted = False
                            if allow_official_accounts_retry:
                                preferred_attempted = True
                                preferred = await self._prefer_official_accounts_surface_for_preview_match(
                                    search_surface_bounds,
                                    effective_region,
                                    account_name,
                                    account_result_ocr,
                                    official_account_region=official_account_region,
                                    detected_texts=accessibility_texts + result_texts + scoped_texts,
                                    allow_container_result_click=allow_container_result_click,
                                )
                                if preferred:
                                    return True
                            if preferred_attempted:
                                self.logger.info(
                                    "Official Accounts 专用结果面重试未打开目标账号，跳过原始 OCR 预览命中: %s",
                                    match["text"],
                                )
                                match = None
                            if match and not allow_preview_row_click:
                                if await self._open_target_account_from_official_accounts_preview(
                                    search_surface_bounds,
                                    account_name,
                                ):
                                    return True
                                self.logger.info(
                                    "当前重试阶段禁止直接点击预览型结果，跳过 OCR 预览命中: %s",
                                    match["text"],
                                )
                                match = None
                            elif match:
                                alternate_clicks.append((int(match["x"]), int(match["y"])))
                                click_x, click_y = self._search_result_row_click_point(
                                    search_surface_bounds,
                                    effective_region,
                                    match,
                                )
                                self.logger.info(
                                    "Search-result preview '%s' adjusted to row click (%s, %s)",
                                    match["text"],
                                    click_x,
                                    click_y,
                                )
                        if match:
                            click_result = self.click_at(click_x, click_y)
                            if click_result.status == AutomationStatus.SUCCESS:
                                return await self._ensure_account_page_open(
                                    search_surface_bounds,
                                    account_name,
                                    click_x,
                                    click_y,
                                    alternate_clicks=alternate_clicks,
                                )

            # Prefer region-scoped OCR for the official-account section. Full-screen
            # crops are fragile on multi-display setups and when other windows
            # overlap the virtual desktop.
            scoped_screenshot = self._capture_region_screenshot(
                official_account_region,
                expected_bounds=search_surface_bounds,
            )
            if scoped_screenshot is None:
                self.logger.error("无法获取公众号分组截图")
                return False

            scoped_texts = self._extract_region_ocr_texts(official_account_region, min_confidence=18.0)
            if scoped_texts:
                self.logger.info("公众号分组 OCR 文本: %s", scoped_texts[:12])
            has_target_evidence = has_target_evidence or self._has_account_name_evidence(
                scoped_texts,
                account_name,
            )
            current_surface_texts = self._dedupe_surface_texts(
                accessibility_texts + result_texts + scoped_texts
            )

            if current_surface_texts and self._looks_like_official_account_panel(
                current_surface_texts,
                account_name,
            ):
                self.logger.info(
                    "搜索结果阶段已检测到目标公众号/文章页已打开，直接结束账号选择: %s",
                    account_name,
                )
                return True

            if (
                prefer_small_child_surface
                and not self._bounds_roughly_match(search_surface_bounds, root_window_bounds)
                and not (accessibility_texts or result_texts or scoped_texts)
            ):
                self.logger.info(
                    "Dedicated child search surface produced no usable texts for %s; falling back to main window search surface",
                    account_name,
                )
                return await self._find_and_click_account_in_results(
                    root_window_bounds,
                    account_name,
                    root_window_bounds,
                    allow_official_accounts_retry=allow_official_accounts_retry,
                    allow_search_commit_retry=allow_search_commit_retry,
                    allow_container_result_click=allow_container_result_click,
                    allow_preview_row_click=allow_preview_row_click,
                    prefer_small_child_surface=False,
                    base_window_bounds=root_window_bounds,
                )

            if account_result_ocr:
                if not self.ocr_enabled:
                    self.logger.info("全局 OCR 已关闭，使用搜索结果区域的受控 OCR fallback 定位公众号")
                match = self._find_best_ocr_text_match(
                    scoped_screenshot,
                    account_name,
                    bounds=official_account_region,
                    min_similarity=0.60,
                    min_confidence=18,
                    ocr_engine=account_result_ocr,
                )
                if match:
                    self.logger.info(
                        "Scoped OCR matched account result '%s' for '%s' at (%s, %s), similarity=%.2f confidence=%.1f",
                        match["text"],
                        account_name,
                        match["x"],
                        match["y"],
                        match["similarity"],
                        match["confidence"],
                    )
                    click_x = match["x"]
                    click_y = match["y"]
                    alternate_clicks: List[Tuple[int, int]] = []
                    if not self._is_exact_account_name_match(match["text"], account_name):
                        if not self._is_target_account_preview_match(match["text"], account_name):
                            self.logger.info(
                                "Skipping non-exact scoped OCR account match for '%s': %s",
                                account_name,
                                match["text"],
                            )
                            match = None
                    if match and self._is_target_account_preview_match(match["text"], account_name):
                        preferred_attempted = False
                        if allow_official_accounts_retry:
                            preferred_attempted = True
                            preferred = await self._prefer_official_accounts_surface_for_preview_match(
                                search_surface_bounds,
                                effective_region,
                                account_name,
                                account_result_ocr,
                                official_account_region=official_account_region,
                                detected_texts=accessibility_texts + result_texts + scoped_texts,
                                allow_container_result_click=allow_container_result_click,
                            )
                            if preferred:
                                return True
                        if preferred_attempted:
                            self.logger.info(
                                "Official Accounts 专用结果面重试未打开目标账号，跳过原始 Scoped OCR 预览命中: %s",
                                match["text"],
                            )
                            match = None
                        if match and not allow_preview_row_click:
                            if await self._open_target_account_from_official_accounts_preview(
                                search_surface_bounds,
                                account_name,
                            ):
                                return True
                            self.logger.info(
                                "当前重试阶段禁止直接点击预览型结果，跳过 Scoped OCR 预览命中: %s",
                                match["text"],
                            )
                            match = None
                        elif match:
                            alternate_clicks.append((int(match["x"]), int(match["y"])))
                            click_x, click_y = self._search_result_row_click_point(
                                search_surface_bounds,
                                official_account_region,
                                match,
                            )
                            self.logger.info(
                                "Scoped account preview '%s' adjusted to row click (%s, %s)",
                                match["text"],
                                click_x,
                                click_y,
                            )
                    if match:
                        click_result = self.click_at(click_x, click_y)
                        if click_result.status == AutomationStatus.SUCCESS:
                            return await self._ensure_account_page_open(
                                search_surface_bounds,
                                account_name,
                                click_x,
                                click_y,
                                alternate_clicks=alternate_clicks,
                            )

            if has_target_evidence and allow_container_result_click:
                opened_from_container = await self._open_official_accounts_container_result(
                    search_surface_bounds,
                    effective_region,
                    account_name,
                    account_result_ocr,
                    official_account_region=official_account_region,
                    detected_texts=accessibility_texts + result_texts + scoped_texts,
                    allow_retry=False,
                )
                if opened_from_container:
                    return True

            if not has_target_evidence and allow_search_commit_retry:
                self.logger.info(
                    "搜索结果缺少目标公众号证据，先发送 Enter 触发正式搜索后再重试: %s",
                    account_name,
                )
                if self.press_key("enter"):
                    await asyncio.sleep(1.2)
                    retry_bounds = self._resolve_search_surface_bounds(
                        search_surface_bounds,
                        allow_small_child=prefer_small_child_surface,
                    )
                    retried = await self._find_and_click_account_in_results(
                        retry_bounds,
                        account_name,
                        retry_bounds,
                        allow_official_accounts_retry=allow_official_accounts_retry,
                        allow_search_commit_retry=False,
                        allow_container_result_click=allow_container_result_click,
                        allow_preview_row_click=allow_preview_row_click,
                        prefer_small_child_surface=prefer_small_child_surface,
                        base_window_bounds=root_window_bounds,
                    )
                    if retried:
                        return True

            if (
                not has_target_evidence
                and not official_retry_attempted
                and allow_official_accounts_retry
                and account_result_ocr
            ):
                self.logger.info(
                    "搜索结果缺少目标公众号证据，优先重置搜索态并通过公众号目录重试: %s",
                    account_name,
                )
                opened_official_accounts = await self._reset_search_and_open_official_accounts_surface(
                    search_surface_bounds,
                    account_name,
                    account_result_ocr,
                )
                if not opened_official_accounts:
                    opened_official_accounts = await self._open_official_accounts_search_entry(
                        search_surface_bounds,
                        effective_region,
                        account_result_ocr,
                        account_name=account_name,
                        official_account_region=official_account_region,
                        detected_texts=accessibility_texts + result_texts + scoped_texts,
                    )
                if opened_official_accounts:
                    await asyncio.sleep(1.2)
                    retry_bounds = self._resolve_search_surface_bounds(
                        search_surface_bounds,
                        allow_small_child=True,
                    )
                    return await self._find_and_click_account_in_results(
                        retry_bounds,
                        account_name,
                        retry_bounds,
                        allow_official_accounts_retry=False,
                        allow_search_commit_retry=False,
                        allow_container_result_click=allow_container_result_click,
                        allow_preview_row_click=False,
                        prefer_small_child_surface=True,
                        base_window_bounds=root_window_bounds,
                    )

            if not has_target_evidence:
                self.logger.warning(
                    "搜索结果中缺少目标公众号 '%s' 的文本证据，停止兜底点击以避免误触",
                    account_name,
                )
                return False

            # Capture once more in full-screen mode only for visual fallbacks.
            screenshot = self._capture_window_screenshot(bounds)
            if screenshot is None:
                self.logger.error("无法获取全屏截图")
                return False

            visual_match = self._find_account_result_by_visual_layout(
                screenshot,
                search_surface_bounds,
                account_name,
            )
            if visual_match:
                self.logger.info(
                    "使用视觉布局定位公众号分组账号行: (%s, %s) method=%s",
                    visual_match["x"],
                    visual_match["y"],
                    visual_match.get("method"),
                )
                click_result = self.click_at(visual_match["x"], visual_match["y"])
                if click_result.status == AutomationStatus.SUCCESS:
                    return await self._ensure_account_page_open(
                        search_surface_bounds,
                        account_name,
                        visual_match["x"],
                        visual_match["y"],
                    )

            # 如果没有启用 OCR 或 OCR 没有找到，尝试使用 LLM
            if self.llm_enabled and self.llm_element_locator:
                self.logger.info("使用 LLM 查找公众号")
                try:
                    llm_result = await self._await_with_timeout(
                        f"LLM account lookup for {account_name}",
                        self.llm_element_locator.find_element_by_name(
                            screenshot, account_name, official_account_region
                        ),
                        WECHAT_LLM_LOCATOR_TIMEOUT_SECONDS,
                        default=None,
                    )
                    if llm_result:
                        x, y = llm_result
                        self.logger.info(f"LLM 找到公众号: ({x}, {y})")
                        click_result = self.click_at(x, y)
                        if click_result.status == AutomationStatus.SUCCESS:
                            return await self._ensure_account_page_open(
                                search_surface_bounds,
                                account_name,
                                x,
                                y,
                            )
                except Exception as e:
                    self.logger.warning(f"LLM 查找失败: {e}")
            else:
                # 没有启用 LLM 的情况
                if not self.ocr_enabled:
                    self.logger.warning("OCR 和 LLM 都未启用，无法查找公众号")
                    return False

            self.logger.error(f"未找到公众号: {account_name}")
            return False

        except Exception as e:
            self.logger.error(f"查找并点击公众号失败: {e}")
            return False

    async def select_account_from_search_results(
        self,
        bounds: Dict[str, int],
        account_name: str,
    ) -> bool:
        """Click the matching official account from WeChat search results."""
        if self._panel_looks_like_official_account_page(bounds, account_name):
            self.logger.info(
                "Target official account page is already open before result selection: %s",
                account_name,
            )
            return True
        return await self._find_and_click_account_in_results(
            bounds,
            account_name,
            bounds,
            allow_preview_row_click=False,
            prefer_small_child_surface=True,
        )

    async def _open_latest_articles_with_bounds(
        self,
        article_bounds: Dict[str, int],
        max_articles: int,
        read_articles: bool = True,
        article_window_title: Optional[str] = None,
    ) -> AutomationResult:
        """Read the latest official-account list and return normalized results."""
        start_time = time.time()
        try:
            max_articles = max(1, int(max_articles or 1))
            await self._scroll_article_list_to_top(article_window_title, bounds=article_bounds)
            visible_articles = await self._await_with_timeout(
                f"Visible article scan for {article_window_title or 'official account keyword'}",
                self.list_latest_articles(article_bounds, max_articles=max_articles),
                WECHAT_ACCOUNT_ARTICLE_STAGE_TIMEOUT_SECONDS,
                default=[],
            ) or []

            visible_titles = [
                article.get("title", "").strip()
                for article in visible_articles
                if isinstance(article, dict) and article.get("title", "").strip()
            ]
            read_results: List[Dict[str, Any]] = []
            if read_articles:
                readout_timeout = self._article_readout_timeout_seconds(max_articles)
                read_results = await self._await_with_timeout(
                    f"Article readout for {article_window_title or 'official account keyword'}",
                    self.read_latest_articles(
                        article_bounds,
                        max_articles=max_articles,
                        article_window_title=article_window_title,
                    ),
                    readout_timeout,
                    default=[],
                ) or []

            articles = self._merge_article_records(visible_articles, read_results, max_articles)
            read_titles = [
                article.get("title", "").strip()
                for article in articles
                if isinstance(article, dict) and article.get("title", "").strip()
            ]
            titles = read_titles or visible_titles
            status = (
                AutomationStatus.SUCCESS
                if titles or articles
                else AutomationStatus.FAILURE
            )
            message = (
                f"Fetched {len(titles)} title(s), read {len(read_titles)} article(s)"
                if read_articles
                else f"Fetched {len(titles)} title(s)"
            )
            execution_time = time.time() - start_time
            return AutomationResult(
                status=status,
                message=message,
                data={
                    "titles": titles[:max_articles],
                    "visible_articles": visible_articles[:max_articles],
                    "visible_titles": visible_titles[:max_articles],
                    "read_titles": read_titles[:max_articles],
                    "articles": articles[:max_articles],
                    "article_panel_bounds": article_bounds,
                    "read_articles": bool(read_articles),
                },
                execution_time=execution_time,
            )
        except Exception as exc:
            execution_time = time.time() - start_time
            self.logger.error("Failed to read latest official-account articles: %s", exc)
            return AutomationResult(
                status=AutomationStatus.ERROR,
                message=f"Exception occurred: {exc}",
                execution_time=execution_time,
                error_details=str(exc),
            )

    async def open_latest_official_account_article(
        self,
        account_name: Optional[str] = None,
        *,
        max_articles: int = 1,
        read_articles: bool = True,
        search_keyword: str = "公众号",
    ) -> AutomationResult:
        """
        Open a specific public-account page and click latest articles,
        or open the "公众号" function flow and click the latest list item when no target account is given.
        """
        requested_account = (account_name or "").strip()
        if requested_account and requested_account != "公众号":
            return await self.fetch_account_article_titles(
                requested_account,
                max_articles=max(1, int(max_articles or 1)),
                read_articles=read_articles,
            )

        keyword = (search_keyword or "公众号").strip() or "公众号"
        start_time = time.time()

        try:
            bounds = await self._await_with_timeout(
                "WeChat window prep for official account keyword flow",
                self._prepare_account_fetch_window(),
                WECHAT_WINDOW_PREP_STAGE_TIMEOUT_SECONDS,
                default=None,
            )
            if not bounds:
                return AutomationResult(
                    status=AutomationStatus.TIMEOUT,
                    message=f"WeChat window prep timed out for official-account keyword '{keyword}'",
                    data={"search_keyword": keyword},
                    execution_time=time.time() - start_time,
                )

            search_result = await self._await_with_timeout(
                f"WeChat account keyword search for {keyword}",
                self.search_wechat_account(bounds, keyword),
                WECHAT_ACCOUNT_SEARCH_STAGE_TIMEOUT_SECONDS,
                default=None,
            )
            if search_result is None:
                return AutomationResult(
                    status=AutomationStatus.TIMEOUT,
                    message=f"WeChat GUI search timed out for keyword '{keyword}'",
                    data={"search_keyword": keyword},
                    execution_time=time.time() - start_time,
                )
            if search_result.status != AutomationStatus.SUCCESS:
                return AutomationResult(
                    status=search_result.status,
                    message=search_result.message,
                    data={"search_keyword": keyword},
                    execution_time=time.time() - start_time,
                    error_details=search_result.error_details,
                )

            search_surface_bounds = self._resolve_search_surface_bounds(
                bounds,
                allow_small_child=True,
            )
            search_region = self._search_results_panel_bounds(search_surface_bounds)
            official_region = self._official_account_result_region(search_surface_bounds)
            detected_texts = self._collect_official_accounts_surface_texts(
                search_surface_bounds,
                search_region,
                official_account_region=official_region,
            )
            opened = await self._open_official_accounts_search_entry(
                search_surface_bounds,
                search_region,
                self._get_account_result_ocr_engine(),
                account_name=keyword,
                official_account_region=official_region,
                detected_texts=detected_texts,
            )
            if not opened:
                # If we cannot enter the official-account surface, attempt to read the
                # current panel directly as a fallback.
                self.logger.warning(
                    "Failed to enter Official Accounts surface for keyword '%s', reading current panel directly",
                    keyword,
                )
                keyword_article_bounds = self._resolve_article_panel_bounds(bounds)
                result = await self._open_latest_articles_with_bounds(
                    keyword_article_bounds,
                    max_articles=max(1, int(max_articles or 1)),
                    read_articles=read_articles,
                    article_window_title=keyword,
                )
                result.data = dict(result.data or {})
                result.data.update(
                    {
                        "mode": "keyword_fallback",
                        "search_keyword": keyword,
                    }
                )
                return result

            await asyncio.sleep(1.0)
            keyword_article_bounds = self._resolve_article_panel_bounds(bounds, account_name=keyword)
            keyword_articles = await self._open_latest_articles_with_bounds(
                keyword_article_bounds,
                max_articles=max(1, int(max_articles or 1)),
                read_articles=read_articles,
                article_window_title=keyword,
            )
            if keyword_articles.data:
                keyword_articles.data = dict(keyword_articles.data)
                keyword_articles.data.update(
                    {
                        "mode": "keyword",
                        "search_keyword": keyword,
                    }
                )
            return keyword_articles

        except Exception as exc:
            execution_time = time.time() - start_time
            self.logger.error("Failed to open latest official-account article by keyword: %s", exc)
            return AutomationResult(
                status=AutomationStatus.ERROR,
                message=f"Exception occurred: {exc}",
                execution_time=execution_time,
                error_details=str(exc),
            )

    async def list_latest_article_titles(
        self,
        bounds: Dict[str, int],
        max_titles: int = 10,
    ) -> List[str]:
        """Return currently visible latest article titles without opening articles."""
        visible_articles = await self.list_latest_articles(bounds, max_articles=max_titles)
        titles = [article["title"] for article in visible_articles if article.get("title")]
        self.logger.info("当前公众号文章标题列表: %s", titles)
        return titles

    async def list_latest_articles(
        self,
        bounds: Dict[str, int],
        max_articles: int = 10,
    ) -> List[Dict[str, Any]]:
        """Return currently visible latest article snapshots with best-effort URLs."""
        candidates: List[Dict[str, Any]] = []

        accessibility_candidates = self._detect_articles_with_accessibility(
            bounds,
            max(1, max_articles),
        )
        if accessibility_candidates:
            candidates.extend(accessibility_candidates)

        if self.ocr_processor:
            try:
                candidates.extend(self._detect_articles_with_ocr(bounds, max(1, max_articles)))
            except Exception as exc:
                self.logger.warning("OCR article-title list detection failed: %s", exc)

        if not candidates and self.llm_enabled and self.llm_element_locator:
            try:
                candidates = await self._detect_articles_with_llm(bounds, max(1, max_articles))
            except Exception as exc:
                self.logger.warning("LLM article-title list detection failed: %s", exc)

        visible_articles: List[Dict[str, Any]] = []
        seen = set()
        for candidate in candidates:
            title = (candidate.get("title") or "").strip()
            key = self._article_title_key(title)
            if key and key not in seen:
                seen.add(key)
                article = {"title": title}
                article_url = self._normalize_article_url(
                    candidate.get("url") or candidate.get("link")
                )
                if article_url:
                    article["url"] = article_url
                    article["link"] = article_url
                visible_articles.append(article)
            if len(visible_articles) >= max_articles:
                break

        return visible_articles

    def _normalize_article_url(self, raw_value: Any) -> str:
        text = " ".join(str(raw_value or "").split()).strip()
        if not text:
            return ""

        match = self._WECHAT_ARTICLE_URL_RE.search(text) or self._GENERIC_URL_RE.search(text)
        if not match:
            return ""

        url = match.group(0).strip().strip("()[]{}<>,;\"'")
        if url.startswith("mp.weixin.qq.com/"):
            url = f"https://{url}"
        # Proxy-captured article links occasionally carry a dangling percent sign
        # (for example `uin=...%3D%`), which breaks later GETs and title recovery.
        url = re.sub(r"%(?![0-9A-Fa-f]{2})", "", url)
        url = url.rstrip("%")
        if "%" in url:
            malformed_match = re.search(r"%(?![0-9A-Fa-f]{2})", url)
            if malformed_match:
                self.logger.warning("Malformed percent encoding remains in normalized WeChat URL: %s", url)
        return url

    def _extract_article_title_from_html(self, raw_html: str) -> str:
        html_text = str(raw_html or "")
        match = WECHAT_OG_TITLE_RE.search(html_text)
        if match:
            return html.unescape(match.group(1)).strip()
        match = WECHAT_HTML_TITLE_RE.search(html_text)
        if match:
            title = html.unescape(match.group(1)).strip()
            return re.sub(r"\s+", " ", title)
        return ""

    def _fetch_article_title_from_url(self, article_url: str, timeout: float = 8.0) -> str:
        normalized_url = self._normalize_article_url(article_url)
        if not normalized_url:
            return ""
        try:
            request = urllib.request.Request(
                normalized_url,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "User-Agent": "Mozilla/5.0",
                },
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw_html = response.read().decode("utf-8", errors="replace")
            return self._extract_article_title_from_html(raw_html)
        except Exception as exc:
            self.logger.debug("Failed to recover WeChat article title from %s: %s", normalized_url, exc)
            return ""

    def _article_url_from_accessibility_element(self, element: Dict[str, Any]) -> str:
        for field in ("value", "description", "name", "text"):
            url = self._normalize_article_url(element.get(field))
            if url:
                return url
        return ""

    def _normalize_article_record(self, article: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(article or {})
        title = (normalized.get("title") or "").strip()
        if title:
            normalized["title"] = title

        article_url = self._normalize_article_url(
            normalized.get("url") or normalized.get("link") or normalized.get("source_url")
        )
        if article_url:
            normalized["url"] = article_url
            normalized.setdefault("link", article_url)
        return normalized

    def _merge_article_records(
        self,
        visible_articles: List[Dict[str, Any]],
        read_articles: List[Dict[str, Any]],
        max_articles: int,
    ) -> List[Dict[str, Any]]:
        visible_by_key: Dict[str, Dict[str, Any]] = {}
        for article in visible_articles or []:
            normalized = self._normalize_article_record(article)
            key = self._article_title_key(normalized.get("title", ""))
            if key and key not in visible_by_key:
                visible_by_key[key] = normalized

        merged: List[Dict[str, Any]] = []
        seen = set()
        for article in read_articles or []:
            if not isinstance(article, dict):
                continue
            normalized = self._normalize_article_record(article)
            key = self._article_title_key(normalized.get("title", ""))
            if not key or key in seen:
                continue

            visible = visible_by_key.get(key)
            if visible and not normalized.get("url"):
                visible_url = visible.get("url") or visible.get("link") or ""
                if visible_url:
                    normalized["url"] = visible_url
                    normalized.setdefault("link", visible_url)

            merged.append(normalized)
            seen.add(key)
            if len(merged) >= max_articles:
                return merged

        if merged:
            return merged

        for article in visible_articles or []:
            normalized = self._normalize_article_record(article)
            key = self._article_title_key(normalized.get("title", ""))
            if not key or key in seen:
                continue
            normalized.setdefault("content", "")
            normalized.setdefault("read_success", False)
            merged.append(normalized)
            seen.add(key)
            if len(merged) >= max_articles:
                break
        return merged

    def _merge_proxy_article_records(
        self,
        live_articles: List[Dict[str, Any]],
        proxy_articles: List[Dict[str, Any]],
        max_articles: int,
    ) -> Tuple[List[Dict[str, Any]], bool]:
        live_by_key: Dict[str, Dict[str, Any]] = {}
        for article in live_articles or []:
            normalized = self._normalize_article_record(article)
            key = self._article_title_key(normalized.get("title", ""))
            if key and key not in live_by_key:
                live_by_key[key] = normalized

        proxy_by_key: Dict[str, Dict[str, Any]] = {}
        for article in proxy_articles or []:
            normalized = self._normalize_article_record(article)
            key = self._article_title_key(normalized.get("title", ""))
            if key and key not in proxy_by_key:
                proxy_by_key[key] = normalized

        merged = self._merge_article_records(proxy_articles, live_articles, max_articles)
        proxy_used = False
        for article in merged:
            normalized = self._normalize_article_record(article)
            key = self._article_title_key(normalized.get("title", ""))
            if not key:
                continue
            proxy = proxy_by_key.get(key)
            if not proxy:
                continue
            live = live_by_key.get(key)
            if live is None:
                proxy_used = True
                break

            merged_url = normalized.get("url") or normalized.get("link") or ""
            live_url = live.get("url") or live.get("link") or ""
            proxy_url = proxy.get("url") or proxy.get("link") or ""
            merged_content = str(normalized.get("content") or normalized.get("article_html") or "").strip()
            live_content = str(live.get("content") or live.get("article_html") or "").strip()
            proxy_content = str(proxy.get("content") or proxy.get("article_html") or "").strip()

            if proxy_url and merged_url == proxy_url and merged_url != live_url:
                proxy_used = True
                break
            if proxy_content and merged_content == proxy_content and merged_content != live_content:
                proxy_used = True
                break

        return merged, proxy_used

    def _backfill_article_links_from_account_url(
        self,
        visible_articles: List[Dict[str, Any]],
        articles: List[Dict[str, Any]],
        titles: List[str],
        proxy_titles: List[str],
        account_url: str,
        max_articles: int,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], bool]:
        normalized_account_url = self._normalize_article_url(account_url)
        if not normalized_account_url:
            return visible_articles, articles, False

        normalized_visible = [
            self._normalize_article_record(article)
            for article in (visible_articles or [])
            if isinstance(article, dict)
        ]
        normalized_articles = [
            self._normalize_article_record(article)
            for article in (articles or [])
            if isinstance(article, dict)
        ]
        backfill_used = False
        proxy_target_title = next(
            (str(title or "").strip() for title in (proxy_titles or []) if str(title or "").strip()),
            "",
        )
        proxy_target_key = self._article_title_key(proxy_target_title)

        def _apply_link(article: Dict[str, Any]) -> Dict[str, Any]:
            patched = self._normalize_article_record(article)
            if not patched.get("url"):
                patched["url"] = normalized_account_url
                patched.setdefault("link", normalized_account_url)
                patched.setdefault("url_source", "proxy_account_url")
            return patched

        target_key = ""
        if normalized_articles and proxy_target_key:
            for idx, article in enumerate(normalized_articles):
                if article.get("url"):
                    continue
                if not self._is_probable_article_title(article.get("title", "")):
                    continue
                if self._article_title_key(article.get("title", "")) != proxy_target_key:
                    continue
                normalized_articles[idx] = _apply_link(article)
                target_key = proxy_target_key
                backfill_used = True
                break
        else:
            read_backfilled = False
            if proxy_target_key:
                for idx, article in enumerate(normalized_articles):
                    if article.get("url"):
                        continue
                    if not article.get("read_success"):
                        continue
                    if not self._is_probable_article_title(article.get("title", "")):
                        continue
                    normalized_articles[idx] = _apply_link(article)
                    target_key = self._article_title_key(article.get("title", ""))
                    backfill_used = True
                    read_backfilled = True
                    break

            if not read_backfilled:
                first_title = proxy_target_title or next(
                    (str(title or "").strip() for title in (titles or []) if str(title or "").strip()),
                    "",
                )
                if first_title and self._is_probable_article_title(first_title):
                    normalized_articles.append(
                        {
                            "title": first_title,
                            "content": f"文章标题: {first_title}",
                            "read_success": False,
                            "detection_method": "proxy_account_url_fallback",
                            "url": normalized_account_url,
                            "link": normalized_account_url,
                            "url_source": "proxy_account_url",
                        }
                    )
                    target_key = self._article_title_key(first_title)
                    backfill_used = True

        if not target_key and proxy_target_key:
            target_key = proxy_target_key
        if not target_key and titles:
            target_key = self._article_title_key(titles[0])

        if target_key:
            for idx, article in enumerate(normalized_visible):
                if article.get("url"):
                    continue
                if not self._is_probable_article_title(article.get("title", "")):
                    continue
                if self._article_title_key(article.get("title", "")) != target_key:
                    continue
                normalized_visible[idx] = _apply_link(article)
                backfill_used = True
                break

        if not backfill_used and normalized_articles and not proxy_target_key:
            for idx, article in enumerate(normalized_articles):
                if article.get("url"):
                    continue
                if not article.get("read_success"):
                    continue
                if not self._is_probable_article_title(article.get("title", "")):
                    continue
                normalized_articles[idx] = _apply_link(article)
                backfill_used = True

                article_key = self._article_title_key(article.get("title", ""))
                if article_key:
                    for visible_idx, visible_article in enumerate(normalized_visible):
                        if visible_article.get("url"):
                            continue
                        if self._article_title_key(visible_article.get("title", "")) != article_key:
                            continue
                        normalized_visible[visible_idx] = _apply_link(visible_article)
                        break
                break

        return normalized_visible[:max_articles], normalized_articles[:max_articles], backfill_used

    def _normalize_account_name_key(self, account_name: Any) -> str:
        normalized = str(account_name or "").strip().lower()
        normalized = re.sub(r"^[\s•·●・◦▪▫►▶\-–—:：]+", "", normalized)
        normalized = re.sub(r"[\s•·●・◦▪▫]+$", "", normalized)
        return "".join(normalized.split()).strip()

    def _proxy_account_match_score(self, candidate_name: Any, target_name: str) -> float:
        candidate = str(candidate_name or "").strip()
        target = str(target_name or "").strip()
        if not candidate or not target:
            return 0.0

        normalized_candidate = self._normalize_account_name_key(candidate)
        normalized_target = self._normalize_account_name_key(target)
        if not normalized_candidate or not normalized_target:
            return 0.0
        if normalized_candidate == normalized_target:
            return 400.0
        if normalized_target in normalized_candidate or normalized_candidate in normalized_target:
            return 320.0 - abs(len(normalized_candidate) - len(normalized_target))

        similarity = max(
            self._text_similarity(candidate, target),
            self._text_similarity(normalized_candidate, normalized_target),
        )
        if similarity < 0.58:
            return 0.0
        return similarity * 100.0

    def _proxy_sort_timestamp(self, raw_value: Any) -> float:
        if raw_value is None:
            return 0.0

        text = str(raw_value).strip()
        if not text:
            return 0.0
        try:
            return float(text)
        except Exception:
            pass

        normalized = text.rstrip(".").replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized).timestamp()
        except Exception:
            return 0.0

    def _proxy_history_api_base(self) -> str:
        return (os.getenv("WECHAT_PROXY_HISTORY_API_BASE") or f"http://127.0.0.1:{os.getenv('WEB_PORT', '10000')}").rstrip("/")

    def _fetch_proxy_history_json(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        query = urllib.parse.urlencode({key: value for key, value in (params or {}).items() if value is not None})
        url = f"{self._proxy_history_api_base()}{path}"
        if query:
            url = f"{url}?{query}"
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def _get_proxy_history_for_account(
        self,
        account_name: str,
        max_articles: int = 3,
    ) -> Optional[Dict[str, Any]]:
        """Recover the latest proxy-captured WeChat account/article links for an account."""
        try:
            scan_limit = max(50, min(int(os.getenv("WECHAT_PROXY_ACCOUNT_SCAN_LIMIT", "1500")), 5000))
            accounts_payload = self._fetch_proxy_history_json(
                "/api/platforms/weixin/accounts",
                {"page": 1, "per_page": scan_limit},
            )
            accounts = accounts_payload.get("accounts") or []

            scored_accounts: List[Tuple[float, float, Dict[str, Any]]] = []
            for account in accounts:
                if not isinstance(account, dict):
                    continue
                score = self._proxy_account_match_score(account.get("account_name"), account_name)
                if score <= 0:
                    continue
                if self._normalize_article_url(account.get("account_url")):
                    score += 6.0
                scored_accounts.append(
                    (
                        score,
                        self._proxy_sort_timestamp(account.get("update")),
                        account,
                    )
                )

            if not scored_accounts:
                return None

            scored_accounts.sort(key=lambda item: (-item[0], -item[1], -int(item[2].get("id") or 0)))
            matched_account = scored_accounts[0][2]
            matched_account_name = str(matched_account.get("account_name") or account_name).strip() or account_name
            account_url = self._normalize_article_url(matched_account.get("account_url"))

            raw_articles_payload = self._fetch_proxy_history_json(
                "/api/articles/",
                {
                    "platform": "weixin",
                    "channel": matched_account_name,
                    "page": 1,
                    "per_page": max(max_articles * 4, 12),
                },
            )
            raw_articles = raw_articles_payload.get("data") or []

            proxy_articles: List[Dict[str, Any]] = []
            seen = set()
            for raw_article in raw_articles:
                if not isinstance(raw_article, dict):
                    continue
                title = str(
                    raw_article.get("article_title")
                    or raw_article.get("title")
                    or raw_article.get("coreContent")
                    or raw_article.get("core_content")
                    or ""
                ).strip()
                raw_url = (
                    raw_article.get("article_content_url")
                    or raw_article.get("article_source_url")
                    or raw_article.get("url")
                    or raw_article.get("link")
                )
                url = self._normalize_article_url(
                    raw_url
                )
                if not title and url:
                    title = self._fetch_article_title_from_url(url)
                self.logger.info(
                    "WeChat proxy history candidate: raw_url=%s normalized_url=%s recovered_title=%s",
                    raw_url,
                    url,
                    title,
                )
                key = self._article_title_key(title) or url
                if not key or key in seen:
                    continue
                seen.add(key)
                proxy_articles.append(
                    {
                        "title": title,
                        "url": url,
                        "link": url,
                        "source": "proxy_history",
                    }
                )
                if len(proxy_articles) >= max_articles:
                    break

            proxy_titles = [
                article.get("title", "").strip()
                for article in proxy_articles
                if isinstance(article, dict) and article.get("title", "").strip()
            ][:max_articles]
            if not proxy_articles and not account_url:
                return None

            return {
                "account_name": account_name,
                "matched_account_name": matched_account_name,
                "account_id": matched_account.get("id"),
                "account_url": account_url,
                "proxy_fallback_used": True,
                "visible_articles": proxy_articles,
                "visible_titles": list(proxy_titles),
                "read_titles": list(proxy_titles),
                "titles": list(proxy_titles),
                "articles": proxy_articles,
            }
        except Exception as exc:
            self.logger.warning("Failed to recover proxied WeChat history for %s: %s", account_name, exc)
            return None

    def _detect_articles_with_accessibility(
        self,
        bounds: Dict[str, int],
        candidate_limit: int,
    ) -> List[Dict[str, Any]]:
        accessibility_service = getattr(self, "accessibility_service", None)
        if not accessibility_service:
            return []

        try:
            elements = accessibility_service.visible_elements(
                region=bounds,
                allowed_roles=[
                    "axstatictext",
                    "axlink",
                    "axbutton",
                    "axrow",
                    "axgroup",
                    "text",
                    "link",
                    "button",
                    "row",
                ],
                limit=max(80, candidate_limit * 12),
            )
        except Exception as exc:
            self.logger.warning("Accessibility article-title list detection failed: %s", exc)
            return []

        text_records: List[Dict[str, Any]] = []
        for element in elements:
            title = (
                element.get("text")
                or element.get("name")
                or element.get("description")
                or element.get("value")
                or ""
            ).strip()
            center_x = int(element.get("x", 0)) + max(int(element.get("width", 1) or 1), 1) // 2
            center_y = int(element.get("y", 0)) + max(int(element.get("height", 1) or 1), 1) // 2
            if self._point_in_bounds(center_x, center_y, bounds):
                text_records.append({"text": title, "center_y": center_y})
        article_list_floor = self._infer_article_list_content_floor(text_records)

        candidates: List[Dict[str, Any]] = []
        for element in elements:
            title = (
                element.get("text")
                or element.get("name")
                or element.get("description")
                or element.get("value")
                or ""
            ).strip()
            if not self._is_probable_article_title(title):
                continue

            center_x = int(element.get("x", 0)) + max(int(element.get("width", 1) or 1), 1) // 2
            center_y = int(element.get("y", 0)) + max(int(element.get("height", 1) or 1), 1) // 2
            if not self._point_in_bounds(center_x, center_y, bounds):
                continue
            if article_list_floor is not None and center_y <= article_list_floor:
                continue

            relative_y = (center_y - bounds["Y"]) / max(1, bounds["Height"])
            if not 0.03 <= relative_y <= 0.97:
                continue

            role = str(element.get("role") or "").lower()
            role_bonus = 12 if any(token in role for token in ("link", "button", "row")) else 0
            confidence = min(99.0, float(element.get("confidence", 0.88)) * 100.0)
            signal_score = self._article_trading_signal_score(title)
            total_score = confidence + role_bonus + (8 if 0.08 <= relative_y <= 0.9 else 0) + signal_score * 5
            article_url = self._article_url_from_accessibility_element(element)
            candidates.append(
                {
                    "title": title,
                    "x": center_x,
                    "y": center_y,
                    "confidence": confidence,
                    "signal_score": signal_score,
                    "total_score": total_score,
                    "source": "accessibility",
                    "url": article_url,
                }
            )

        candidates.sort(key=lambda item: (-item["total_score"], item["y"], item["x"]))
        candidates = self._dedupe_article_candidates(candidates)[:candidate_limit]
        candidates.sort(key=lambda item: (item["y"], item["x"]))
        if candidates:
            self.logger.info("Accessibility 当前视图找到 %s 个文章候选", len(candidates))
        return candidates

    async def _prepare_account_fetch_window(self) -> Optional[Dict[str, int]]:
        """Normalize WeChat window state before search so search timeout only measures search work."""
        fast_bounds = await asyncio.to_thread(self._get_interaction_bounds)
        if fast_bounds:
            front_bounds = await asyncio.to_thread(self._get_frontmost_wechat_window_bounds)
            front_window_info = None
            front_window_name = ""
            if front_bounds:
                front_window_info = await asyncio.to_thread(
                    self._find_wechat_window_info_by_bounds,
                    front_bounds,
                )
                front_window_name = (front_window_info or {}).get("name") or ""

            if (
                front_bounds
                and not self._bounds_roughly_match(front_bounds, fast_bounds)
                and front_window_name not in {"微信", "WeChat", "Weixin"}
            ):
                self.logger.info(
                    "Closing front auxiliary WeChat window before account search: title=%r bounds=%s main=%s",
                    front_window_name,
                    front_bounds,
                    fast_bounds,
                )
                await asyncio.to_thread(self._close_front_auxiliary_wechat_windows)
                await asyncio.sleep(0.35)
                refreshed_bounds = await asyncio.to_thread(self._get_interaction_bounds)
                if refreshed_bounds:
                    fast_bounds = refreshed_bounds

            front_ready = await asyncio.to_thread(
                self._ensure_wechat_frontmost,
                activate=True,
                attempts=1,
                settle_seconds=0.25,
            )
            if not front_ready:
                front_ready = await asyncio.to_thread(
                    self._prime_wechat_for_immediate_action,
                    settle_seconds=0.12,
                )
            if front_ready:
                self._wechat_focus_grace_deadline = time.time() + 4.0
                return fast_bounds

        await asyncio.to_thread(self._close_front_auxiliary_wechat_windows)
        await asyncio.sleep(0.35)

        front_ready = await asyncio.to_thread(
            self._ensure_wechat_frontmost,
            activate=True,
            attempts=2,
            settle_seconds=0.45,
        )
        if not front_ready:
            bring_result = await asyncio.to_thread(self.bring_wechat_to_front)
            front_ready = bring_result.status == AutomationStatus.SUCCESS

        bounds = await asyncio.to_thread(self._get_interaction_bounds)
        if bounds and front_ready:
            self._wechat_focus_grace_deadline = time.time() + 4.0
        return bounds

    async def fetch_account_article_titles(
        self,
        account_name: str,
        max_articles: int = 3,
        read_articles: bool = True,
    ) -> AutomationResult:
        """Search an official account, open it, list latest titles, then read articles one by one."""
        start_time = time.time()
        try:
            if not account_name or not account_name.strip():
                return AutomationResult(
                    status=AutomationStatus.FAILURE,
                    message="account_name is required",
                    execution_time=time.time() - start_time,
                )

            account_name = account_name.strip()
            accessibility_status = self.get_accessibility_status()
            proxy_payload = self._get_proxy_history_for_account(account_name, max_articles=max_articles)

            def _proxy_recovery_result(message: str) -> AutomationResult:
                execution_time = time.time() - start_time
                self.performance_monitor.record_operation(
                    "fetch_account_article_titles",
                    execution_time,
                    True,
                )
                payload = dict(proxy_payload or {})
                payload.setdefault("account_name", account_name)
                payload.setdefault("titles", [])
                payload.setdefault("visible_articles", payload.get("articles", []))
                payload.setdefault("visible_titles", payload.get("titles", []))
                payload.setdefault("read_titles", payload.get("titles", []))
                payload.setdefault("articles", [])
                payload.setdefault("account_url", "")
                payload.setdefault("matched_account_name", "")
                payload.setdefault("proxy_fallback_used", bool(proxy_payload))
                payload.setdefault("proxy_account_url_backfilled", False)
                payload.setdefault("accessibility_status", accessibility_status)
                payload.setdefault(
                    "accessibility_blocked",
                    bool(accessibility_status.get("permission_required")),
                )
                payload.setdefault("read_articles", bool(read_articles))
                return AutomationResult(
                    status=AutomationStatus.SUCCESS,
                    message=message,
                    data=payload,
                    execution_time=execution_time,
                )

            if (
                not read_articles
                and proxy_payload
                and (
                    proxy_payload.get("account_url")
                    or proxy_payload.get("titles")
                    or proxy_payload.get("articles")
                )
            ):
                proxy_titles = proxy_payload.get("titles", [])
                proxy_articles = proxy_payload.get("articles", [])
                message = (
                    f"Recovered {len(proxy_titles)} proxied title(s) for {account_name} without GUI article readout"
                    if proxy_titles or proxy_articles
                    else f"Recovered proxied WeChat account link for {account_name} without GUI article readout"
                )
                return _proxy_recovery_result(message)

            # Keep the GUI search/selection stages on the base timeout
            # contract so explicit overrides and timeout recovery semantics
            # remain predictable. Read-mode extensions belong to later
            # article-readout steps, not to the upstream GUI routing stages.
            window_prep_timeout = WECHAT_WINDOW_PREP_STAGE_TIMEOUT_SECONDS
            search_timeout = WECHAT_ACCOUNT_SEARCH_STAGE_TIMEOUT_SECONDS
            selection_timeout = WECHAT_ACCOUNT_SELECTION_STAGE_TIMEOUT_SECONDS
            bounds = await self._await_with_timeout(
                f"WeChat window prep for {account_name}",
                self._prepare_account_fetch_window(),
                window_prep_timeout,
                default=None,
            )
            if not bounds:
                if proxy_payload:
                    proxy_titles = proxy_payload.get("titles", [])
                    proxy_articles = proxy_payload.get("articles", [])
                    message = (
                        f"Recovered {len(proxy_titles)} proxied title(s) for {account_name} after WeChat window prep failed"
                        if proxy_titles or proxy_articles
                        else f"Recovered proxied WeChat account link for {account_name} after WeChat window prep failed"
                    )
                    return _proxy_recovery_result(message)
                return AutomationResult(
                    status=AutomationStatus.TIMEOUT,
                    message=f"WeChat window prep timed out for {account_name}",
                    data={"account_name": account_name},
                    execution_time=time.time() - start_time,
                )

            if (
                accessibility_status.get("permission_required")
                and proxy_payload
                and (
                    proxy_payload.get("account_url")
                    or proxy_payload.get("titles")
                    or proxy_payload.get("articles")
                )
            ):
                proxy_titles = (proxy_payload or {}).get("titles", [])
                proxy_articles = (proxy_payload or {}).get("articles", [])
                message = (
                    f"Recovered {len(proxy_titles)} proxied title(s) for {account_name} because macOS accessibility permission is unavailable"
                    if proxy_titles or proxy_articles
                    else f"Recovered proxied WeChat account link for {account_name} because macOS accessibility permission is unavailable"
                )
                return _proxy_recovery_result(message)

            search_result = await self._await_with_timeout(
                f"WeChat account search for {account_name}",
                self.search_wechat_account(bounds, account_name),
                search_timeout,
                default=None,
            )
            if search_result is None:
                if proxy_payload:
                    proxy_titles = proxy_payload.get("titles", [])
                    proxy_articles = proxy_payload.get("articles", [])
                    message = (
                        f"Recovered {len(proxy_titles)} proxied title(s) for {account_name} after GUI search timed out"
                        if proxy_titles or proxy_articles
                        else f"Recovered proxied WeChat account link for {account_name} after GUI search timed out"
                    )
                    return _proxy_recovery_result(message)
                return AutomationResult(
                    status=AutomationStatus.TIMEOUT,
                    message=f"WeChat GUI search timed out for {account_name}",
                    data={"account_name": account_name},
                    execution_time=time.time() - start_time,
                )
            if search_result.status != AutomationStatus.SUCCESS:
                return AutomationResult(
                    status=search_result.status,
                    message=f"Search failed before selecting account: {search_result.message}",
                    data={"account_name": account_name},
                    execution_time=time.time() - start_time,
                    error_details=search_result.error_details,
                )

            async def _select_account_with_exact_path(timeout_seconds: float) -> bool:
                search_surface_bounds = self._resolve_search_surface_bounds(
                    bounds,
                    allow_small_child=True,
                    account_name=account_name,
                )
                search_region = self._search_results_panel_bounds(search_surface_bounds)
                official_account_region = self._official_account_result_region(search_surface_bounds)
                detected_texts = self._collect_official_accounts_surface_texts(
                    search_surface_bounds,
                    search_region,
                    official_account_region=official_account_region,
                )
                account_result_ocr = self._get_account_result_ocr_engine()
                has_official_entry_hint = bool(
                    detected_texts
                    and (
                        any(
                            self._looks_like_official_accounts_entry(text)
                            for text in detected_texts
                        )
                        or self._has_account_name_evidence(detected_texts, account_name)
                    )
                )
                if has_official_entry_hint:
                    official_entry_timeout = max(
                        0.001,
                        min(0.5, timeout_seconds * 0.6),
                    )
                    official_selected = await self._await_with_timeout(
                        f"WeChat official entry selection for {account_name}",
                        self._open_official_accounts_search_entry(
                            search_surface_bounds,
                            search_region,
                            account_result_ocr,
                            account_name=account_name,
                            official_account_region=official_account_region,
                            detected_texts=detected_texts,
                        ),
                        official_entry_timeout,
                        default=False,
                    )
                    if official_selected:
                        return True

                    if timeout_seconds <= official_entry_timeout:
                        return False

                return await self.select_account_from_search_results(
                    search_surface_bounds,
                    account_name,
                )

            selected = await self._await_with_timeout(
                f"WeChat account selection for {account_name}",
                _select_account_with_exact_path(selection_timeout),
                selection_timeout,
                default=None,
            )
            if read_articles and selected in (None, False) and not proxy_payload:
                retry_reason = "timed out" if selected is None else "failed"
                self.logger.info(
                    "WeChat account selection %s for %s; rerunning GUI search + selection once",
                    retry_reason,
                    account_name,
                )
                search_result = await self._await_with_timeout(
                    f"WeChat account search retry for {account_name}",
                    self.search_wechat_account(bounds, account_name),
                    search_timeout,
                    default=None,
                )
                if search_result is not None and search_result.status == AutomationStatus.SUCCESS:
                    retry_selection_timeout = selection_timeout
                    if read_articles:
                        retry_selection_timeout = max(
                            retry_selection_timeout,
                            WECHAT_ACCOUNT_SELECTION_STAGE_TIMEOUT_SECONDS_READ,
                        )
                    selected = await self._await_with_timeout(
                        f"WeChat account selection retry for {account_name}",
                        _select_account_with_exact_path(retry_selection_timeout),
                        retry_selection_timeout,
                        default=None,
                    )
            if selected is None:
                if proxy_payload:
                    proxy_titles = proxy_payload.get("titles", [])
                    proxy_articles = proxy_payload.get("articles", [])
                    message = (
                        f"Recovered {len(proxy_titles)} proxied title(s) for {account_name} after GUI selection timed out"
                        if proxy_titles or proxy_articles
                        else f"Recovered proxied WeChat account link for {account_name} after GUI selection timed out"
                    )
                    return _proxy_recovery_result(message)
                return AutomationResult(
                    status=AutomationStatus.TIMEOUT,
                    message=f"WeChat GUI selection timed out for {account_name}",
                    data={"account_name": account_name},
                    execution_time=time.time() - start_time,
                )
            if not selected:
                if proxy_payload:
                    proxy_titles = proxy_payload.get("titles", [])
                    proxy_articles = proxy_payload.get("articles", [])
                    message = (
                        f"Recovered {len(proxy_titles)} proxied title(s) for {account_name} after GUI selection failed"
                        if proxy_titles or proxy_articles
                        else f"Recovered proxied WeChat account link for {account_name} after GUI selection failed"
                    )
                    return _proxy_recovery_result(message)
                return AutomationResult(
                    status=AutomationStatus.FAILURE,
                    message=f"Search result for official account '{account_name}' was not clicked",
                    data={"account_name": account_name},
                    execution_time=time.time() - start_time,
                )

            await asyncio.sleep(2.0)
            article_bounds = self._resolve_article_panel_bounds(bounds, account_name)
            await self._scroll_article_list_to_top(account_name, article_bounds)
            visible_articles = await self._await_with_timeout(
                f"Visible article scan for {account_name}",
                self.list_latest_articles(article_bounds, max_articles=max_articles),
                WECHAT_ACCOUNT_ARTICLE_STAGE_TIMEOUT_SECONDS,
                default=[],
            ) or []
            visible_titles = [
                article.get("title", "").strip()
                for article in visible_articles
                if isinstance(article, dict) and article.get("title", "").strip()
            ]
            read_results: List[Dict[str, Any]] = []
            if read_articles:
                self._article_read_url_hints = self._build_article_url_hints(proxy_payload)
                self._set_partial_article_read_results([])
                self._set_last_completed_article_read(None)
                readout_timeout = self._article_readout_timeout_seconds(max_articles)
                try:
                    read_results = await self._await_with_timeout(
                        f"Article readout for {account_name}",
                        self.read_latest_articles(
                            article_bounds,
                            max_articles=max_articles,
                            article_window_title=account_name,
                        ),
                        readout_timeout,
                        default=[],
                    ) or []
                finally:
                    partial_read_results = self._consume_partial_article_read_results()
                    pending_article = self._consume_last_completed_article_read()
                    self._article_read_url_hints = {}
                if pending_article:
                    partial_read_results = self._merge_article_records(
                        [],
                        [*partial_read_results, pending_article],
                        max_articles,
                    )
                if not read_results and partial_read_results:
                    self.logger.info(
                        "Recovered %s partially read article(s) for %s after article readout timeout",
                        len(partial_read_results),
                        account_name,
                    )
                    read_results = partial_read_results
            articles = self._merge_article_records(visible_articles, read_results, max_articles)
            read_titles = [
                article.get("title", "").strip()
                for article in articles
                if isinstance(article, dict) and article.get("title", "").strip()
            ][:max_articles]
            titles = self._merge_article_titles(read_titles, visible_titles, max_articles)
            proxy_fallback_used = False
            proxy_account_url_backfilled = False
            if proxy_payload:
                proxy_articles = proxy_payload.get("articles", [])
                if proxy_articles:
                    visible_articles, visible_proxy_used = self._merge_proxy_article_records(
                        visible_articles,
                        proxy_articles,
                        max_articles,
                    )
                    articles, article_proxy_used = self._merge_proxy_article_records(
                        articles,
                        proxy_articles,
                        max_articles,
                    )
                    proxy_fallback_used = visible_proxy_used or article_proxy_used
                    visible_titles = self._merge_article_titles(
                        [
                            article.get("title", "").strip()
                            for article in visible_articles
                            if isinstance(article, dict) and article.get("title", "").strip()
                        ],
                        proxy_payload.get("visible_titles", []),
                        max_articles,
                    )
                    read_titles = self._merge_article_titles(
                        [
                            article.get("title", "").strip()
                            for article in articles
                            if isinstance(article, dict) and article.get("title", "").strip()
                        ],
                        proxy_payload.get("read_titles", []),
                        max_articles,
                    )
                    titles = self._merge_article_titles(
                        self._merge_article_titles(read_titles, visible_titles, max_articles),
                        proxy_payload.get("titles", []),
                        max_articles,
                    )
                    if not (read_titles or visible_titles) and titles:
                        proxy_fallback_used = True
                elif proxy_payload.get("account_url"):
                    titles = self._merge_article_titles(titles, proxy_payload.get("titles", []), max_articles)
                    if not (read_titles or visible_titles or articles or visible_articles) and titles:
                        proxy_fallback_used = True
                visible_articles, articles, proxy_account_url_backfilled = self._backfill_article_links_from_account_url(
                    visible_articles,
                    articles,
                    titles,
                    proxy_payload.get("titles", []),
                    proxy_payload.get("account_url", ""),
                    max_articles,
                )
                if not (titles or articles) and proxy_payload.get("account_url"):
                    proxy_fallback_used = True

            status = AutomationStatus.SUCCESS if titles or articles or (proxy_payload and proxy_payload.get("account_url")) else AutomationStatus.FAILURE
            message = (
                f"Fetched {len(titles)} title(s), read {len(articles)} article(s) for {account_name}"
                if (titles or articles) and read_articles
                else f"Fetched {len(titles)} title(s) for {account_name}"
                if titles or articles
                else f"Recovered proxied WeChat account link for {account_name}"
                if proxy_payload and proxy_payload.get("account_url")
                else f"No article titles found and no articles read for {account_name}"
            )

            execution_time = time.time() - start_time
            self.performance_monitor.record_operation(
                "fetch_account_article_titles",
                execution_time,
                status == AutomationStatus.SUCCESS,
            )
            return AutomationResult(
                status=status,
                message=message,
                data={
                    "account_name": account_name,
                    "titles": titles,
                    "visible_articles": visible_articles,
                    "visible_titles": visible_titles,
                    "read_titles": read_titles,
                    "articles": articles[:max_articles],
                    "article_panel_bounds": article_bounds,
                    "account_url": (proxy_payload or {}).get("account_url", ""),
                    "matched_account_name": (proxy_payload or {}).get("matched_account_name", ""),
                    "proxy_fallback_used": proxy_fallback_used,
                    "proxy_account_url_backfilled": proxy_account_url_backfilled,
                    "accessibility_status": accessibility_status,
                    "accessibility_blocked": bool(accessibility_status.get("permission_required")),
                    "read_articles": bool(read_articles),
                },
                execution_time=execution_time,
            )
        except Exception as e:
            execution_time = time.time() - start_time
            self.performance_monitor.record_operation("fetch_account_article_titles", execution_time, False)
            self.logger.error("Failed to fetch account article titles: %s", e, exc_info=True)
            return AutomationResult(
                status=AutomationStatus.ERROR,
                message=f"Exception occurred: {e}",
                execution_time=execution_time,
                error_details=str(e),
            )

    async def fetch_accounts_latest_articles(
        self,
        account_names: List[str],
        max_articles: int = 3,
        read_articles: bool = True,
    ) -> AutomationResult:
        """Search multiple official accounts and read each account's latest articles."""
        start_time = time.time()
        cleaned_accounts = []
        for account_name in account_names or []:
            if isinstance(account_name, str) and account_name.strip():
                cleaned_accounts.append(account_name.strip())

        if not cleaned_accounts:
            return AutomationResult(
                status=AutomationStatus.FAILURE,
                message="account_names is required",
                execution_time=time.time() - start_time,
            )

        results = []
        for account_name in cleaned_accounts:
            result = await self.fetch_account_article_titles(
                account_name,
                max_articles=max_articles,
                read_articles=read_articles,
            )
            result_data = result.data or {}
            results.append({
                "account_name": account_name,
                "status": result.status.value,
                "success": result.status == AutomationStatus.SUCCESS,
                "message": result.message,
                "titles": result_data.get("titles", []),
                "visible_articles": result_data.get("visible_articles", []),
                "visible_titles": result_data.get("visible_titles", []),
                "read_titles": result_data.get("read_titles", []),
                "articles": result_data.get("articles", []),
                "error_details": result.error_details,
            })

        success_count = sum(1 for result in results if result.get("success"))
        if success_count == len(cleaned_accounts):
            status = AutomationStatus.SUCCESS
        elif success_count > 0:
            status = AutomationStatus.PARTIAL_SUCCESS
        else:
            status = AutomationStatus.FAILURE

        execution_time = time.time() - start_time
        self.performance_monitor.record_operation(
            "fetch_accounts_latest_articles",
            execution_time,
            status in (AutomationStatus.SUCCESS, AutomationStatus.PARTIAL_SUCCESS),
        )
        return AutomationResult(
            status=status,
            message=(
                f"Processed {len(cleaned_accounts)} account(s), "
                f"successful: {success_count}/{len(cleaned_accounts)}"
            ),
            data={
                "results": results,
                "success_count": success_count,
                "account_count": len(cleaned_accounts),
            },
            execution_time=execution_time,
        )

    async def read_latest_articles(
        self,
        bounds: Dict[str, int],
        max_articles: int = 3,
        article_window_title: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        读取公众号聚合页面中的最新文章
        使用 LLM 定位文章列表中的各个文章条目，逐个点击打开，等待2秒后关闭

        Args:
            bounds: 窗口边界

        Returns:
            List[Dict[str, Any]]: 文章内容列表，每篇文章包含标题、内容等信息
        """
        try:
            self.logger.info("开始读取最新文章")

            # Prefer real local OCR on the actual official-account window. The
            # remote LLM path may be unavailable or return empty text.
            if self.ocr_processor:
                articles = await self._read_articles_with_ocr(
                    bounds,
                    max_articles=max_articles,
                    article_window_title=article_window_title,
                )
                if articles:  # If we got real articles, return them
                    return articles

            # Fallback: use LLM vision if configured.
            if self.llm_enabled and self.llm_element_locator:
                articles = await self._read_articles_with_llm(
                    bounds,
                    max_articles=max_articles,
                    article_window_title=article_window_title,
                )
                if articles:  # If we got real articles, return them
                    return articles
            self.logger.error("Failed to read real articles: both LLM and OCR article extraction returned no data")
            return []

        except Exception as e:
            self.logger.error(f"读取文章失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return []

    def _article_title_key(self, title: str) -> str:
        """Normalize a title for de-duplication across scrolls and OCR variants."""
        return "".join((title or "").split()).strip("·.-_")[:80]

    def _normalize_detected_article_text(self, title: str) -> str:
        normalized = re.sub(r"^[\s•●·▪▫►▶□■☐☑✓✔❖◆◇◦○○口]+", "", str(title or "")).strip()
        normalized = re.sub(r"\s{2,}", " ", normalized)
        return normalized

    def _looks_like_fragmentary_article_title(self, raw_title: str, normalized_title: str = "") -> bool:
        raw = str(raw_title or "").strip()
        normalized = normalized_title or self._normalize_detected_article_text(raw)
        compact = "".join(normalized.split())
        if not compact:
            return True
        if raw and raw[0] in "，,。.!！？?、；;:：）)]】>》」』":
            return True
        if compact and compact[0] in "，,。.!！？?、；;:：）)]】>》」』":
            return True
        if re.match(r"^[\u4e00-\u9fff]的(净利润|归母净利润|营业收入|营收|同比增长)", compact):
            return True
        return False

    def _article_trading_signal_score(self, title: str, content: str = "") -> float:
        title_text = self._normalize_detected_article_text(title).lower()
        content_text = self._normalize_detected_article_text(content).lower()
        combined = f"{title_text}\n{content_text}".strip()
        if not combined:
            return 0.0

        score = 0.0
        strong_theme_hits = 0
        for keyword, weight in WECHAT_ARTICLE_TRADING_SIGNAL_KEYWORDS:
            keyword_lower = keyword.lower()
            title_weight = weight if keyword_lower in WECHAT_ARTICLE_WEAK_SIGNAL_KEYWORDS else weight * 3
            if keyword_lower in title_text:
                score += title_weight
                if keyword_lower not in WECHAT_ARTICLE_WEAK_SIGNAL_KEYWORDS:
                    strong_theme_hits += 1
            elif keyword_lower in combined:
                score += weight
                if keyword_lower not in WECHAT_ARTICLE_WEAK_SIGNAL_KEYWORDS:
                    strong_theme_hits += 1

        if strong_theme_hits == 0:
            for keyword, penalty in WECHAT_ARTICLE_LOW_CONVICTION_FINANCIAL_KEYWORDS:
                keyword_lower = keyword.lower()
                if keyword_lower in title_text:
                    score -= penalty * 2
                elif keyword_lower in combined:
                    score -= penalty

        return score

    def _article_readout_timeout_seconds(self, max_articles: int) -> float:
        scaled_timeout = 12.0 * max(1, int(max_articles or 1)) + 4.0
        return max(WECHAT_ACCOUNT_ARTICLE_STAGE_TIMEOUT_SECONDS, scaled_timeout)

    def _looks_like_non_article_header_text(self, title: str) -> bool:
        normalized = "".join(self._normalize_detected_article_text(title).split())
        if not normalized:
            return False
        if normalized in WECHAT_ARTICLE_HEADER_BLOCKED_LABELS:
            return True
        if any(phrase in normalized for phrase in WECHAT_ARTICLE_HEADER_BLOCKED_PHRASES):
            return True
        if re.fullmatch(r"[\u4e00-\u9fffA-Za-z0-9]{2,16}VIP", normalized, re.IGNORECASE):
            return True
        descriptor_hits = sum(
            1 for marker in WECHAT_ARTICLE_PROFILE_DESCRIPTOR_MARKERS if marker in normalized
        )
        return descriptor_hits >= 2

    def _infer_article_list_content_floor(self, text_records: List[Dict[str, Any]]) -> Optional[int]:
        anchor_positions = []
        for record in text_records:
            normalized = "".join((record.get("text") or "").split())
            center_y = int(record.get("center_y") or 0)
            if center_y <= 0 or not normalized:
                continue
            if any(marker in normalized for marker in WECHAT_ARTICLE_LIST_SECTION_MARKERS):
                anchor_positions.append(center_y)
        if not anchor_positions:
            return None
        return min(anchor_positions)

    def _is_probable_article_title(self, title: str) -> bool:
        raw_title = str(title or "")
        title = self._normalize_detected_article_text(raw_title)
        if len(title) < 8 or len(title) > 220:
            return False
        if self._looks_like_fragmentary_article_title(raw_title, title):
            return False
        ui_keywords = {
            "微信", "首页", "消息", "发现", "我", "搜索", "公众号", "更多", "加载",
            "刷新", "顶部", "底部", "分享", "喜欢", "在看", "评论", "关注", "收藏",
            "常看的号", "账号", "推荐", "订阅号", "服务号", "视频号", "小程序",
            "媒体", "原创内容", "小时前更新", "VIP资讯", "VIP资讯。", "财联社早知道",
        }
        blocked_terms = (
            "任务wx_",
            "当前步骤",
            "正在执行",
            "启动 codex",
            "元宝",
            "会议",
            "共享屏幕",
            "加入会议",
            "我的 Bot",
            "Bot",
            "Claude",
            "Clauc",
            "session",
        )
        if title in ui_keywords or any(title == kw for kw in ui_keywords):
            return False
        if any(term.lower() in title.lower() for term in blocked_terms):
            return False
        if self._looks_like_non_article_header_text(title):
            return False
        if "账号" in title and len(title) <= 24:
            return False
        if "原创内容" in title or "小时前更新" in title:
            return False
        if title.endswith("媒体") and len(title) <= 12:
            return False
        if title.endswith("号") and len(title) <= 8:
            return False
        return any("\u4e00" <= char <= "\u9fff" for char in title)

    def _dedupe_article_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped = []
        seen = set()
        for candidate in sorted(
            candidates,
            key=lambda item: (
                -float(item.get("signal_score") or 0.0),
                -float(item.get("total_score") or item.get("confidence") or 0.0),
                item.get("y", 0),
                item.get("x", 0),
            ),
        ):
            title = self._normalize_detected_article_text(candidate.get("title") or "")
            if not self._is_probable_article_title(title):
                continue
            candidate["title"] = title
            key = self._article_title_key(title) or (
                int(candidate.get("x", 0)) // 80,
                int(candidate.get("y", 0)) // 36,
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(candidate)
        return deduped

    def _merge_article_titles(
        self,
        visible_titles: List[str],
        read_titles: List[str],
        max_titles: int,
    ) -> List[str]:
        titles: List[str] = []
        seen = set()
        for title in [*(visible_titles or []), *(read_titles or [])]:
            title = (title or "").strip()
            key = self._article_title_key(title)
            if not key or key in seen:
                continue
            seen.add(key)
            titles.append(title)
            if len(titles) >= max_titles:
                break
        return titles

    def _build_article_url_hints(self, proxy_payload: Optional[Dict[str, Any]]) -> Dict[str, str]:
        hints: Dict[str, str] = {}
        if not isinstance(proxy_payload, dict):
            return hints

        for row in proxy_payload.get("articles") or []:
            if not isinstance(row, dict):
                continue
            title_key = self._article_title_key(str(row.get("title") or "").strip())
            url = self._normalize_article_url(row.get("url") or row.get("link") or row.get("source_url"))
            if title_key and url and title_key not in hints:
                hints[title_key] = url
        return hints

    def _article_url_hint_for_title(self, title: str) -> str:
        title_key = self._article_title_key(title)
        if not title_key:
            return ""
        hints = getattr(self, "_article_read_url_hints", {}) or {}
        return self._normalize_article_url(hints.get(title_key) or "")

    def _set_partial_article_read_results(self, articles: List[Dict[str, Any]]) -> None:
        self._partial_article_read_results = [
            dict(article)
            for article in (articles or [])
            if isinstance(article, dict)
        ]

    def _consume_partial_article_read_results(self) -> List[Dict[str, Any]]:
        articles = getattr(self, "_partial_article_read_results", []) or []
        self._partial_article_read_results = []
        return [
            dict(article)
            for article in articles
            if isinstance(article, dict)
        ]

    def _set_last_completed_article_read(self, article: Optional[Dict[str, Any]]) -> None:
        self._last_completed_article_read = dict(article) if isinstance(article, dict) else {}

    def _consume_last_completed_article_read(self) -> Dict[str, Any]:
        article = getattr(self, "_last_completed_article_read", {}) or {}
        self._last_completed_article_read = {}
        return dict(article) if isinstance(article, dict) else {}

    async def _scroll_article_list(
        self,
        article_window_title: Optional[str] = None,
        bounds: Optional[Dict[str, int]] = None,
    ) -> None:
        """Scroll the article list so the next iteration reads a different visible item."""
        try:
            if article_window_title:
                self._raise_wechat_window_by_title(article_window_title)
            elif not self._ensure_wechat_frontmost(activate=False):
                self._ensure_wechat_frontmost(activate=True)
            pyautogui = self.dep_manager.get_dependency("pyautogui") if self.dep_manager else None
            if pyautogui and bounds:
                pyautogui.moveTo(
                    int(bounds["X"] + bounds["Width"] / 2),
                    int(bounds["Y"] + bounds["Height"] / 2),
                    duration=0.1,
                )
            await asyncio.sleep(0.2)
            self.window_manager.scroll_down()
            await asyncio.sleep(1.2)
        except Exception as exc:
            self.logger.warning("滚动文章列表失败: %s", exc)

    async def _open_extract_close_article(
        self,
        article: Dict[str, Any],
        detection_method: str,
    ) -> Optional[Dict[str, Any]]:
        title = (article.get("title") or "").strip()
        x = int(article.get("x", 0))
        y = int(article.get("y", 0))
        article_url = self._normalize_article_url(article.get("url") or article.get("link"))
        article_window_title = article.get("window_title")
        self.logger.info("点击文章: '%s' at (%s, %s)", title, x, y)

        if article_window_title:
            self._raise_wechat_window_by_title(article_window_title)
        elif not self._ensure_wechat_frontmost(activate=False):
            self._ensure_wechat_frontmost(activate=True)
        await asyncio.sleep(0.5)
        click_result = self.click_at(x, y)
        if click_result.status != AutomationStatus.SUCCESS:
            self.logger.warning("点击文章失败: '%s' - %s", title, click_result.message)
            return None

        try:
            self.logger.info("成功点击文章 '%s'，等待文章加载...", title)
            await asyncio.sleep(3.0)
            article_content = await self._extract_article_content(title)
            article_content = await self._promote_article_content_from_url(
                article_content,
                article_url,
                title,
            )
            if article_content and article_content.get("content", "").strip():
                if article_url:
                    article_content.setdefault("url", article_url)
                    article_content.setdefault("link", article_url)
                article_content.setdefault("detection_method", detection_method)
                self._set_last_completed_article_read(article_content)
                self.logger.info(
                    "成功提取文章内容: '%s' (长度: %s)",
                    title,
                    len(article_content.get("content", "")),
                )
                return article_content

            self.logger.info("仅获取文章标题: '%s'", title)
            result = {
                "title": title,
                "content": f"文章标题: {title}",
                "read_success": True,
                "detection_method": f"{detection_method}_title_only",
            }
            if article_url:
                result["url"] = article_url
                result["link"] = article_url
            self._set_last_completed_article_read(result)
            return result
        finally:
            self.logger.info("关闭文章: '%s'", title)
            if not self._ensure_wechat_frontmost(activate=False):
                self._ensure_wechat_frontmost(activate=True)
            await asyncio.sleep(0.3)
            self.gui_automation.close_tab()
            await asyncio.sleep(1.0)
            if article_window_title:
                self._raise_wechat_window_by_title(article_window_title)
                await asyncio.sleep(0.5)

    async def _detect_articles_with_llm(
        self,
        bounds: Dict[str, int],
        candidate_limit: int,
    ) -> List[Dict[str, Any]]:
        """Detect visible article candidates with LLM in the current viewport."""
        if not self.ocr_processor:
            self.logger.error("LLM 文章检测跳过：OCR 处理器不可用")
            return []
        screenshot = self.ocr_processor.capture_screenshot()
        if screenshot is None:
            self.logger.error("无法获取截图")
            return []

        from PIL import Image
        if hasattr(screenshot, "crop"):
            screenshot_pil = screenshot
        elif hasattr(screenshot, "shape"):
            screenshot_pil = Image.fromarray(screenshot)
        else:
            self.logger.error("不支持的截图格式: %s", type(screenshot))
            return []

        full_width, full_height = screenshot_pil.size
        screen_scale = self.llm_element_locator._detect_screen_scale(full_width)
        region_box = (
            max(0, int(bounds["X"] * screen_scale)),
            max(0, int(bounds["Y"] * screen_scale)),
            min(full_width, int((bounds["X"] + bounds["Width"]) * screen_scale)),
            min(full_height, int((bounds["Y"] + bounds["Height"]) * screen_scale)),
        )
        region_screenshot = screenshot_pil.crop(region_box)
        if screen_scale > 1.0:
            logical_w = max(1, int(region_screenshot.size[0] / screen_scale))
            logical_h = max(1, int(region_screenshot.size[1] / screen_scale))
            region_screenshot = region_screenshot.resize((logical_w, logical_h), Image.Resampling.LANCZOS)

        actual_w, actual_h = region_screenshot.size
        if ComputerUseFallbackPromptBuilder:
            articles_prompt = (
                ComputerUseFallbackPromptBuilder.build_wechat_visible_articles_prompt(
                    candidate_limit=candidate_limit,
                    width=actual_w,
                    height=actual_h,
                )
            )
        else:
            articles_prompt = "请分析这张微信公众号文章列表区域截图，找出当前可见的可点击文章条目。"

        screenshot_b64 = self.llm_element_locator._screenshot_helper.screenshot_to_base64(region_screenshot)
        if not screenshot_b64:
            self.logger.error("截图转换失败")
            return []

        if hasattr(self.llm_client, "legacy_visual_fallback"):
            result = await self.llm_client.legacy_visual_fallback(
                articles_prompt,
                screenshot_b64,
            )
        else:
            result = await self.llm_client.analyze_screenshot(
                articles_prompt,
                screenshot_b64,
            )
        if not result or not isinstance(result, dict) or not result.get("found", False):
            self.logger.warning("LLM 未找到文章")
            return []

        screenshot_info = self.llm_element_locator._get_screenshot_info_from_llm()
        candidates = []
        for article in result.get("articles", []):
            title = (article.get("title") or "").strip()
            cx = article.get("center_x")
            cy = article.get("center_y")
            if not title or cx is None or cy is None:
                continue
            if screenshot_info and screenshot_info.was_compressed:
                cx = int(cx / screenshot_info.scale_x)
                cy = int(cy / screenshot_info.scale_y)
            cx = max(0, min(int(cx), max(0, actual_w - 1)))
            cy = max(0, min(int(cy), max(0, actual_h - 1)))
            screen_x = int(bounds["X"] + cx)
            screen_y = int(bounds["Y"] + cy)
            if not self._point_in_bounds(screen_x, screen_y, bounds):
                continue
            candidates.append({
                "title": title,
                "x": screen_x,
                "y": screen_y,
                "confidence": result.get("confidence", 0.0),
                "source": "llm",
            })

        candidates = self._dedupe_article_candidates(candidates)
        self.logger.info("LLM 当前视图找到 %s 个文章候选", len(candidates))
        return candidates

    async def _read_articles_with_llm(
        self,
        bounds: Dict[str, int],
        max_articles: int = 3,
        article_window_title: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Use LLM to read articles one by one, re-detecting after each scroll."""
        try:
            self.logger.info("使用 LLM 逐篇识别并读取文章，最多 %s 篇", max_articles)
            results = []
            self._set_partial_article_read_results(results)
            seen_titles = set()
            attempts = 0
            max_attempts = max(5, max_articles * 4)

            while len(results) < max_articles and attempts < max_attempts:
                attempts += 1
                candidates = await self._detect_articles_with_llm(bounds, max(5, max_articles * 2))
                next_article = None
                for candidate in candidates:
                    key = self._article_title_key(candidate.get("title", ""))
                    if key and key not in seen_titles:
                        next_article = candidate
                        break

                if not next_article:
                    self.logger.info("当前视图没有新的文章候选，滚动后重试")
                    await self._scroll_article_list(article_window_title, bounds)
                    continue

                title_key = self._article_title_key(next_article.get("title", ""))
                seen_titles.add(title_key)
                hinted_url = self._article_url_hint_for_title(next_article.get("title", ""))
                if hinted_url:
                    next_article.setdefault("url", hinted_url)
                    next_article.setdefault("link", hinted_url)
                if article_window_title:
                    next_article["window_title"] = article_window_title
                article_content = await self._open_extract_close_article(next_article, "llm_iterative")
                if article_content:
                    results.append(article_content)
                    self._set_partial_article_read_results(results)

                if len(results) < max_articles:
                    await self._scroll_article_list(article_window_title, bounds)

            self.logger.info("LLM 文章阅读完成: 成功提取 %s 篇文章", len(results))
            self._set_partial_article_read_results(results)
            return results

        except Exception as e:
            self.logger.error(f"LLM 读取文章失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return []

    def _html_to_plain_text_fragment(self, raw_html: Any) -> str:
        text = str(raw_html or "")
        if not text:
            return ""
        text = re.sub(r"<script.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<style.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = html.unescape(re.sub(r"<[^>]+>", " ", text))
        return re.sub(r"\s+", " ", text).strip()

    def _extract_article_title_from_raw_html(self, raw_html: Any) -> str:
        text = str(raw_html or "")
        if not text:
            return ""
        for pattern in (
            r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.*?)["\']',
            r'<h\d[^>]+id=["\']activity-name["\'][^>]*>(.*?)</h\d>',
            r"<title[^>]*>(.*?)</title>",
        ):
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                title = self._html_to_plain_text_fragment(match.group(1))
                if title:
                    return title
        return ""

    def _extract_article_body_html_from_raw_html(self, source_url: str, raw_html: Any) -> str:
        text = str(raw_html or "")
        if not text:
            return ""

        normalized_source = str(source_url or "").lower()
        if "mp.weixin.qq.com" in normalized_source:
            match = re.search(r"(<div[^>]+id=[\"']js_content[\"'][^>]*>.*?</div>)", text, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()
            match = re.search(
                r"(<div[^>]+class=[\"'][^\"']*rich_media_content[^\"']*[\"'][^>]*>.*?</div>)",
                text,
                re.IGNORECASE | re.DOTALL,
            )
            if match:
                return match.group(1).strip()

        match = re.search(r"<body[^>]*>(.*)</body>", text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        return text

    def _looks_like_account_overview_content(self, content: Any, article_title: str = "") -> bool:
        lines = [line.strip() for line in str(content or "").splitlines() if line.strip()]
        if not lines:
            return False

        compact = "\n".join(lines)
        normalized_title = "".join((article_title or "").split())
        if normalized_title and f"{normalized_title}-Account" in "".join(compact.split()):
            return True
        if re.search(r"\d+\s*篇原创内容", compact) and re.search(r"\d+\s*(小时|分钟)前更新", compact):
            return True

        marker_hits = sum(1 for marker in WECHAT_ARTICLE_OVERVIEW_NOISE_MARKERS if marker in compact)
        if marker_hits >= 3:
            return True
        if marker_hits >= 2 and len(lines) >= 6:
            return True
        return False

    def _is_substantive_article_text(self, content: Any, article_title: str = "") -> bool:
        text = self._html_to_plain_text_fragment(content)
        normalized_title = self._html_to_plain_text_fragment(article_title)
        if not text:
            return False
        if normalized_title and text in {normalized_title, f"文章标题: {normalized_title}"}:
            return False
        if len(text) < 28:
            return False
        if not any("\u4e00" <= char <= "\u9fff" for char in text):
            return False
        if self._looks_like_account_overview_content(text, article_title):
            return False
        return True

    def _title_mismatches_expected_article(self, fetched_title: str, expected_title: str) -> bool:
        fetched = self._html_to_plain_text_fragment(fetched_title)
        expected = self._html_to_plain_text_fragment(expected_title)
        if not fetched or not expected:
            return False
        if fetched == expected:
            return False
        if expected in fetched or fetched in expected:
            return False
        return self._text_similarity(fetched, expected) < 0.72

    def _title_only_article_content(
        self,
        article_content: Optional[Dict[str, Any]],
        article_title: str,
        marker: str,
    ) -> Dict[str, Any]:
        fallback_title = self._html_to_plain_text_fragment(article_title) or str(article_title or "").strip()
        title_only_text = f"文章标题: {fallback_title}" if fallback_title else ""
        demoted = dict(article_content or {})
        if fallback_title:
            demoted["title"] = fallback_title
        demoted["content"] = title_only_text
        demoted["read_success"] = True
        demoted["content_length"] = len(title_only_text)
        demoted["content_parts"] = 1 if title_only_text else 0
        demoted.pop("article_html", None)
        previous_method = str(demoted.get("detection_method") or "").strip()
        if previous_method and marker not in previous_method:
            demoted["detection_method"] = f"{previous_method}+{marker}"
        elif marker:
            demoted["detection_method"] = previous_method or marker
        return demoted

    def _fetch_article_html_from_url(self, url: str, timeout_seconds: float = 15.0) -> str:
        normalized_url = self._normalize_article_url(url)
        if not normalized_url.lower().startswith(("http://", "https://")):
            return ""

        import requests

        try:
            response = requests.get(
                normalized_url,
                timeout=timeout_seconds,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/135.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
            )
            response.raise_for_status()
            return response.text
        except Exception as exc:
            self.logger.debug("文章 URL HTML 抓取失败 %s: %s", normalized_url, exc)
            return ""

    async def _promote_article_content_from_url(
        self,
        article_content: Optional[Dict[str, Any]],
        article_url: str,
        article_title: str,
    ) -> Optional[Dict[str, Any]]:
        if not article_content:
            article_content = {}

        normalized_url = self._normalize_article_url(article_url)
        current_text = str(article_content.get("content") or article_content.get("article_html") or "").strip()
        if not normalized_url:
            return article_content
        if self._is_substantive_article_text(current_text, article_title):
            return article_content

        raw_html = await asyncio.to_thread(self._fetch_article_html_from_url, normalized_url)
        if not raw_html:
            return article_content

        article_html = self._extract_article_body_html_from_raw_html(normalized_url, raw_html)
        extracted_text = self._html_to_plain_text_fragment(article_html or raw_html)
        fetched_title = self._extract_article_title_from_raw_html(raw_html) or article_title
        if self._title_mismatches_expected_article(fetched_title, article_title):
            self.logger.info(
                "Skipping URL HTML promotion because fetched title mismatches clicked article: expected=%s fetched=%s url=%s",
                article_title,
                fetched_title,
                normalized_url,
            )
            if not self._is_substantive_article_text(current_text, article_title):
                return self._title_only_article_content(
                    article_content,
                    article_title,
                    "url_title_mismatch_title_only",
                )
            return article_content
        if not self._is_substantive_article_text(extracted_text, fetched_title):
            return article_content

        promoted = dict(article_content)
        promoted["title"] = article_title or fetched_title
        promoted["content"] = extracted_text
        promoted["article_html"] = article_html or raw_html
        promoted["read_success"] = True
        promoted["content_length"] = len(extracted_text)
        promoted["content_parts"] = max(
            int(promoted.get("content_parts") or 0),
            len([line for line in extracted_text.splitlines() if line.strip()]),
        )
        previous_method = str(promoted.get("detection_method") or "").strip()
        promoted["detection_method"] = (
            f"{previous_method}+url_html_fallback" if previous_method else "url_html_fallback"
        )
        return promoted

    async def _extract_article_content(self, article_title: str) -> Optional[Dict[str, Any]]:
        """提取文章内容（在文章页面中获取更详细的内容）"""
        try:
            self.logger.info(f"提取文章内容: {article_title}")

            # 等待内容加载
            await asyncio.sleep(2.0)

            # 捕获文章页面截图
            screenshot = self.ocr_processor.capture_screenshot()
            if screenshot is None:
                self.logger.warning("无法获取文章页面截图")
                return None

            # 使用 OCR 识别页面内容。Even when OCR_ENABLED disables tesseract
            # paths, the base processor can still use macOS Vision on Darwin.
            ocr_results = self._recognize_text_regions(screenshot)
            if not ocr_results:
                return {
                    "title": article_title,
                    "content": f"文章标题: {article_title}",
                    "read_success": True,
                    "detection_method": "title_only_ocr_unavailable",
                    "content_length": len(article_title),
                }
            content_bounds = self._get_frontmost_wechat_window_bounds()
            interaction_bounds = self._get_interaction_bounds()
            if interaction_bounds:
                if not content_bounds:
                    content_bounds = interaction_bounds
                else:
                    front_area = max(1, int(content_bounds["Width"]) * int(content_bounds["Height"]))
                    interaction_area = max(1, int(interaction_bounds["Width"]) * int(interaction_bounds["Height"]))
                    if interaction_area > int(front_area * 1.15):
                        content_bounds = interaction_bounds

            # 过滤和组合有意义的内容 - 更严格的过滤
            content_parts = []
            ui_keywords = [
                '微信', '首页', '消息', '发现', '搜索', '返回', '菜单', '设置', '更多',
                '刷新', '分享', '在看', '评论', '关注', '收藏', '公众号', '文章',
                '原文', '写留言', '留言', '视频', '小程序', '赞', '客服', '听全文',
            ]
            normalized_title = re.sub(r'\s+', '', article_title or '')

            def _reading_region_ok(center_x: int, center_y: int) -> bool:
                if not content_bounds:
                    return True
                if not self._point_in_bounds(center_x, center_y, content_bounds):
                    return False
                width = max(1, int(content_bounds["Width"]))
                height = max(1, int(content_bounds["Height"]))
                rel_x = (center_x - int(content_bounds["X"])) / width
                rel_y = (center_y - int(content_bounds["Y"])) / height
                return 0.06 <= rel_x <= 0.94 and 0.10 <= rel_y <= 0.95

            def _looks_like_body_text(text: str) -> bool:
                compact = re.sub(r'\s+', '', text or '')
                if not compact or compact == normalized_title:
                    return False
                if len(compact) < 6 or compact.isdigit():
                    return False
                if not any('\u4e00' <= char <= '\u9fff' for char in compact):
                    return False
                matched_ui = [kw for kw in ui_keywords if kw in compact]
                if len(matched_ui) >= 2:
                    stripped = compact
                    for keyword in matched_ui:
                        stripped = stripped.replace(keyword, '')
                        stripped = re.sub(r'[：:，,。.!！？?、/|]+', '', stripped)
                    if len(stripped) < 8:
                        return False
                return True

            def _looks_like_loose_body_text(text: str) -> bool:
                compact = re.sub(r'\s+', '', text or '')
                if not compact or compact == normalized_title:
                    return False
                if len(compact) < 4 or compact.isdigit():
                    return False
                if not any('\u4e00' <= char <= '\u9fff' for char in compact):
                    return False
                matched_ui = [kw for kw in ui_keywords if kw in compact]
                if len(matched_ui) >= 3:
                    stripped = compact
                    for keyword in matched_ui:
                        stripped = stripped.replace(keyword, '')
                    stripped = re.sub(r'[：:，,。.!！？?、/|]+', '', stripped)
                    if len(stripped) < 10:
                        return False
                return True

            def _looks_like_fragment_body_text(text: str) -> bool:
                compact = re.sub(r'\s+', '', text or '')
                if not compact or compact == normalized_title:
                    return False
                if len(compact) < 2 or compact.isdigit():
                    return False
                if not any('\u4e00' <= char <= '\u9fff' for char in compact):
                    return False
                if compact in ui_keywords:
                    return False
                if any(marker in compact for marker in ("阅读", "更多", "搜索指定公众号", "常看的号")):
                    return False
                if any(char.isdigit() for char in compact) and len(compact) <= 4 and compact[-1:] in {"人", "次"}:
                    return False
                return True

            def _dedupe_parts(parts: List[Tuple[str, int, int]], limit: int) -> List[str]:
                unique_parts = []
                seen = set()
                for text, _left, _top in parts:
                    key = re.sub(r'\s+', '', text)[:24]
                    if key not in seen and len(unique_parts) < limit:
                        seen.add(key)
                        unique_parts.append(text)
                return unique_parts

            for result in ocr_results:
                text = result.get('text', '').strip()
                confidence = result.get('confidence', 0)
                position = self._ocr_position(result)
                left = position["x"]
                top = position["y"]
                center_x, center_y = self._ocr_center(result, screenshot)
                if not _reading_region_ok(center_x, center_y):
                    continue

                if text and confidence >= 20 and _looks_like_body_text(text):
                    content_parts.append((text, confidence, left, top))  # 保存位置信息用于排序
                    self.logger.debug(f"内容片段: '{text}' (置信度: {confidence}, 位置: ({left}, {top}))")

            # 组合内容 - 按位置排序（从上到下，从左到右）
            if content_parts:
                # 按垂直位置（top）主要排序，水平位置（left）次要排序
                content_parts.sort(key=lambda x: (x[3], x[2]))

                unique_parts = _dedupe_parts(
                    [(text, left, top) for text, _confidence, left, top in content_parts],
                    16,
                )

                full_content = '\n'.join(unique_parts)
                if len(full_content) > 1600:
                    full_content = full_content[:1200] + "..."
                if self._is_substantive_article_text(full_content, article_title):
                    return {
                        "title": article_title,
                        "content": full_content,
                        "read_success": True,
                        "detection_method": "ocr_content_extraction",
                        "content_length": len(full_content),
                        "content_parts": len(unique_parts)
                    }

            self.logger.info("未找到高置信度内容片段，尝试次级内容提取策略")

            # 次级策略：寻找较长的文本块，即使置信度较低
            secondary_parts = []
            for result in ocr_results:
                text = result.get('text', '').strip()
                confidence = result.get('confidence', 0)
                center_x, center_y = self._ocr_center(result, screenshot)
                if not _reading_region_ok(center_x, center_y):
                    continue

                if confidence > 10 and _looks_like_body_text(text):
                    position = self._ocr_position(result)
                    secondary_parts.append((text, position["x"], position["y"]))
                    self.logger.debug(f"次级内容片段: '{text}' (置信度: {confidence})")

            if secondary_parts:
                secondary_parts.sort(key=lambda item: (item[2], item[1]))
                unique_secondary = _dedupe_parts(secondary_parts, 12)
                full_content = '\n'.join(unique_secondary)
                if len(full_content) > 800:
                    full_content = full_content[:800] + "..."
                if self._is_substantive_article_text(full_content, article_title):
                    return {
                        "title": article_title,
                        "content": full_content,
                        "read_success": True,
                        "detection_method": "ocr_secondary_content",
                        "content_length": len(full_content),
                        "content_parts": len(unique_secondary)
                    }

            self.logger.info("次级内容仍不足，尝试聚合正文页 OCR 片段")
            tertiary_parts: List[Tuple[str, int, int]] = []
            for result in ocr_results:
                text = result.get('text', '').strip()
                confidence = result.get('confidence', 0)
                center_x, center_y = self._ocr_center(result, screenshot)
                if not _reading_region_ok(center_x, center_y):
                    continue
                if confidence <= 5 or not _looks_like_loose_body_text(text):
                    continue
                position = self._ocr_position(result)
                tertiary_parts.append((text, position["x"], position["y"]))

            if tertiary_parts:
                tertiary_parts.sort(key=lambda item: (item[2], item[1]))
                unique_tertiary = _dedupe_parts(tertiary_parts, 24)
                full_content = '\n'.join(unique_tertiary)
                if len(full_content) > 1200:
                    full_content = full_content[:1200] + "..."
                if self._is_substantive_article_text(full_content, article_title):
                    return {
                        "title": article_title,
                        "content": full_content,
                        "read_success": True,
                        "detection_method": "ocr_tertiary_content",
                        "content_length": len(full_content),
                        "content_parts": len(unique_tertiary),
                    }

            self.logger.info("三级正文聚合仍不足，尝试拼接短 OCR 片段")
            fragment_parts: List[Tuple[str, int, int]] = []
            for result in ocr_results:
                text = result.get('text', '').strip()
                confidence = result.get('confidence', 0)
                center_x, center_y = self._ocr_center(result, screenshot)
                if not _reading_region_ok(center_x, center_y):
                    continue
                if confidence <= 3 or not _looks_like_fragment_body_text(text):
                    continue
                position = self._ocr_position(result)
                fragment_parts.append((text, position["x"], position["y"]))

            if fragment_parts:
                fragment_parts.sort(key=lambda item: (item[2], item[1]))
                unique_fragments = _dedupe_parts(fragment_parts, 40)
                stitched_parts: List[str] = []
                for fragment in unique_fragments:
                    if (
                        stitched_parts
                        and len(fragment) <= 6
                        and len(stitched_parts[-1]) <= 24
                    ):
                        stitched_parts[-1] = f"{stitched_parts[-1]}{fragment}"
                    else:
                        stitched_parts.append(fragment)
                full_content = '\n'.join(part for part in stitched_parts if part)
                if len(full_content) > 1400:
                    full_content = full_content[:1400] + "..."
                if self._is_substantive_article_text(full_content, article_title):
                    return {
                        "title": article_title,
                        "content": full_content,
                        "read_success": True,
                        "detection_method": "ocr_fragment_stitch_content",
                        "content_length": len(full_content),
                        "content_parts": len(stitched_parts),
                    }
                self.logger.info(
                    "短 OCR 片段拼接后仍非正文: fragments=%s sample=%s",
                    len(unique_fragments),
                    unique_fragments[:8],
                )

            return {
                "title": article_title,
                "content": f"文章标题: {article_title}",
                "read_success": True,
                "detection_method": "ocr_account_overview_title_only",
                "content_length": len(article_title),
                "content_parts": 1 if article_title else 0,
            }

        except Exception as e:
            self.logger.warning(f"提取文章内容失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            # 返回基本信息而不是失败
            return {
                "title": article_title,
                "content": f"文章标题: {article_title}",
                "read_success": True,
                "detection_method": "ocr_fallback",
                "error": str(e)
            }

    def _recognize_text_regions(self, screenshot) -> List[Dict[str, Any]]:
        """Recognize text using the real OCR processor, even when tesseract OCR is disabled."""
        if screenshot is None:
            return []
        try:
            if self.adaptive_ocr:
                return self.adaptive_ocr.recognize(screenshot)
        except Exception as exc:
            self.logger.warning("Adaptive OCR failed, trying base OCR processor: %s", exc)
        try:
            if self.ocr_processor and hasattr(self.ocr_processor, "recognize"):
                return self.ocr_processor.recognize(screenshot)
        except Exception as exc:
            self.logger.warning("Base OCR processor failed: %s", exc)
        return []

    def _detect_articles_with_ocr(
        self,
        bounds: Dict[str, int],
        candidate_limit: int,
    ) -> List[Dict[str, Any]]:
        """Detect visible article candidates with OCR in the current viewport."""
        screenshot = self._capture_region_screenshot(bounds, expected_bounds=bounds)
        if screenshot is None:
            screenshot = self._capture_window_screenshot(bounds)
        if screenshot is None:
            self.logger.error("无法获取截图")
            return []

        ocr_results = self._recognize_text_regions(screenshot)
        article_features = ["的", "了", "在", "是", "有", "和", "与", "或", "但", "因为", "所以"]
        text_records: List[Dict[str, Any]] = []
        for result in ocr_results:
            text = (result.get("text") or "").strip()
            if not text:
                continue
            center_x, center_y = self._ocr_center(result, screenshot)
            if self._point_in_bounds(center_x, center_y, bounds):
                text_records.append({"text": text, "center_y": center_y})
        article_list_floor = self._infer_article_list_content_floor(text_records)
        candidates = []
        for result in ocr_results:
            text = (result.get("text") or "").strip()
            confidence = float(result.get("confidence") or 0)
            if confidence < 28 or not self._is_probable_article_title(text):
                continue

            center_x, center_y = self._ocr_center(result, screenshot)
            if not self._point_in_bounds(center_x, center_y, bounds):
                continue
            if article_list_floor is not None and center_y <= article_list_floor:
                continue

            relative_y = (center_y - bounds["Y"]) / max(1, bounds["Height"])
            if not 0.03 <= relative_y <= 0.97:
                continue

            feature_score = sum(1 for feat in article_features if feat in text)
            signal_score = self._article_trading_signal_score(text)
            total_score = confidence + feature_score * 5 + (10 if 0.08 <= relative_y <= 0.9 else 0) + signal_score * 5
            candidates.append({
                "title": text,
                "x": center_x,
                "y": center_y,
                "confidence": confidence,
                "signal_score": signal_score,
                "total_score": total_score,
                "source": "ocr",
            })

        candidates.sort(key=lambda item: (-item["total_score"], item["y"]))
        candidates = self._dedupe_article_candidates(candidates)[:candidate_limit]
        candidates.sort(key=lambda item: (item["y"], item["x"]))
        self.logger.info("OCR 当前视图找到 %s 个文章候选", len(candidates))
        return candidates

    async def _read_articles_with_ocr(
        self,
        bounds: Dict[str, int],
        max_articles: int = 3,
        article_window_title: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Use OCR fallback to read articles one by one, scrolling between items."""
        try:
            self.logger.info("使用 OCR 逐篇识别并读取文章，最多 %s 篇", max_articles)
            results = []
            self._set_partial_article_read_results(results)
            seen_titles = set()
            attempts = 0
            max_attempts = max(5, max_articles * 4)
            low_signal_scroll_budget = min(max_attempts - 1, max(4, max_articles * 2))

            while len(results) < max_articles and attempts < max_attempts:
                attempts += 1
                candidates = self._detect_articles_with_ocr(bounds, max(5, max_articles * 2))
                next_article = None
                ranked_candidates = sorted(
                    candidates,
                    key=lambda candidate: (
                        -float(candidate.get("signal_score") or 0.0),
                        -float(candidate.get("total_score") or candidate.get("confidence") or 0.0),
                        int(candidate.get("y", 0)),
                        int(candidate.get("x", 0)),
                    ),
                )
                unseen_candidates = [
                    candidate
                    for candidate in ranked_candidates
                    if self._article_title_key(candidate.get("title", "")) not in seen_titles
                ]
                strongest_signal = max(
                    (float(candidate.get("signal_score") or 0.0) for candidate in unseen_candidates),
                    default=float("-inf"),
                )
                if unseen_candidates and strongest_signal <= 0 and attempts <= low_signal_scroll_budget:
                    self.logger.info(
                        "当前视图只有低交易语义文章候选，滚动后继续查找更强主题文章"
                    )
                    await self._scroll_article_list(article_window_title, bounds)
                    continue
                for candidate in ranked_candidates:
                    key = self._article_title_key(candidate.get("title", ""))
                    if key and key not in seen_titles:
                        next_article = candidate
                        break

                if not next_article:
                    self.logger.info("当前视图没有新的 OCR 文章候选，滚动后重试")
                    await self._scroll_article_list(article_window_title, bounds)
                    continue

                title_key = self._article_title_key(next_article.get("title", ""))
                seen_titles.add(title_key)
                hinted_url = self._article_url_hint_for_title(next_article.get("title", ""))
                if hinted_url:
                    next_article.setdefault("url", hinted_url)
                    next_article.setdefault("link", hinted_url)
                if article_window_title:
                    next_article["window_title"] = article_window_title
                article_content = await self._open_extract_close_article(next_article, "ocr_iterative")
                if article_content:
                    results.append(article_content)
                    self._set_partial_article_read_results(results)

                if len(results) < max_articles:
                    await self._scroll_article_list(article_window_title, bounds)

            self.logger.info("OCR 文章阅读完成: 成功提取 %s 篇文章", len(results))
            self._set_partial_article_read_results(results)
            return results

        except Exception as e:
            self.logger.error(f"OCR 读取文章失败: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return []

    async def click_wechat_account(self, bounds: Dict[str, int], account_data: Dict[str, Any]) -> bool:
        """
        点击公众号并打开

        Args:
            bounds: 窗口边界
            account_data: 公众号数据

        Returns:
            bool: 是否成功点击
        """
        try:
            if not self.ocr_enabled:
                self.logger.warning("OCR is disabled, cannot click account")
                return False

            account_name = account_data.get("account_name", "")
            self.logger.info(f"点击公众号: {account_name}")

            # 捕获截图
            screenshot = self.ocr_processor.capture_screenshot()
            if screenshot is None:
                self.logger.error("无法获取截图")
                return False

            # 使用 OCR 查找公众号名称
            ocr_results = self.adaptive_ocr.recognize(screenshot)
            result_region = self._search_results_panel_bounds(bounds)

            for result in ocr_results:
                text = result.get('text', '')
                if account_name in text:
                    self.logger.info(f"找到公众号: {text}")

                    # 计算点击位置
                    center_x, center_y = self._ocr_center(result, screenshot)
                    if not self._point_in_bounds(center_x, center_y, result_region):
                        continue

                    click_result = self.click_at(center_x, center_y)
                    if click_result.status == AutomationStatus.SUCCESS:
                        await asyncio.sleep(2.0)
                        return True

            self.logger.error(f"未找到公众号: {account_name}")
            return False

        except Exception as e:
            self.logger.error(f"点击公众号失败: {e}")
            return False

    # ====== Delegated methods for backward compatibility ======
    async def _llm_locate_element(self, screenshot, element_type: str) -> Optional[Tuple[int, int]]:
        """
        使用 LLM 定位元素位置 (委托给 LLMElementLocator)

        Args:
            screenshot: 截图
            element_type: 元素类型（如"搜索框"）

        Returns:
            元素中心坐标 (x, y)，或 None
        """
        if not getattr(self, "llm_element_locator", None):
            self.logger.warning("LLM 元素定位器未初始化")
            return None
        return await self.llm_element_locator.locate_element(screenshot, element_type)

    async def _llm_find_element(
        self,
        screenshot,
        target_name: str,
        region: Dict[str, int]
    ) -> Optional[Tuple[int, int]]:
        """
        使用 LLM 查找元素 (委托给 LLMElementLocator)

        Args:
            screenshot: 截图
            target_name: 目标名称（如公众号名称）
            region: 搜索区域 {'X': x, 'Y': y, 'Width': w, 'Height': h}

        Returns:
            元素中心坐标 (x, y)，或 None
        """
        if not getattr(self, "llm_element_locator", None):
            self.logger.warning("LLM 元素定位器未初始化")
            return None
        return await self.llm_element_locator.find_element_by_name(screenshot, target_name, region)

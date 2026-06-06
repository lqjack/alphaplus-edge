"""
Dependency Manager for WeChat Viewer Server

Manages lazy loading of GUI automation and OCR dependencies with OS-specific optimization.
"""

import sys
import os
import platform
from typing import Optional, Dict, Any

# Import shared types from core deps
try:
    from core.deps import DependencyInfo, DependencyStatus
except ImportError:
    # Fallback: define locally if core.deps not available
    import sys
    import logging
    from dataclasses import dataclass, field
    from enum import Enum
    from typing import Any, Optional, List

    class DependencyStatus(str, Enum):
        NOT_LOADED = "NOT_LOADED"
        LOADING = "LOADING"
        LOADED = "LOADED"
        FAILED = "FAILED"

    @dataclass
    class DependencyInfo:
        name: str
        description: str = ""
        status: DependencyStatus = DependencyStatus.NOT_LOADED
        instance: Any = None
        error: Optional[str] = None
        os_specific: bool = False
        os_list: List[str] = field(default_factory=list)

        def is_available(self) -> bool:
            return self.status == DependencyStatus.LOADED and self.instance is not None

        def set_loaded(self, instance: Any) -> None:
            """Mark dependency as loaded"""
            self.instance = instance
            self.status = DependencyStatus.LOADED


class WeChatViewerDependencyManager:
    """Manages lazy loading of WeChat Viewer-specific dependencies with OS-specific optimization"""

    def __init__(self):
        self._deps = {}
        self._lock = None  # We'll add async import if needed
        self._initialized = False
        self._os_type = self._detect_os()
        self._platform_name = platform.system().lower()

    def _detect_os(self) -> str:
        """Detect the current operating system"""
        if sys.platform.startswith("win"):
            return "windows"
        elif sys.platform.startswith("darwin"):
            return "macos"
        elif sys.platform.startswith("linux"):
            return "linux"
        else:
            return "unknown"

    def register_dependency(
        self,
        name: str,
        description: str = "",
        os_specific: bool = False,
        os_list: list = None,
    ) -> None:
        """Register a dependency for lazy loading with optional OS-specific information"""
        dep_info = DependencyInfo(name, description)
        dep_info.os_specific = os_specific
        dep_info.os_list = os_list or []
        self._deps[name] = dep_info

    def get_dependency(self, name: str):
        """Get a loaded dependency instance"""
        dep = self._deps.get(name)
        return dep.instance if dep and dep.is_available() else None

    def is_available(self, name: str) -> bool:
        """Check if a dependency is available"""
        dep = self._deps.get(name)
        return dep.is_available() if dep else False

    def get_available_dependencies(self) -> Dict[str, Any]:
        """Get all available dependencies grouped by category"""
        categories = {"gui": {}, "ocr": {}, "config": {}, "standard": {}}

        for name, dep in self._deps.items():
            if dep.is_available():
                if name in ["pyautogui", "quartz", "win32gui", "Xlib"]:
                    categories["gui"][name] = dep.instance
                elif name in ["PIL", "pytesseract"]:
                    categories["ocr"][name] = dep.instance
                elif name in ["logger", "database_adapter", "run_with_app"]:
                    categories["config"][name] = dep.instance
                else:
                    categories["standard"][name] = dep.instance

        return categories

    def initialize_all(self) -> None:
        """Initialize all registered dependencies based on OS"""
        if self._initialized:
            return

        print(
            f"INFO: Initializing WeChat Viewer MCP server dependencies for {self._os_type}...",
            file=sys.stderr,
        )
        print(f"INFO: Detected platform: {self._platform_name}", file=sys.stderr)

        # Initialize dependencies in order based on OS
        self._init_standard_dependencies()
        self._init_gui_dependencies()
        self._init_ocr_dependencies()
        self._init_config_dependencies()
        self._init_llm_dependencies()
        self._init_cross_platform_dependencies()

        self._initialized = True
        print(
            "INFO: WeChat Viewer dependencies initialized successfully", file=sys.stderr
        )

    def _init_standard_dependencies(self) -> None:
        """Initialize standard library dependencies (cross-platform)"""
        try:
            # Register standard dependencies
            self.register_dependency("subprocess", "System subprocess management")
            self.register_dependency("time", "Time utilities")
            self.register_dependency("os", "Operating system interface")
            self.register_dependency("sys", "System-specific parameters")

            # Import standard libraries
            try:
                import subprocess
                import time
                import os as os_module
                import sys as sys_module

                self._deps["subprocess"].set_loaded(subprocess)
                self._deps["time"].set_loaded(time)
                self._deps["os"].set_loaded(os_module)
                self._deps["sys"].set_loaded(sys_module)

                print(
                    f"INFO: Standard dependencies loaded for {self._os_type}",
                    file=sys.stderr,
                )
            except ImportError as e:
                print(
                    f"WARNING: Standard libraries not available: {e}", file=sys.stderr
                )
                for dep_name in ["subprocess", "time", "os", "sys"]:
                    self._deps[dep_name].set_loaded(None)

        except Exception as e:
            print(
                f"WARNING: Standard dependencies loading failed: {e}", file=sys.stderr
            )

    def _init_gui_dependencies(self) -> None:
        """Initialize GUI automation dependencies based on OS"""
        try:
            # Register OS-specific GUI dependencies
            self.register_dependency(
                "pyautogui", "Cross-platform GUI automation library", os_specific=False
            )

            if self._os_type == "macos":
                self.register_dependency(
                    "quartz",
                    "macOS Quartz window management",
                    os_specific=True,
                    os_list=["macos"],
                )
            elif self._os_type == "windows":
                self.register_dependency(
                    "win32gui",
                    "Windows GUI automation",
                    os_specific=True,
                    os_list=["windows"],
                )
            elif self._os_type == "linux":
                self.register_dependency(
                    "Xlib",
                    "Linux X11 window management",
                    os_specific=True,
                    os_list=["linux"],
                )

            # Try to import pyautogui (cross-platform)
            try:
                import pyautogui

                self._deps["pyautogui"].set_loaded(pyautogui)
                print(
                    "INFO: pyautogui loaded (cross-platform GUI automation)",
                    file=sys.stderr,
                )
            except ImportError:
                print("WARNING: pyautogui not available", file=sys.stderr)
                self._deps["pyautogui"].set_loaded(None)

            # Load OS-specific GUI dependencies
            if self._os_type == "macos":
                self._init_macos_gui_dependencies()
            elif self._os_type == "windows":
                self._init_windows_gui_dependencies()
            elif self._os_type == "linux":
                self._init_linux_gui_dependencies()

        except Exception as e:
            print(f"WARNING: GUI dependencies loading failed: {e}", file=sys.stderr)

    def _init_macos_gui_dependencies(self) -> None:
        """Initialize macOS-specific GUI dependencies"""
        try:
            # Try to import Quartz (macOS specific)
            try:
                import Quartz

                self._deps["quartz"].set_loaded(Quartz)
                print("INFO: Quartz loaded (macOS window management)", file=sys.stderr)
            except ImportError:
                print("WARNING: Quartz not available (macOS only)", file=sys.stderr)
                self._deps["quartz"].set_loaded(None)

        except Exception as e:
            print(
                f"WARNING: macOS GUI dependencies loading failed: {e}", file=sys.stderr
            )

    def _init_windows_gui_dependencies(self) -> None:
        """Initialize Windows-specific GUI dependencies"""
        try:
            # Try to import win32gui (Windows specific)
            try:
                import win32gui

                self._deps["win32gui"].set_loaded(win32gui)
                print("INFO: win32gui loaded (Windows GUI automation)", file=sys.stderr)
            except ImportError:
                print("WARNING: win32gui not available (Windows only)", file=sys.stderr)
                self._deps["win32gui"].set_loaded(None)

        except Exception as e:
            print(
                f"WARNING: Windows GUI dependencies loading failed: {e}",
                file=sys.stderr,
            )

    def _init_linux_gui_dependencies(self) -> None:
        """Initialize Linux-specific GUI dependencies"""
        try:
            # Try to import Xlib (Linux specific)
            try:
                from Xlib import display

                self._deps["Xlib"].set_loaded(display)
                print(
                    "INFO: Xlib loaded (Linux X11 window management)", file=sys.stderr
                )
            except ImportError:
                print("WARNING: Xlib not available (Linux only)", file=sys.stderr)
                self._deps["Xlib"].set_loaded(None)

        except Exception as e:
            print(
                f"WARNING: Linux GUI dependencies loading failed: {e}", file=sys.stderr
            )

    def _init_ocr_dependencies(self) -> None:
        """Initialize OCR dependencies (cross-platform)"""
        try:
            # Register OCR dependencies
            self.register_dependency("PIL", "Python Imaging Library", os_specific=False)
            self.register_dependency("pytesseract", "OCR library", os_specific=False)

            # Try to import PIL
            try:
                from PIL import Image

                self._deps["PIL"].set_loaded(Image)
                print("INFO: PIL loaded (image processing)", file=sys.stderr)
            except ImportError:
                print("WARNING: PIL not available", file=sys.stderr)
                self._deps["PIL"].set_loaded(None)

            # Try to import pytesseract
            try:
                import pytesseract

                self._deps["pytesseract"].set_loaded(pytesseract)
                print("INFO: pytesseract loaded (OCR processing)", file=sys.stderr)
            except ImportError:
                print("WARNING: pytesseract not available", file=sys.stderr)
                self._deps["pytesseract"].set_loaded(None)

        except Exception as e:
            print(f"WARNING: OCR dependencies loading failed: {e}", file=sys.stderr)

    def _init_config_dependencies(self) -> None:
        """Initialize configuration dependencies (cross-platform)"""
        try:
            # Register config dependencies
            self.register_dependency("logger", "Logging system", os_specific=False)
            self.register_dependency(
                "database_adapter", "MongoDB adapter", os_specific=False
            )
            self.register_dependency(
                "run_with_app", "Flask app context decorator", os_specific=False
            )

            # Try to import logger
            try:
                from core.logger import setup_logger

                logger_instance = setup_logger(
                    "mcp-server-wechat-viewer-mcp", log_to_console=False
                )
                self._deps["logger"].set_loaded(logger_instance)
                print("INFO: Logger loaded", file=sys.stderr)
            except ImportError:
                # Fallback to basic logging
                import logging

                logger_instance = logging.getLogger("mcp-server-wechat-viewer-mcp")
                logger_instance.setLevel(logging.INFO)
                self._deps["logger"].set_loaded(logger_instance)
                print("INFO: Basic logger loaded (fallback)", file=sys.stderr)

            # Try to import database adapter
            try:
                from api.rest.mongodb_adapter import account_adapter

                self._deps["database_adapter"].set_loaded(account_adapter)
                print("INFO: Database adapter loaded", file=sys.stderr)
            except ImportError:
                print("WARNING: Database adapter not available", file=sys.stderr)
                self._deps["database_adapter"].set_loaded(None)

            # Try to import Flask app context decorator
            try:
                from core.tools.article_content_check import run_with_app

                self._deps["run_with_app"].set_loaded(run_with_app)
                print("INFO: Flask app context decorator loaded", file=sys.stderr)
            except ImportError:
                print(
                    "WARNING: Flask app context decorator not available",
                    file=sys.stderr,
                )
                self._deps["run_with_app"].set_loaded(None)

        except Exception as e:
            print(f"WARNING: Config dependencies loading failed: {e}", file=sys.stderr)

    def _init_llm_dependencies(self) -> None:
        """Initialize LLM dependencies for intelligent search and analysis"""
        try:
            # Register LLM dependencies
            self.register_dependency("llm_chain", "LLM chain instance")
            self.register_dependency("settings", "AI model settings")

            # Register cross-platform automation dependencies
            from mcp_core.dependency_types import (
                CROSS_PLATFORM_AUTOMATION_ENGINE,
                MACOS_ADAPTER,
                WINDOWS_ADAPTER,
                ADAPTIVE_ELEMENT_LOCATOR,
                LLM_TASK_PLANNER,
                INTELLIGENT_EXECUTION_MONITOR,
                STATE_PERSISTENCE_LAYER,
                CONFIG_MANAGER,
                OPENAI_VISION_LOCATOR
            )

            self.register_dependency(CROSS_PLATFORM_AUTOMATION_ENGINE, "Cross-platform automation engine")
            self.register_dependency(MACOS_ADAPTER, "macOS platform adapter")
            self.register_dependency(WINDOWS_ADAPTER, "Windows platform adapter")
            self.register_dependency(ADAPTIVE_ELEMENT_LOCATOR, "Adaptive element locator")
            self.register_dependency(LLM_TASK_PLANNER, "LLM task planner")
            self.register_dependency(INTELLIGENT_EXECUTION_MONITOR, "Intelligent execution monitor")
            self.register_dependency(STATE_PERSISTENCE_LAYER, "State persistence layer")
            self.register_dependency(CONFIG_MANAGER, "Configuration manager")
            self.register_dependency(OPENAI_VISION_LOCATOR, "OpenAI vision element locator")
            from mcp_core.dependency_types import WINDOW_MANAGER
            self.register_dependency(WINDOW_MANAGER, "Window manager")

            # Try to load settings from environment variables
            try:
                from dotenv import load_dotenv
                try:
                    from core.service_ports import get_port

                    gateway_default = f"http://localhost:{get_port('gateway', 'api')}"
                except Exception:
                    gateway_default = "http://localhost:8001"

                load_dotenv()

                settings = {
                    "AI_REQUEST_MODEL": os.getenv("AI_REQUEST_MODEL", "gpt-4"),
                    "AI_MODEL": os.getenv("AI_MODEL", "gpt-4"),
                    "AI_KEY": os.getenv("AI_KEY", ""),
                    "AI_BASE_URL": os.getenv("AI_BASE_URL", ""),
                    "AI_TEMPERATURE": float(os.getenv("AI_TEMPERATURE", "0.7")),
                    "AI_MAX_TOKENS": int(os.getenv("AI_MAX_TOKENS", "2000")),
                    "GATEWAY_URL": os.getenv("GATEWAY_URL", gateway_default),
                    "GATEWAY_API_KEY": os.getenv("GATEWAY_API_KEY", ""),
                }
                self._deps["settings"].set_loaded(settings)
                print(
                    f"INFO: LLM settings loaded: model={settings.get('AI_REQUEST_MODEL')}",
                    file=sys.stderr,
                )
            except Exception as e:
                print(f"WARNING: Failed to load LLM settings: {e}", file=sys.stderr)
                self._deps["settings"].set_loaded({})

            # Try to create MCP-based LLM client
            try:
                # Detect which MCP server to use (stdio or API mode)
                mcp_server_name = "ai"
                mcp_url = os.getenv("MCP_AI_URL")
                if mcp_url:
                    mcp_server_name = "ai_api"
                    print(
                        f"INFO: Using API mode for AI MCP server: {mcp_url}",
                        file=sys.stderr,
                    )
                else:
                    print(f"INFO: Using stdio mode for AI MCP server", file=sys.stderr)

                # Import and create MCP-based LLM client
                from mcp_core.llm_protocol import MCPBasedLLMClient

                llm_client = MCPBasedLLMClient(mcp_server_name=mcp_server_name)
                self._deps["llm_chain"].set_loaded(llm_client)
                print(
                    "INFO: LLM client (MCPBasedLLMClient) initialized successfully",
                    file=sys.stderr,
                )
            except ImportError as e:
                print(f"WARNING: MCPBasedLLMClient not available: {e}", file=sys.stderr)
                self._deps["llm_chain"].set_loaded(None)
            except Exception as e:
                print(f"WARNING: Failed to initialize LLM client: {e}", file=sys.stderr)
                self._deps["llm_chain"].set_loaded(None)

            # Import OpenAI vision locator for type hints (do this later in the init function)
            OpenAIVisionLocator = None
            OPENAI_VISION_LOCATOR = None

        except Exception as e:
            import traceback
            print(f"WARNING: LLM dependencies loading failed: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            self._deps["llm_chain"].set_loaded(None)
            self._deps["settings"].set_loaded({})

    def _init_cross_platform_dependencies(self) -> None:
        """Initialize cross-platform automation dependencies"""
        try:
            from mcp_core.dependency_types import (
                CROSS_PLATFORM_AUTOMATION_ENGINE,
                MACOS_ADAPTER,
                WINDOWS_ADAPTER,
                ADAPTIVE_ELEMENT_LOCATOR,
                LLM_TASK_PLANNER,
                INTELLIGENT_EXECUTION_MONITOR,
                STATE_PERSISTENCE_LAYER,
                CONFIG_MANAGER,
                WINDOW_MANAGER,
                OPENAI_VISION_LOCATOR,
            )

            # Import the actual implementation classes
            from mcp_core.cross_platform_automation import CrossPlatformAutomationEngine
            from mcp_core.macos_adapter import MacOSAccessibilityAdapter
            from mcp_core.windows_adapter import WindowsUIAutomationAdapter
            from mcp_core.adaptive_locator import AdaptiveElementLocator
            from mcp_core.execution_monitor import IntelligentExecutionMonitor
            from mcp_core.llm_task_planner import LLMTaskPlanner
            from mcp_core.state_persistence import StatePersistenceLayer
            from mcp_core.window_manager import MacOSWindowManager, WindowsWindowManager

            # Initialize platform-specific Window Manager
            if self._os_type == "darwin" or self._os_type == "macos":
                window_manager = MacOSWindowManager(self)
            elif self._os_type == "windows":
                window_manager = WindowsWindowManager(self)
            else:
                window_manager = None
            
            if window_manager:
                self._deps[WINDOW_MANAGER].set_loaded(window_manager)
                print(f"INFO: {self._os_type} Window Manager initialized", file=sys.stderr)

            # Initialize platform-specific adapters based on OS
            if self._os_type == "darwin" or self._os_type == "macos":
                macos_adapter = MacOSAccessibilityAdapter(self)
                self._deps[MACOS_ADAPTER].set_loaded(macos_adapter)
                print("INFO: macOS adapter initialized", file=sys.stderr)
            elif self._os_type == "windows":
                windows_adapter = WindowsUIAutomationAdapter(self)
                self._deps[WINDOWS_ADAPTER].set_loaded(windows_adapter)
                print("INFO: Windows adapter initialized", file=sys.stderr)

            # Initialize the cross-platform automation engine with the dependency manager
            # Now all adapters are loaded in self._deps, so the engine can find them
            cross_platform_engine = CrossPlatformAutomationEngine(self)
            self._deps[CROSS_PLATFORM_AUTOMATION_ENGINE].set_loaded(cross_platform_engine)
            print(
                f"INFO: Cross-platform automation engine initialized",
                file=sys.stderr,
            )

            # Initialize other cross-platform components
            adaptive_locator = AdaptiveElementLocator(self)
            self._deps[ADAPTIVE_ELEMENT_LOCATOR].set_loaded(adaptive_locator)

            execution_monitor = IntelligentExecutionMonitor(self)
            self._deps[INTELLIGENT_EXECUTION_MONITOR].set_loaded(execution_monitor)

            task_planner = LLMTaskPlanner(self)
            self._deps[LLM_TASK_PLANNER].set_loaded(task_planner)

            # Initialize OpenAI vision locator only when gateway credentials are present.
            try:
                settings = self._deps["settings"].instance if self._deps["settings"].is_available() else {}
                gateway_url = settings.get("GATEWAY_URL", "")
                api_key = settings.get("GATEWAY_API_KEY", "")
                if gateway_url:
                    from automation.openai_vision_locator import OpenAIVisionLocator

                    # Get logger instance if available
                    logger_instance = None
                    if self._deps["logger"].is_available():
                        logger_instance = self._deps["logger"].instance

                    openai_vision_locator = OpenAIVisionLocator(
                        gateway_url=gateway_url,
                        api_key=api_key,
                        logger=logger_instance
                    )
                    self._deps[OPENAI_VISION_LOCATOR].set_loaded(openai_vision_locator)
                    print(f"INFO: OpenAI vision locator initialized: gateway @ {gateway_url}", file=sys.stderr)
                else:
                    print("INFO: OpenAI vision locator not configured: GATEWAY_URL is empty", file=sys.stderr)
                    self._deps[OPENAI_VISION_LOCATOR].set_loaded(None)
            except Exception as e:
                print(f"WARNING: Failed to initialize OpenAI vision locator: {e}", file=sys.stderr)
                self._deps[OPENAI_VISION_LOCATOR].set_loaded(None)

            state_persistence = StatePersistenceLayer(self)
            self._deps[STATE_PERSISTENCE_LAYER].set_loaded(state_persistence)

            print("INFO: Cross-platform dependencies initialization completed", file=sys.stderr)


        except Exception as e:
            import traceback
            print(f"WARNING: Cross-platform dependencies loading failed: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            # Set all cross-platform dependencies to None/failed state
            from mcp_core.dependency_types import (
                CROSS_PLATFORM_AUTOMATION_ENGINE,
                MACOS_ADAPTER,
                WINDOWS_ADAPTER,
                ADAPTIVE_ELEMENT_LOCATOR,
                LLM_TASK_PLANNER,
                INTELLIGENT_EXECUTION_MONITOR,
                STATE_PERSISTENCE_LAYER,
                CONFIG_MANAGER,
                WINDOW_MANAGER,
                OPENAI_VISION_LOCATOR,
            )
            for dep_name in [CROSS_PLATFORM_AUTOMATION_ENGINE, MACOS_ADAPTER, WINDOWS_ADAPTER,
                           ADAPTIVE_ELEMENT_LOCATOR, LLM_TASK_PLANNER, INTELLIGENT_EXECUTION_MONITOR,
                           STATE_PERSISTENCE_LAYER, CONFIG_MANAGER, WINDOW_MANAGER, OPENAI_VISION_LOCATOR]:
                self._deps[dep_name].set_loaded(None)


# Global dependency manager instance
_wechat_viewer_dependency_manager = None


def get_dependency_manager() -> WeChatViewerDependencyManager:
    """Get global WeChat Viewer dependency manager instance"""
    global _wechat_viewer_dependency_manager
    if _wechat_viewer_dependency_manager is None:
        _wechat_viewer_dependency_manager = WeChatViewerDependencyManager()
    return _wechat_viewer_dependency_manager

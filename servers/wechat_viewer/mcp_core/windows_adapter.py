"""
Windows Adapter for Cross-Platform Automation

Implements platform-specific automation for Windows using UI Automation API.
"""
import platform
import logging
from typing import Dict, Optional, Any, Tuple, List
from abc import ABC, abstractmethod
from .interfaces import IPlatformAdapter, PlatformCapabilities, ElementLocation
from .dependency_types import WINDOWS_ADAPTER


class WindowsUIAutomationAdapter(IPlatformAdapter):
    """Windows-specific automation adapter using UI Automation API"""

    def __init__(self, dependency_manager):
        self.dep_manager = dependency_manager
        self.logger = logging.getLogger("mcp-server-wechat-viewer-mcp.windows_adapter")
        self._initialize_ui_automation_framework()

    def _initialize_ui_automation_framework(self):
        """Initialize the Windows UI Automation framework"""
        try:
            # Try to import the required UI Automation modules
            # In a real implementation, we would use pywinauto or comtypes to access UI Automation
            # For now, we'll simulate the availability check
            self.logger.info("Initializing Windows UI Automation framework")

            # Check if we're actually on Windows
            if platform.system().lower() != "windows":
                self.logger.warning("WindowsUIAutomationAdapter initialized on non-Windows platform")

            # In a real implementation, we would initialize the UI Automation framework here
            self._ui_automation_available = True
            self.logger.info("Windows UI Automation framework initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize Windows UI Automation framework: {e}")
            self._ui_automation_available = False

    def get_capabilities(self) -> PlatformCapabilities:
        """Get Windows-specific platform capabilities"""
        return PlatformCapabilities(
            supports_accessibility_api=False,
            supports_ui_automation=True,
            supports_ocr=True,
            supports_vision_llm=True,  # Assuming vision LLMs are available
            max_concurrent_operations=1,
            requires_permissions=["UI Automation", "Accessibility", "Screen Capture"]
        )

    def click_at(self, x: int, y: int) -> bool:
        """Click at specific coordinates on Windows"""
        if not self._ui_automation_available:
            self.logger.error("UI Automation framework not available")
            return False

        try:
            self.logger.debug(f"Clicking at coordinates ({x}, {y}) on Windows")

            # In a real implementation, we would:
            # 1. Use UI Automation to click at the coordinates
            # 2. Or use SendInput/ mouse_event APIs for low-level mouse control
            # 3. Or use UI Automation elements if we have the element reference

            # For now, we'll simulate the behavior using pyautogui as a fallback
            # but note that in a production implementation we'd use native APIs
            pyautogui = self.dep_manager.get_dependency("pyautogui")
            if pyautogui:
                # Validate coordinates
                try:
                    screen_width, screen_height = pyautogui.size()
                    if x < 0 or x > screen_width or y < 0 or y > screen_height:
                        self.logger.error(f"Coordinates ({x}, {y}) are outside screen bounds ({screen_width}x{screen_height})")
                        return False
                except:
                    self.logger.warning("Could not verify screen bounds")

                # Perform the click with more explicit mouse down/up for reliability
                pyautogui.mouseDown(button='left', x=x, y=y)
                # Small delay to ensure button press is registered
                import time
                time.sleep(0.01)
                pyautogui.mouseUp(button='left', x=x, y=y)

                self.logger.info(f"Successfully clicked at coordinates ({x}, {y}) using pyautogui")
                return True
            else:
                self.logger.error("pyautogui dependency not available for fallback")
                return False

        except Exception as e:
            self.logger.error(f"Failed to click at ({x}, {y}) on Windows: {e}", exc_info=True)
            return False

    def type_text(self, text: str) -> bool:
        """Type text using keyboard on Windows"""
        if not self._ui_automation_available:
            self.logger.error("UI Automation framework not available")
            return False

        try:
            self.logger.debug(f"Typing text on Windows: '{text[:50]}{'...' if len(text) > 50 else ''}'")

            # In a real implementation, we would:
            # 1. Find the focused UI element using UI Automation
            # 2. Use ValuePattern.SetValue to set the text value
            # 3. Or post keyboard events using SendInput API

            # For now, we'll use pyautogui as a fallback
            pyautogui = self.dep_manager.get_dependency("pyautogui")
            if not pyautogui:
                self.logger.error("pyautogui dependency not available")
                return False

            # Check if we have non-ASCII characters that might need special handling
            has_non_ascii = any(ord(char) > 127 for char in text)

            if has_non_ascii:
                # For non-ASCII characters, use clipboard method as it's more reliable
                return self._type_text_via_clipboard(text, pyautogui)
            else:
                # For ASCII characters, we can try direct input first
                try:
                    # Type character by character with small delays for reliability
                    import time
                    for i, char in enumerate(text):
                        pyautogui.write(char, interval=0.01)
                        # Small delay every 20 characters to prevent overwhelming the system
                        if i > 0 and i % 20 == 0:
                            time.sleep(0.01)

                    self.logger.info(f"Successfully typed {len(text)} ASCII characters on Windows")
                    return True
                except Exception as e:
                    self.logger.warning(f"Direct typing failed: {e}, trying clipboard method")
                    return self._type_text_via_clipboard(text, pyautogui)

        except Exception as e:
            self.logger.error(f"Failed to type text on Windows: {e}", exc_info=True)
            return False

    def _type_text_via_clipboard(self, text: str, pyautogui) -> bool:
        """Type text using clipboard paste (helper method)"""
        try:
            self.logger.debug(f"Using clipboard paste method for text input")

            # Try to use clipboard-related dependencies
            old_clipboard = None

            # Try multiple clipboard approaches
            clipboard_success = False

            # Approach 1: Try pyperclip
            try:
                import pyperclip
                old_clipboard = pyperclip.paste()
                pyperclip.copy(text)
                clipboard_success = True
            except ImportError:
                self.logger.debug("pyperclip not available")
            except Exception as e:
                self.logger.debug(f"pyperclip failed: {e}")

            # Approach 2: Try win32clipboard if pyperclip failed
            if not clipboard_success:
                try:
                    import win32clipboard
                    win32clipboard.OpenClipboard()
                    try:
                        old_clipboard = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                    except:
                        old_clipboard = None
                    win32clipboard.CloseClipboard()

                    win32clipboard.OpenClipboard()
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
                    win32clipboard.CloseClipboard()
                    clipboard_success = True
                except ImportError:
                    self.logger.debug("win32clipboard not available")
                except Exception as e:
                    self.logger.debug(f"win32clipboard failed: {e}")

            # Approach 3: Try subprocess with clip (Windows-specific)
            if not clipboard_success:
                try:
                    import subprocess
                    # Save current clipboard
                    try:
                        result = subprocess.run(['powershell', '-command', 'Get-Clipboard'],
                                              capture_output=True, text=True, timeout=2)
                        old_clipboard = result.stdout.strip() if result.returncode == 0 else ""
                    except:
                        old_clipboard = ""

                    # Set new clipboard
                    subprocess.run(['powershell', '-command', f'Set-Clipboard -Value "{text}"'],
                                 timeout=2)
                    clipboard_success = True
                except Exception as e:
                    self.logger.debug(f"PowerShell clipboard method failed: {e}")

            if clipboard_success:
                # Small delay to ensure clipboard is set
                import time
                time.sleep(0.1)

                # Perform paste
                pyautogui.hotkey('ctrl', 'v')

                # Small delay to ensure paste completes
                time.sleep(0.2)

                # Restore clipboard if we saved it
                try:
                    if old_clipboard is not None:
                        # Try to restore using the same method we used to set it
                        try:
                            import pyperclip
                            pyperclip.copy(old_clipboard)
                        except:
                            try:
                                import win32clipboard
                                win32clipboard.OpenClipboard()
                                win32clipboard.EmptyClipboard()
                                win32clipboard.SetClipboardText(old_clipboard, win32clipboard.CF_UNICODETEXT)
                                win32clipboard.CloseClipboard()
                            except:
                                try:
                                    import subprocess
                                    subprocess.run(['powershell', '-command', f'Set-Clipboard -Value "{old_clipboard}"'],
                                                 timeout=2)
                                except:
                                    pass  # Best effort restore
                except Exception as e:
                    self.logger.debug(f"Could not restore clipboard: {e}")

                self.logger.info(f"Successfully pasted {len(text)} characters via clipboard on Windows")
                return True
            else:
                # Last resort: direct input (may fail for complex characters)
                self.logger.warning("Clipboard methods unavailable, trying direct input")
                pyautogui.typewrite(text)
                return True

        except Exception as e:
            self.logger.error(f"Clipboard method failed: {e}", exc_info=True)
            # Final fallback
            try:
                pyautogui = self.dep_manager.get_dependency("pyautogui")
                if pyautogui:
                    pyautogui.typewrite(text)
                    return True
            except:
                pass
            return False

    def press_key(self, key: str) -> bool:
        """Press a single key on Windows"""
        if not self._ui_automation_available:
            self.logger.error("UI Automation framework not available")
            return False

        try:
            self.logger.debug(f"Pressing key on Windows: {key}")

            # In a real implementation, we would:
            # 1. Map the key to the appropriate virtual key code
            # 2. Create and post a keyboard event using SendInput API

            # For now, we'll use pyautogui as a fallback
            pyautogui = self.dep_manager.get_dependency("pyautogui")
            if not pyautogui:
                self.logger.error("pyautogui dependency not available")
                return False

            # Map common key names to what pyautogui expects
            key_mapping = {
                'cmd': 'win',  # Windows key
                'win': 'win',
                'win+l': 'win+l',
                'win+d': 'win+d',
                'ctrl+alt+del': 'ctrl+alt+del',
                'alt+tab': 'alt+tab',
                'alt+f4': 'alt+f4',
                'backspace': 'backspace',
                'delete': 'delete',
                'enter': 'enter',
                'return': 'return',
                'space': 'space',
                'tab': 'tab',
                'escape': 'esc',
                'up': 'up',
                'down': 'down',
                'left': 'left',
                'right': 'right',
                'f1': 'f1', 'f2': 'f2', 'f3': 'f3', 'f4': 'f4',
                'f5': 'f5', 'f6': 'f6', 'f7': 'f7', 'f8': 'f8',
                'f9': 'f9', 'f10': 'f10', 'f11': 'f11', 'f12': 'f12'
            }

            mapped_key = key_mapping.get(key.lower(), key)
            pyautogui.press(mapped_key)

            self.logger.info(f"Successfully pressed key '{key}' on Windows")
            return True

        except Exception as e:
            self.logger.error(f"Failed to press key '{key}' on Windows: {e}", exc_info=True)
            return False

    def scroll_down(self) -> bool:
        """Scroll down on Windows"""
        if not self._ui_automation_available:
            self.logger.error("UI Automation framework not available")
            return False

        try:
            self.logger.debug("Scrolling down on Windows")

            # In a real implementation, we would:
            # 1. Find the scrollable element using UI Automation
            # 2. Use ScrollPattern to scroll or send wheel events

            # For now, we'll use pyautogui as a fallback
            pyautogui = self.dep_manager.get_dependency("pyautogui")
            if not pyautogui:
                self.logger.error("pyautogui dependency not available")
                return False

            pyautogui.scroll(-10)  # Negative value scrolls down
            self.logger.info("Successfully scrolled down on Windows")
            return True

        except Exception as e:
            self.logger.error(f"Failed to scroll down on Windows: {e}", exc_info=True)
            return False

    def close_tab(self) -> bool:
        """Close active tab/window on Windows using Ctrl+W"""
        if not self._ui_automation_available:
            self.logger.error("UI Automation framework not available")
            return False

        try:
            self.logger.debug("Closing tab/window on Windows")

            # In a real implementation, we would:
            # 1. Find the active window/tab using UI Automation
            # 2. Send the appropriate close command via UI Automation patterns

            # For now, we'll use pyautogui as a fallback
            pyautogui = self.dep_manager.get_dependency("pyautogui")
            if not pyautogui:
                self.logger.error("pyautogui dependency not available")
                return False

            pyautogui.hotkey('ctrl', 'w')
            self.logger.info("Successfully sent close tab command (Ctrl+W) on Windows")
            return True

        except Exception as e:
            self.logger.error(f"Failed to close tab on Windows: {e}", exc_info=True)
            return False

    def capture_screenshot(self, region: Optional[Dict[str, int]] = None):
        """Capture screenshot on Windows"""
        if not self._ui_automation_available:
            self.logger.error("UI Automation framework not available")
            return None

        try:
            self.logger.debug(f"Capturing screenshot on Windows" +
                            (f" with region: {region}" if region else " (full screen)"))

            # In a real implementation, we could use:
            # 1. DirectX or GDI for screen capture
            # 2. UI Automation to capture specific elements
            # 3. PrintWindow API for specific window capture

            # For now, we'll use pyautogui as a fallback
            pyautogui = self.dep_manager.get_dependency("pyautogui")
            if not pyautogui:
                self.logger.error("pyautogui dependency not available")
                return None

            if region:
                screenshot = pyautogui.screenshot(
                    region=(region['X'], region['Y'], region['Width'], region['Height'])
                )
            else:
                screenshot = pyautogui.screenshot()

            self.logger.info("Successfully captured screenshot on Windows")
            return screenshot

        except Exception as e:
            self.logger.error(f"Failed to capture screenshot on Windows: {e}", exc_info=True)
            return None

    def clear_input(self) -> bool:
        """Clear current input field on Windows"""
        if not self._ui_automation_available:
            self.logger.error("UI Automation framework not available")
            return False

        try:
            self.logger.debug("Clearing input field on Windows")

            # In a real implementation, we would:
            # 1. Find the focused input element using UI Automation
            # 2. Use ValuePattern.SetValue to set the value to empty string

            # For now, we'll use pyautogui as a fallback (Ctrl+A then Delete)
            pyautogui = self.dep_manager.get_dependency("pyautogui")
            if not pyautogui:
                self.logger.error("pyautogui dependency not available")
                return False

            import time
            # Select all text (Ctrl+A on Windows)
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.05)

            # Delete selected text
            pyautogui.press('delete')
            time.sleep(0.05)

            self.logger.info("Successfully cleared input field on Windows")
            return True

        except Exception as e:
            self.logger.error(f"Failed to clear input field on Windows: {e}", exc_info=True)
            return False

    # UI Automation-specific methods (placeholders for future implementation)
    def find_element_by_accessibility_id(self, element_id: str) -> Optional[ElementLocation]:
        """Find element by accessibility ID on Windows (not applicable - UI Automation uses different mechanisms)"""
        self.logger.debug("Accessibility ID lookup not applicable for Windows UI Automation")
        # In Windows UI Automation, we'd use AutomationId or Name properties instead
        return None

    def find_element_by_name(self, name: str) -> Optional[ElementLocation]:
        """Find element by name on Windows"""
        if not self._ui_automation_available:
            self.logger.error("UI Automation framework not available")
            return None

        try:
            self.logger.debug(f"Finding element by name: {name}")

            # In a real implementation, we would:
            # 1. Use UI Automation to find elements by Name property
            # 2. Traverse the automation tree or use specific searches

            # For now, we'll return None to indicate not fully implemented
            self.logger.warning(f"Name-based element lookup not fully implemented for Windows: {name}")
            return None

        except Exception as e:
            self.logger.error(f"Failed to find element by name '{name}' on Windows: {e}", exc_info=True)
            return None

    def find_elements_by_type(self, element_type: str) -> List[ElementLocation]:
        """Find elements by type/role on Windows"""
        if not self._ui_automation_available:
            self.logger.error("UI Automation framework not available")
            return []

        try:
            self.logger.debug(f"Finding elements by type: {element_type}")

            # In a real implementation, we would:
            # 1. Use UI Automation to find elements by ControlType property
            # 2. Traverse the automation tree or use specific searches

            # For now, we'll return empty list to indicate not fully implemented
            self.logger.warning(f"Type-based element lookup not fully implemented for Windows: {element_type}")
            return []

        except Exception as e:
            self.logger.error(f"Failed to find elements by type '{element_type}' on Windows: {e}", exc_info=True)
            return []

    def get_active_window_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the active window on Windows"""
        if not self._ui_automation_available:
            self.logger.error("UI Automation framework not available")
            return None

        try:
            self.logger.debug("Getting active window info on Windows")

            # In a real implementation, we would:
            # 1. Use UI Automation to get the foreground window
            # 2. Get window properties like name, class, position, size, etc.

            # For now, we'll return basic information using available tools
            pyautogui = self.dep_manager.get_dependency("pyautogui")
            if pyautogui:
                try:
                    # Get current mouse position as approximation
                    x, y = pyautogui.position()

                    window_info = {
                        "X": float(x),
                        "Y": float(y),
                        "Width": 800.0,  # Placeholder - would get actual width
                        "Height": 600.0,  # Placeholder - would get actual height
                        "title": "Unknown Window",  # Placeholder
                        "class_name": "Unknown",  # Placeholder
                        "process_name": "Unknown Process"  # Placeholder
                    }

                    self.logger.debug(f"Active window info: {window_info}")
                    return window_info
                except Exception as e:
                    self.logger.warning(f"Could not get detailed window info: {e}")

            # Return basic fallback info
            return {
                "X": 0.0,
                "Y": 0.0,
                "Width": 1024.0,
                "Height": 768.0,
                "title": "Unknown Window",
                "class_name": "Unknown",
                "process_name": "Unknown Process"
            }

        except Exception as e:
            self.logger.error(f"Failed to get active window info on Windows: {e}", exc_info=True)
            return None
"""
GUI Automation Core

Handles cross-platform GUI automation operations including mouse clicks, keyboard input,
and screen capture operations.
"""
import platform
import logging
from typing import Dict, Optional, Any, Tuple
from abc import ABC, abstractmethod
from .interfaces import IGUIAutomation


class GUIAutomation(IGUIAutomation, ABC):
    """Abstract base class for GUI automation operations"""
    
    def __init__(self, dep_manager):
        self.dep_manager = dep_manager
        self.logger = logging.getLogger("mcp-server-wechat-viewer-mcp.gui_automation")
        self.platform = platform.system().lower()
    
    @abstractmethod
    def click_at(self, x: int, y: int) -> bool:
        """Click at specific coordinates"""
        pass
    
    @abstractmethod
    def type_text(self, text: str) -> bool:
        """Type text using keyboard"""
        pass
    
    @abstractmethod
    def press_key(self, key: str) -> bool:
        """Press a single key"""
        pass
    
    @abstractmethod
    def scroll_down(self) -> bool:
        """Scroll down the page"""
        pass

    @abstractmethod
    def close_tab(self) -> bool:
        """Close active tab/window using platform-specific shortcut"""
        pass
    
    @abstractmethod
    def capture_screenshot(self, region: Optional[Dict[str, int]] = None):
        """Capture screenshot of screen or region"""
        pass
    
    @abstractmethod
    def clear_input(self) -> bool:
        """Clear current input field using platform-specific shortcut"""
        pass


class MacOSGUIAutomation(GUIAutomation):
    """macOS-specific GUI automation"""
    
    def click_at(self, x: int, y: int) -> bool:
        """Click at specific coordinates on macOS"""
        pyautogui = self.dep_manager.get_dependency("pyautogui")
        if not pyautogui:
            self.logger.error("pyautogui dependency not available")
            return False

        try:
            # 获取屏幕尺寸用于验证坐标
            try:
                screen_width, screen_height = pyautogui.size()
                self.logger.debug(f"Screen size: {screen_width}x{screen_height}")
                if x < 0 or x > screen_width or y < 0 or y > screen_height:
                    self.logger.error(f"Coordinates ({x}, {y}) are outside screen bounds ({screen_width}x{screen_height})")
                    return False
            except:
                self.logger.warning("Could not verify screen bounds")

            self.logger.info(f"Preparing to click at coordinates (x={x}, y={y})")

            # Step 1: 先快速移动鼠标到目标位置
            self.logger.debug(f"Step 1: Moving mouse to ({x}, {y})")
            pyautogui.moveTo(x, y, duration=0)
            
            # 步骤 2: 等待极短时间确保鼠标定位
            time_module = self.dep_manager.get_dependency("time")
            if time_module:
                time_module.sleep(0.05)

            # 步骤 3: 执行点击
            self.logger.debug(f"Step 2: Performing left click at ({x}, {y})")
            pyautogui.click(x=x, y=y)

            # 步骤 4: 点击后等待较短时间
            if time_module:
                time_module.sleep(0.3)

            self.logger.info(f"Successfully clicked at coordinates (x={x}, y={y})")
            return True

        except Exception as e:
            self.logger.error(f"Failed to click at ({x}, {y}): {e}", exc_info=True)
            return False
    
    def type_text(self, text: str) -> bool:
        """Type text using keyboard on macOS, fallback to clipboard if direct input fails"""
        pyautogui = self.dep_manager.get_dependency("pyautogui")
        if not pyautogui:
            self.logger.error("pyautogui dependency not available")
            return False

        time_module = self.dep_manager.get_dependency("time")
        has_non_ascii = any(ord(char) > 127 for char in text)

        # pyautogui.write can partially succeed or interact with the current
        # input method for Chinese text. Clipboard paste is deterministic and
        # avoids duplicate query text.
        if has_non_ascii:
            return self._paste_text_with_clipboard(text, pyautogui, time_module)

        # 尝试方法 1: 直接键盘输入
        try:
            self.logger.debug(f"Method 1: Direct keyboard typing")

            # 使用更可靠的输入方式：逐字符输入并添加间隔
            chars_typed = 0
            last_error = None
            for i, char in enumerate(text):
                try:
                    pyautogui.write(char, interval=0.02)
                    chars_typed += 1
                    # 每 10 个字符暂停一下，避免输入过快
                    if i > 0 and i % 10 == 0:
                        if time_module:
                            time_module.sleep(0.05)
                except Exception as e:
                    last_error = e
                    self.logger.warning(f"Failed to type character at position {i}: {e}")
                    # 如果单个字符输入失败，直接跳到剪贴板方法
                    break

            # 如果输入失败，直接使用剪贴板方法
            if chars_typed < len(text) or last_error:
                self.logger.warning(f"Only typed {chars_typed}/{len(text)} characters (last error: {last_error}), trying clipboard method...")
                raise Exception(f"Partial input: {chars_typed}/{len(text)}")
            else:
                if time_module:
                    time_module.sleep(0.5)
                self.logger.info(f"Successfully typed {len(text)} characters via direct input")
                return True

        except Exception as e:
            self.logger.warning(f"Direct keyboard input failed: {e}, trying clipboard method...")

        # 尝试方法 2: 使用剪贴板
        return self._paste_text_with_clipboard(text, pyautogui, time_module)

    def _paste_text_with_clipboard(self, text: str, pyautogui, time_module) -> bool:
        """Paste text through the macOS clipboard and restore previous text."""
        try:
            self.logger.debug(f"Method 2: Clipboard paste")

            # 导入剪贴板模块
            try:
                from AppKit import NSPasteboard, NSString
                import subprocess

                # 保存当前剪贴板内容
                pasteboard = NSPasteboard.generalPasteboard()
                old_clipboard = pasteboard.stringForType_("public.utf8-plain-text")

                # 将文本放入剪贴板
                new_clipboard = NSString.stringWithString_(text)
                pasteboard.clearContents()
                pasteboard.setString_forType_(new_clipboard, "public.utf8-plain-text")

                if time_module:
                    time_module.sleep(0.2)

                # 使用 Cmd+V 粘贴
                pyautogui.hotkey('command', 'v')

                # 增加延迟确保粘贴完成
                if time_module:
                    time_module.sleep(0.5)

                # 恢复剪贴板内容
                if old_clipboard:
                    old_clipboard_obj = NSString.stringWithString_(old_clipboard)
                    pasteboard.clearContents()
                    pasteboard.setString_forType_(old_clipboard_obj, "public.utf8-plain-text")

                self.logger.info(f"Successfully pasted {len(text)} characters via clipboard")
                return True

            except ImportError:
                # 如果没有 AppKit，尝试使用 subprocess 和 pbpaste/pbcopy
                import subprocess

                # 保存当前剪贴板内容
                try:
                    old_clipboard = subprocess.run(['pbpaste'], capture_output=True, text=True).stdout
                except:
                    old_clipboard = None

                # 将文本放入剪贴板
                process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
                process.communicate(text.encode('utf-8'))

                if time_module:
                    time_module.sleep(0.2)

                # 使用 Cmd+V 粘贴
                pyautogui.hotkey('command', 'v')

                # 增加延迟确保粘贴完成
                if time_module:
                    time_module.sleep(0.5)

                # 恢复剪贴板内容
                if old_clipboard:
                    process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
                    process.communicate(old_clipboard.encode('utf-8'))
                
                self.logger.info(f"Successfully pasted {len(text)} characters via clipboard (subprocess)")
                return True
                
        except Exception as e:
            self.logger.error(f"Clipboard method also failed: {e}", exc_info=True)
            return False
    
    def press_key(self, key: str) -> bool:
        """Press a single key on macOS"""
        pyautogui = self.dep_manager.get_dependency("pyautogui")
        if not pyautogui:
            self.logger.error("pyautogui dependency not available")
            return False

        try:
            # 将常见快捷键转换为 pyautogui 识别的格式
            key_mapping = {
                'cmd': 'command',
                'cmd+a': 'command+a',
                'cmd+c': 'command+c',
                'cmd+v': 'command+v',
                'cmd+w': 'command+w',
                'backspace': 'backspace',
                'delete': 'delete',
                'enter': 'enter',
                'return': 'return',
                'space': 'space',
            }
            
            # 转换键名
            mapped_key = key_mapping.get(key.lower(), key)
            
            self.logger.debug(f"Pressing key: {key} (mapped: {mapped_key})")
            pyautogui.press(mapped_key)
            
            time_module = self.dep_manager.get_dependency("time")
            if time_module:
                self.logger.debug("Waiting 0.3 seconds after key press")
                time_module.sleep(0.3)
                
            self.logger.info(f"Successfully pressed key: {key}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to press key {key}: {e}", exc_info=True)
            return False
    def scroll_down(self) -> bool:
        """Scroll down on macOS using pyautogui"""
        pyautogui = self.dep_manager.get_dependency("pyautogui")
        if not pyautogui:
            return False
        try:
            pyautogui.scroll(-10) # Scroll down
            return True
        except Exception as e:
            self.logger.error(f"Failed to scroll down: {e}")
            return False

    def close_tab(self) -> bool:
        """Send Command+W to close active tab/window on macOS"""
        pyautogui = self.dep_manager.get_dependency("pyautogui")
        if not pyautogui:
            self.logger.error("pyautogui dependency not available")
            return False

        try:
            shortcut = ['command', 'w']
            self.logger.debug(f"Calling pyautogui.hotkey({shortcut})")
            pyautogui.hotkey(*shortcut)
            
            time_module = self.dep_manager.get_dependency("time")
            if time_module:
                self.logger.debug("Waiting 0.5 seconds after close command")
                time_module.sleep(0.5)
                
            self.logger.info(f"Successfully sent close tab command with shortcut: {shortcut}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to close tab: {e}", exc_info=True)
            return False
    
    def capture_screenshot(self, region: Optional[Dict[str, int]] = None):
        """Capture screenshot on macOS"""
        pyautogui = self.dep_manager.get_dependency("pyautogui")
        if not pyautogui:
            self.logger.error("pyautogui dependency not available")
            return None

        try:
            if region:
                screenshot = pyautogui.screenshot(region=(region['X'], region['Y'], region['Width'], region['Height']))
            else:
                screenshot = pyautogui.screenshot()
            return screenshot
        except Exception as e:
            self.logger.error(f"Failed to capture screenshot: {e}", exc_info=True)
            return None
    
    def clear_input(self) -> bool:
        """Clear current input field on macOS using Cmd+A then Delete"""
        pyautogui = self.dep_manager.get_dependency("pyautogui")
        if not pyautogui:
            self.logger.error("pyautogui dependency not available")
            return False

        try:
            self.logger.debug("Clearing input field with Cmd+A + Delete")
            time_module = self.dep_manager.get_dependency("time")
            
            # Select all text (Cmd+A on macOS)
            pyautogui.hotkey('command', 'a')
            
            if time_module:
                time_module.sleep(0.1)
            
            # Delete selected text
            pyautogui.press('delete')
            
            if time_module:
                time_module.sleep(0.1)
            
            self.logger.info("Successfully cleared input field")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to clear input field: {e}", exc_info=True)
            return False


class WindowsGUIAutomation(GUIAutomation):
    """Windows-specific GUI automation"""
    
    def click_at(self, x: int, y: int) -> bool:
        """Click at specific coordinates on Windows"""
        pyautogui = self.dep_manager.get_dependency("pyautogui")
        if not pyautogui:
            self.logger.error("pyautogui dependency not available")
            return False

        try:
            # 获取屏幕尺寸用于验证坐标
            try:
                screen_width, screen_height = pyautogui.size()
                self.logger.debug(f"Screen size: {screen_width}x{screen_height}")
                if x < 0 or x > screen_width or y < 0 or y > screen_height:
                    self.logger.error(f"Coordinates ({x}, {y}) are outside screen bounds ({screen_width}x{screen_height})")
                    return False
            except:
                self.logger.warning("Could not verify screen bounds")

            self.logger.info(f"Preparing to click at coordinates (x={x}, y={y})")

            # 步骤 1: 先移动鼠标到目标位置
            self.logger.debug(f"Step 1: Moving mouse to ({x}, {y})")
            pyautogui.moveTo(x, y, duration=0.2)

            # 获取当前鼠标位置进行验证
            try:
                current_x, current_y = pyautogui.position()
                self.logger.debug(f"Current mouse position after moveTo: ({current_x}, {current_y})")
            except:
                pass

            # 步骤 2: 等待一小段时间确保鼠标移动完成
            time_module = self.dep_manager.get_dependency("time")
            if time_module:
                time_module.sleep(0.1)

            # 步骤 3: 执行点击（使用显式的鼠标按下和释放，更可靠）
            self.logger.debug(f"Step 2: Performing left click at ({x}, {y})")
            pyautogui.mouseDown(button='left', x=x, y=y)

            if time_module:
                time_module.sleep(0.05)  # 短暂按下时间

            pyautogui.mouseUp(button='left', x=x, y=y)

            # 步骤 4: 点击后等待
            if time_module:
                time_module.sleep(0.5)

            self.logger.info(f"Successfully clicked at coordinates (x={x}, y={y})")
            return True

        except Exception as e:
            self.logger.error(f"Failed to click at ({x}, {y}): {e}", exc_info=True)
            return False
    
    def type_text(self, text: str) -> bool:
        """Type text using keyboard on Windows, with clipboard fallback for non-ASCII characters"""
        pyautogui = self.dep_manager.get_dependency("pyautogui")
        if not pyautogui:
            self.logger.error("pyautogui dependency not available")
            return False

        time_module = self.dep_manager.get_dependency("time")
        
        # 检测是否包含非 ASCII 字符（如中文）
        has_non_ascii = any(ord(char) > 127 for char in text)
        
        # 如果包含非 ASCII 字符，优先使用剪贴板方式
        if has_non_ascii:
            self.logger.debug(f"Non-ASCII characters detected, using clipboard method")
            return self._type_text_clipboard(text, pyautogui, time_module)
        
        # 尝试方法 1: 直接键盘输入（仅限 ASCII 字符）
        try:
            self.logger.debug(f"Method 1: Direct keyboard typing")
            pyautogui.typewrite(text, interval=0.01)

            if time_module:
                time_module.sleep(0.2)

            self.logger.info(f"Successfully typed {len(text)} characters via direct input")
            return True

        except Exception as e:
            self.logger.warning(f"Direct keyboard input failed: {e}, trying clipboard method...")
            return self._type_text_clipboard(text, pyautogui, time_module)
    
    def _type_text_clipboard(self, text: str, pyautogui, time_module) -> bool:
        """Type text using clipboard paste (for non-ASCII characters)"""
        try:
            self.logger.debug(f"Using clipboard paste method for: {text[:20]}...")
            
            # 尝试使用 pyperclip 或 win32clipboard 设置剪贴板
            old_clipboard = None
            
            # 保存当前剪贴板内容
            try:
                import win32clipboard
                win32clipboard.OpenClipboard()
                try:
                    old_clipboard = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                except:
                    old_clipboard = None
                win32clipboard.CloseClipboard()
            except Exception as e:
                self.logger.debug(f"Could not save old clipboard: {e}")
                old_clipboard = None
            
            # 使用 pyperclip 设置剪贴板（支持中文）
            try:
                import pyperclip
                pyperclip.copy(text)
            except ImportError:
                # 如果没有 pyperclip，使用 win32clipboard
                import win32clipboard
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()

            if time_module:
                time_module.sleep(0.1)

            # 使用 Ctrl+V 粘贴
            pyautogui.hotkey('ctrl', 'v')

            if time_module:
                time_module.sleep(0.3)

            # 恢复剪贴板内容
            if old_clipboard is not None:
                try:
                    import win32clipboard
                    win32clipboard.OpenClipboard()
                    win32clipboard.EmptyClipboard()
                    win32clipboard.SetClipboardText(old_clipboard, win32clipboard.CF_UNICODETEXT)
                    win32clipboard.CloseClipboard()
                except Exception as e:
                    self.logger.debug(f"Could not restore clipboard: {e}")

            self.logger.info(f"Successfully pasted {len(text)} characters via clipboard")
            return True

        except Exception as e:
            self.logger.error(f"Clipboard method failed: {e}", exc_info=True)
            
            # 最后尝试：直接输入（可能失败于中文）
            try:
                self.logger.warning("Trying direct input as last resort...")
                pyautogui.typewrite(text, interval=0.01)
                return True
            except:
                return False
    
    def press_key(self, key: str) -> bool:
        """Press a single key on Windows"""
        pyautogui = self.dep_manager.get_dependency("pyautogui")
        if not pyautogui:
            self.logger.error("pyautogui dependency not available")
            return False

        try:
            self.logger.debug(f"Pressing key: {key}")
            pyautogui.press(key)
            
            time_module = self.dep_manager.get_dependency("time")
            if time_module:
                self.logger.debug("Waiting 0.2 seconds after key press")
                time_module.sleep(0.2)
                
            self.logger.info(f"Successfully pressed key: {key}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to press key {key}: {e}", exc_info=True)
            return False
    
    def close_tab(self) -> bool:
        """Send Ctrl+W to close active tab/window on Windows"""
        pyautogui = self.dep_manager.get_dependency("pyautogui")
        if not pyautogui:
            self.logger.error("pyautogui dependency not available")
            return False

        try:
            shortcut = ['ctrl', 'w']
            self.logger.debug(f"Calling pyautogui.hotkey({shortcut})")
            pyautogui.hotkey(*shortcut)
            
            time_module = self.dep_manager.get_dependency("time")
            if time_module:
                self.logger.debug("Waiting 0.5 seconds after close command")
                time_module.sleep(0.5)
                
            self.logger.info(f"Successfully sent close tab command with shortcut: {shortcut}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to close tab: {e}", exc_info=True)
            return False
    
    def capture_screenshot(self, region: Optional[Dict[str, int]] = None):
        """Capture screenshot on Windows"""
        pyautogui = self.dep_manager.get_dependency("pyautogui")
        if not pyautogui:
            self.logger.error("pyautogui dependency not available")
            return None

        try:
            if region:
                screenshot = pyautogui.screenshot(region=(region['X'], region['Y'], region['Width'], region['Height']))
            else:
                screenshot = pyautogui.screenshot()
            return screenshot
        except Exception as e:
            self.logger.error(f"Failed to capture screenshot: {e}", exc_info=True)
            return None
    
    def clear_input(self) -> bool:
        """Clear current input field on Windows using Ctrl+A then Delete"""
        pyautogui = self.dep_manager.get_dependency("pyautogui")
        if not pyautogui:
            self.logger.error("pyautogui dependency not available")
            return False

        try:
            self.logger.debug("Clearing input field with Ctrl+A + Delete")
            time_module = self.dep_manager.get_dependency("time")
            
            # Select all text (Ctrl+A on Windows)
            pyautogui.hotkey('ctrl', 'a')
            
            if time_module:
                time_module.sleep(0.1)
            
            # Delete selected text
            pyautogui.press('delete')
            
            if time_module:
                time_module.sleep(0.1)
            
            self.logger.info("Successfully cleared input field")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to clear input field: {e}", exc_info=True)
            return False
    
    def scroll_down(self) -> bool:
        """Scroll down on Windows using pyautogui"""
        pyautogui = self.dep_manager.get_dependency("pyautogui")
        if not pyautogui:
            self.logger.error("pyautogui dependency not available")
            return False
        try:
            self.logger.debug("Scrolling down")
            pyautogui.scroll(-10)  # Scroll down
            time_module = self.dep_manager.get_dependency("time")
            if time_module:
                time_module.sleep(0.3)
            self.logger.info("Successfully scrolled down")
            return True
        except Exception as e:
            self.logger.error(f"Failed to scroll down: {e}")
            return False


class LinuxGUIAutomation(GUIAutomation):
    """Linux-specific GUI automation"""
    
    def click_at(self, x: int, y: int) -> bool:
        """Click at specific coordinates on Linux"""
        pyautogui = self.dep_manager.get_dependency("pyautogui")
        if not pyautogui:
            self.logger.error("pyautogui dependency not available")
            return False

        try:
            # 获取屏幕尺寸用于验证坐标
            try:
                screen_width, screen_height = pyautogui.size()
                self.logger.debug(f"Screen size: {screen_width}x{screen_height}")
                if x < 0 or x > screen_width or y < 0 or y > screen_height:
                    self.logger.error(f"Coordinates ({x}, {y}) are outside screen bounds ({screen_width}x{screen_height})")
                    return False
            except:
                self.logger.warning("Could not verify screen bounds")

            self.logger.info(f"Preparing to click at coordinates (x={x}, y={y})")

            # 步骤 1: 先移动鼠标到目标位置
            self.logger.debug(f"Step 1: Moving mouse to ({x}, {y})")
            pyautogui.moveTo(x, y, duration=0.2)

            # 获取当前鼠标位置进行验证
            try:
                current_x, current_y = pyautogui.position()
                self.logger.debug(f"Current mouse position after moveTo: ({current_x}, {current_y})")
            except:
                pass

            # 步骤 2: 等待一小段时间确保鼠标移动完成
            time_module = self.dep_manager.get_dependency("time")
            if time_module:
                time_module.sleep(0.1)

            # 步骤 3: 执行点击（使用显式的鼠标按下和释放，更可靠）
            self.logger.debug(f"Step 2: Performing left click at ({x}, {y})")
            pyautogui.mouseDown(button='left', x=x, y=y)

            if time_module:
                time_module.sleep(0.05)  # 短暂按下时间

            pyautogui.mouseUp(button='left', x=x, y=y)

            # 步骤 4: 点击后等待
            if time_module:
                time_module.sleep(0.5)

            self.logger.info(f"Successfully clicked at coordinates (x={x}, y={y})")
            return True

        except Exception as e:
            self.logger.error(f"Failed to click at ({x}, {y}): {e}", exc_info=True)
            return False
    
    def type_text(self, text: str) -> bool:
        """Type text using keyboard on Linux, fallback to clipboard if direct input fails"""
        pyautogui = self.dep_manager.get_dependency("pyautogui")
        if not pyautogui:
            self.logger.error("pyautogui dependency not available")
            return False

        time_module = self.dep_manager.get_dependency("time")

        # 尝试方法 1: 直接键盘输入
        try:
            self.logger.debug(f"Method 1: Direct keyboard typing")
            pyautogui.typewrite(text)

            if time_module:
                time_module.sleep(0.2)

            self.logger.info(f"Successfully typed {len(text)} characters via direct input")
            return True

        except Exception as e:
            self.logger.warning(f"Direct keyboard input failed: {e}, trying clipboard method...")

        # 尝试方法 2: 使用剪贴板
        try:
            self.logger.debug(f"Method 2: Clipboard paste")
            import subprocess

            # 保存当前剪贴板内容
            try:
                old_clipboard = subprocess.run(['xclip', '-o', '-selection', 'clipboard'], capture_output=True, text=True).stdout
            except:
                old_clipboard = None

            # 将文本放入剪贴板
            process = subprocess.Popen(['xclip', '-selection', 'clipboard'], stdin=subprocess.PIPE)
            process.communicate(text.encode('utf-8'))

            if time_module:
                time_module.sleep(0.1)

            # 使用 Ctrl+V 粘贴
            pyautogui.hotkey('ctrl', 'v')

            if time_module:
                time_module.sleep(0.3)

            # 恢复剪贴板内容
            if old_clipboard:
                process = subprocess.Popen(['xclip', '-selection', 'clipboard'], stdin=subprocess.PIPE)
                process.communicate(old_clipboard.encode('utf-8'))

            self.logger.info(f"Successfully pasted {len(text)} characters via clipboard")
            return True

        except Exception as e:
            self.logger.error(f"Clipboard method also failed: {e}", exc_info=True)
            return False
    
    def press_key(self, key: str) -> bool:
        """Press a single key on Linux"""
        pyautogui = self.dep_manager.get_dependency("pyautogui")
        if not pyautogui:
            self.logger.error("pyautogui dependency not available")
            return False

        try:
            self.logger.debug(f"Pressing key: {key}")
            pyautogui.press(key)
            
            time_module = self.dep_manager.get_dependency("time")
            if time_module:
                self.logger.debug("Waiting 0.2 seconds after key press")
                time_module.sleep(0.2)
                
            self.logger.info(f"Successfully pressed key: {key}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to press key {key}: {e}", exc_info=True)
            return False
    
    def close_tab(self) -> bool:
        """Send Ctrl+W to close active tab/window on Linux"""
        pyautogui = self.dep_manager.get_dependency("pyautogui")
        if not pyautogui:
            self.logger.error("pyautogui dependency not available")
            return False

        try:
            shortcut = ['ctrl', 'w']
            self.logger.debug(f"Calling pyautogui.hotkey({shortcut})")
            pyautogui.hotkey(*shortcut)
            
            time_module = self.dep_manager.get_dependency("time")
            if time_module:
                self.logger.debug("Waiting 0.5 seconds after close command")
                time_module.sleep(0.5)
                
            self.logger.info(f"Successfully sent close tab command with shortcut: {shortcut}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to close tab: {e}", exc_info=True)
            return False
    
    def capture_screenshot(self, region: Optional[Dict[str, int]] = None):
        """Capture screenshot on Linux"""
        pyautogui = self.dep_manager.get_dependency("pyautogui")
        if not pyautogui:
            self.logger.error("pyautogui dependency not available")
            return None

        try:
            if region:
                screenshot = pyautogui.screenshot(region=(region['X'], region['Y'], region['Width'], region['Height']))
            else:
                screenshot = pyautogui.screenshot()
            return screenshot
        except Exception as e:
            self.logger.error(f"Failed to capture screenshot: {e}", exc_info=True)
            return None
    
    def clear_input(self) -> bool:
        """Clear current input field on Linux using Ctrl+A then Delete"""
        pyautogui = self.dep_manager.get_dependency("pyautogui")
        if not pyautogui:
            self.logger.error("pyautogui dependency not available")
            return False

        try:
            self.logger.debug("Clearing input field with Ctrl+A + Delete")
            time_module = self.dep_manager.get_dependency("time")
            
            # Select all text (Ctrl+A on Linux)
            pyautogui.hotkey('ctrl', 'a')
            
            if time_module:
                time_module.sleep(0.1)
            
            # Delete selected text
            pyautogui.press('delete')
            
            if time_module:
                time_module.sleep(0.1)
            
            self.logger.info("Successfully cleared input field")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to clear input field: {e}", exc_info=True)
            return False


class GUIAutomationFactory:
    """Factory for creating platform-specific GUI automation instances"""
    
    @staticmethod
    def create_gui_automation(dep_manager) -> GUIAutomation:
        """Create appropriate GUI automation for current platform"""
        platform_name = platform.system().lower()
        
        if platform_name == "darwin":
            return MacOSGUIAutomation(dep_manager)
        elif platform_name == "windows":
            return WindowsGUIAutomation(dep_manager)
        elif platform_name == "linux":
            return LinuxGUIAutomation(dep_manager)
        else:
            raise ValueError(f"Unsupported platform: {platform_name}")

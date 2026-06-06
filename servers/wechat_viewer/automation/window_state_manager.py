"""
window_state_manager.py - 智能窗口状态管理
解决：窗口状态感知不足
"""

import platform
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging
import time
import asyncio


@dataclass
class WindowState:
    """窗口状态快照"""
    is_visible: bool
    is_minimized: bool
    is_foreground: bool
    bounds: Dict[str, int]
    display_index: int  # 多显示器支持
    z_order: int        # 窗口层级
    last_active: datetime
    occlusion_ratio: float = 0.0  # 被遮挡比例
    screenshot_hash: Optional[str] = None


class WindowStateManager:
    """窗口状态管理器 - 处理多显示器、遮挡、最小化等场景"""
    
    def __init__(self, window_manager):
        self.wm = window_manager
        self.platform = platform.system().lower()
        self.logger = logging.getLogger("window_state")
        
        # 状态历史
        self.state_history: List[WindowState] = []
        self.max_history = 100
        
        # 多显示器信息
        self.displays = self._enumerate_displays()
        
    def _enumerate_displays(self) -> List[Dict]:
        """枚举所有显示器"""
        displays = []
        
        if self.platform == "windows":
            try:
                import win32api
                import win32con
                
                def callback(monitor, dc, rect, data):
                    displays.append({
                        'index': len(displays),
                        'left': rect[0],
                        'top': rect[1],
                        'right': rect[2],
                        'bottom': rect[3],
                        'width': rect[2] - rect[0],
                        'height': rect[3] - rect[1],
                        'is_primary': (win32api.GetMonitorInfo(monitor).get('Flags') 
                                      & win32con.MONITORINFOF_PRIMARY) != 0
                    })
                    return True
                    
                win32api.EnumDisplayMonitors(None, None, callback, None)
            except ImportError:
                self.logger.warning("win32api not available")
                
        elif self.platform == "darwin":
            try:
                from AppKit import NSScreen
                for i, screen in enumerate(NSScreen.screens()):
                    frame = screen.frame()
                    displays.append({
                        'index': i,
                        'left': int(frame.origin.x),
                        'top': int(frame.origin.y),
                        'right': int(frame.origin.x + frame.size.width),
                        'bottom': int(frame.origin.y + frame.size.height),
                        'width': int(frame.size.width),
                        'height': int(frame.size.height),
                        'is_primary': i == 0
                    })
            except ImportError:
                self.logger.warning("AppKit not available")
                
        return displays
        
    def get_current_state(self) -> Optional[WindowState]:
        """获取当前窗口状态"""
        try:
            # 基础信息
            bounds = self.wm.get_window_bounds()
            if not bounds:
                return None
                
            # 可见性检测
            is_visible = self._check_visibility(bounds)
            
            # 最小化检测
            is_minimized = self._check_minimized()
            
            # 前台检测
            is_foreground = self._check_foreground()
            
            # 多显示器检测
            display_index = self._get_display_index(bounds)
            
            # 遮挡检测
            occlusion = self._calculate_occlusion(bounds)
            
            # 窗口层级
            z_order = self._get_z_order()
            
            state = WindowState(
                is_visible=is_visible,
                is_minimized=is_minimized,
                is_foreground=is_foreground,
                bounds=bounds,
                display_index=display_index,
                z_order=z_order,
                last_active=datetime.now(),
                occlusion_ratio=occlusion
            )
            
            # 保存历史
            self.state_history.append(state)
            if len(self.state_history) > self.max_history:
                self.state_history.pop(0)
                
            return state
            
        except Exception as e:
            self.logger.error(f"获取窗口状态失败: {e}")
            return None
            
    def _check_visibility(self, bounds: Dict) -> bool:
        """检查窗口是否可见"""
        # 检查窗口是否完全在屏幕外
        for display in self.displays:
            # 检查是否与任何显示器有交集
            if self._rects_intersect(bounds, display):
                return True
        return False
        
    def _rects_intersect(self, rect1: Dict, rect2: Dict) -> bool:
        """检查两个矩形是否相交"""
        return not (
            rect1['X'] + rect1['Width'] < rect2['left'] or
            rect1['X'] > rect2['right'] or
            rect1['Y'] + rect1['Height'] < rect2['top'] or
            rect1['Y'] > rect2['bottom']
        )
        
    def _check_minimized(self) -> bool:
        """检查窗口是否最小化"""
        if self.platform == "windows":
            try:
                import win32gui
                import win32con
                hwnd = self.wm.get_hwnd()
                if hwnd:
                    placement = win32gui.GetWindowPlacement(hwnd)
                    return placement[1] == win32con.SW_SHOWMINIMIZED
            except Exception as e:
                self.logger.warning(f"检查最小化状态失败: {e}")
                
        elif self.platform == "darwin":
            try:
                subprocess = self.wm.dep_manager.get_dependency("subprocess")
                if not subprocess:
                    return False
                
                # 使用AppleScript检查窗口最小化状态
                check_minimized_script = '''
                tell application "System Events"
                    tell process "WeChat"
                        set theWindows to every window
                        repeat with w in theWindows
                            if miniaturized of w is true then
                                return "MINIMIZED"
                            end if
                        end repeat
                        return "NOT_MINIMIZED"
                    end tell
                end tell
                '''
                
                result = subprocess.run(["osascript", "-e", check_minimized_script], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    return result.stdout.strip() == "MINIMIZED"
                else:
                    # 尝试中文进程名
                    check_minimized_script = '''
                    tell application "System Events"
                        tell process "微信"
                            set theWindows to every window
                            repeat with w in theWindows
                                if miniaturized of w is true then
                                    return "MINIMIZED"
                                end if
                            end repeat
                            return "NOT_MINIMIZED"
                        end tell
                    end tell
                    '''
                    result = subprocess.run(["osascript", "-e", check_minimized_script], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        return result.stdout.strip() == "MINIMIZED"
                
            except Exception as e:
                self.logger.warning(f"检查最小化状态失败: {e}")
                
        return False
        
    def _check_foreground(self) -> bool:
        """检查窗口是否在前台"""
        if self.platform == "windows":
            try:
                import win32gui
                foreground_hwnd = win32gui.GetForegroundWindow()
                wechat_hwnd = self.wm.get_hwnd()
                return foreground_hwnd == wechat_hwnd
            except:
                pass
        return False
        
    def _get_display_index(self, bounds: Dict) -> int:
        """获取窗口所在显示器索引"""
        window_center_x = bounds['X'] + bounds['Width'] // 2
        window_center_y = bounds['Y'] + bounds['Height'] // 2
        
        for display in self.displays:
            if (display['left'] <= window_center_x <= display['right'] and
                display['top'] <= window_center_y <= display['bottom']):
                return display['index']
        return 0  # 默认主显示器
        
    def _calculate_occlusion(self, bounds: Dict) -> float:
        """计算窗口被遮挡的比例"""
        if self.platform == "windows":
            try:
                import win32gui
                
                hwnd = self.wm.get_hwnd()
                if not hwnd:
                    return 0.0
                    
                # 获取窗口区域
                window_rect = (bounds['X'], bounds['Y'], 
                              bounds['X'] + bounds['Width'],
                              bounds['Y'] + bounds['Height'])
                
                # 枚举所有窗口，检查覆盖情况
                covered_area = 0
                
                def enum_callback(hwnd_extra, extra):
                    nonlocal covered_area
                    if not win32gui.IsWindowVisible(hwnd_extra):
                        return True
                    if hwnd_extra == hwnd:
                        return True
                        
                    # 获取覆盖窗口的矩形
                    rect = win32gui.GetWindowRect(hwnd_extra)
                    # 计算交集面积
                    intersect = self._rect_intersection_area(window_rect, rect)
                    covered_area += intersect
                    return True
                    
                win32gui.EnumWindows(enum_callback, None)
                
                total_area = bounds['Width'] * bounds['Height']
                return min(covered_area / total_area, 1.0) if total_area > 0 else 0.0
                
            except Exception as e:
                self.logger.warning(f"计算遮挡比例失败: {e}")
                
        return 0.0
        
    def _rect_intersection_area(self, rect1: Tuple, rect2: Tuple) -> int:
        """计算两个矩形交集面积"""
        x1 = max(rect1[0], rect2[0])
        y1 = max(rect1[1], rect2[1])
        x2 = min(rect1[2], rect2[2])
        y2 = min(rect1[3], rect2[3])
        
        if x2 <= x1 or y2 <= y1:
            return 0
            
        return (x2 - x1) * (y2 - y1)
        
    def _get_z_order(self) -> int:
        """获取窗口Z序"""
        if self.platform == "windows":
            try:
                import win32gui
                hwnd = self.wm.get_hwnd()
                if hwnd:
                    return win32gui.GetWindow(hwnd, win32con.GW_HWNDPREV)
            except:
                pass
        return 0
        
    async def ensure_window_ready(self, require_foreground: bool = True,
                                   max_wait: float = 30.0) -> bool:
        """确保窗口处于可用状态"""
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            state = self.get_current_state()
            
            if not state:
                self.logger.warning("无法获取窗口状态")
                await asyncio.sleep(0.5)
                continue
                
            # 检查各项状态
            issues = []
            
            if state.is_minimized:
                issues.append("窗口最小化")
                self._restore_window()
                
            if not state.is_visible:
                issues.append("窗口不可见")
                self.wm.bring_to_front()
                
            if state.occlusion_ratio > 0.5:
                issues.append(f"窗口被遮挡 {state.occlusion_ratio:.0%}")
                self.wm.bring_to_front()
                
            if require_foreground and not state.is_foreground:
                issues.append("窗口不在前台")
                self.wm.bring_to_front()
                
            if not issues:
                self.logger.info("窗口状态就绪")
                return True
                
            self.logger.info(f"窗口状态问题: {', '.join(issues)}，等待恢复...")
            await asyncio.sleep(0.5)
            
        self.logger.error(f"等待窗口就绪超时 ({max_wait}s)")
        return False
        
    def _restore_window(self):
        """从最小化恢复窗口"""
        if self.platform == "windows":
            try:
                import win32gui
                import win32con
                hwnd = self.wm.get_hwnd()
                if hwnd:
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            except Exception as e:
                self.logger.error(f"恢复窗口失败: {e}")
                
        elif self.platform == "darwin":
            try:
                subprocess = self.wm.dep_manager.get_dependency("subprocess")
                if not subprocess:
                    return
                
                # 使用AppleScript恢复最小化的窗口
                restore_script = '''
                tell application "System Events"
                    tell process "WeChat"
                        set theWindows to every window
                        repeat with w in theWindows
                            if miniaturized of w is true then
                                set miniaturized of w to false
                                set visible of w to true
                            end if
                        end repeat
                    end tell
                end tell
                '''
                
                result = subprocess.run(["osascript", "-e", restore_script], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    self.logger.info("成功恢复最小化的WeChat窗口")
                else:
                    # 尝试中文进程名
                    restore_script = '''
                    tell application "System Events"
                        tell process "微信"
                            set theWindows to every window
                            repeat with w in theWindows
                                if miniaturized of w is true then
                                    set miniaturized of w to false
                                    set visible of w to true
                                end if
                            end repeat
                        end tell
                    end tell
                    '''
                    result = subprocess.run(["osascript", "-e", restore_script], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        self.logger.info("成功恢复最小化的WeChat(微信)窗口")
                    else:
                        self.logger.warning(f"恢复最小化窗口失败: {result.stderr}")
                
            except Exception as e:
                self.logger.error(f"恢复最小化窗口失败: {e}")
                
    def get_state_summary(self) -> Dict:
        """获取状态摘要"""
        if not self.state_history:
            return {"message": "No state history"}
            
        recent = self.state_history[-10:]  # 最近10次
        
        return {
            'current_display': self.displays[0] if self.displays else None,
            'all_displays': len(self.displays),
            'recent_states': [
                {
                    'visible': s.is_visible,
                    'minimized': s.is_minimized,
                    'foreground': s.is_foreground,
                    'occlusion': f"{s.occlusion_ratio:.0%}",
                    'display': s.display_index
                }
                for s in recent
            ]
        }
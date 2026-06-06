#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Improved Search Bar Locator
专门解决搜索框定位问题的增强模块
"""

import logging
import time
from typing import Optional, Tuple, Dict, List, Any
from dataclasses import dataclass
from enum import Enum

from automation.adaptive_ocr import AdaptiveOCR
from mcp_core.window_manager import WindowManager

try:
    from shared.computer_use import (
        ComputerUseAgentAdapter,
        ComputerUseContextBuilder,
        ComputerUseFallbackPromptBuilder,
        ComputerUseGroundingInterpreter,
    )
except ImportError:
    try:
        from dataproai.src.servers.shared.computer_use import (
            ComputerUseAgentAdapter,
            ComputerUseContextBuilder,
            ComputerUseFallbackPromptBuilder,
            ComputerUseGroundingInterpreter,
        )
    except ImportError:
        ComputerUseAgentAdapter = None
        ComputerUseContextBuilder = None
        ComputerUseFallbackPromptBuilder = None
        ComputerUseGroundingInterpreter = None


class SearchStrategy(Enum):
    """搜索策略类型"""
    TEMPLATE_MATCHING = "template_matching"
    OCR_SEMANTIC = "ocr_semantic"
    HEURISTIC_POSITION = "heuristic_position"
    HYBRID = "hybrid"
    LLM_VISION = "llm_vision"


@dataclass
class SearchBarResult:
    """搜索框定位结果"""
    x: int
    y: int
    strategy: SearchStrategy
    confidence: float
    metadata: Dict[str, Any]


class ImprovedSearchBarLocator:
    """改进的搜索框定位器"""
    
    def __init__(self, adaptive_ocr: AdaptiveOCR, window_manager: WindowManager, ocr_enabled: bool):
        self.adaptive_ocr = adaptive_ocr
        self.window_manager = window_manager
        self.logger = logging.getLogger("improved_search_bar_locator")
        self.ocr_enabled = ocr_enabled
        
        # 搜索框特征词（用于 OCR 识别）
        self.search_indicators = [
            # 中文搜索词
            "搜索",
            # 英文搜索词
            "Search", "search",
            # 图标和符号
            "🔍", "🔎"
        ]

    def _get_last_screenshot_info(self, llm_client):
        if llm_client and hasattr(llm_client, "get_last_screenshot_info"):
            return llm_client.get_last_screenshot_info()
        return None

    def _restore_llm_point_to_original_screenshot(
        self,
        x: Optional[float],
        y: Optional[float],
        llm_client,
    ) -> Tuple[Optional[float], Optional[float]]:
        """Undo screenshot compression before adding window offsets."""
        screenshot_info = self._get_last_screenshot_info(llm_client)
        if (
            x is None
            or y is None
            or screenshot_info is None
            or not getattr(screenshot_info, "was_compressed", False)
        ):
            return x, y

        scale_x = float(getattr(screenshot_info, "scale_x", 1.0) or 1.0)
        scale_y = float(getattr(screenshot_info, "scale_y", 1.0) or 1.0)
        if scale_x <= 0 or scale_y <= 0:
            return x, y

        restored_x = float(x) / scale_x
        restored_y = float(y) / scale_y
        self.logger.info(
            "恢复搜索框定位坐标: (%s, %s) -> (%s, %s), 比例 X=%.3f, Y=%.3f",
            x,
            y,
            int(round(restored_x)),
            int(round(restored_y)),
            scale_x,
            scale_y,
        )
        return restored_x, restored_y
    
    async def locate_search_bar(self, bounds: Dict[str, float], llm_client=None) -> Optional[SearchBarResult]:
        """
        统一的搜索框定位逻辑 - 使用 OCR + LLM

        Args:
            bounds: 窗口边界信息 {'X': x, 'Y': y, 'Width': w, 'Height': h}
            llm_client: LLM 客户端（可选）

        Returns:
            SearchBarResult 或 None
        """
        import time

        self.logger.info("开始使用统一的 OCR+LLM 搜索框定位器")
        start_time = time.time()
        total_timeout = 30.0  # 30秒总超时

        try:
            # 策略1: OCR 文本识别搜索
            if self.ocr_enabled and time.time() - start_time < total_timeout:
                ocr_result = await self._ocr_based_search(bounds)
                if ocr_result:
                    self.logger.info(f"OCR 搜索成功: {ocr_result}")
                    return ocr_result

            # 策略2: LLM 视觉分析（如果可用）
            if llm_client and time.time() - start_time < total_timeout:
                llm_result = await self._llm_based_search(bounds, llm_client)
                if llm_result:
                    self.logger.info(f"LLM 搜索成功: {llm_result}")
                    return llm_result

            # 策略4: 启发式估算 (最后手段)
            if time.time() - start_time < total_timeout:
                self.logger.warning("尝试启发式估算搜索框位置 (最后手段)")
                heuristic_result = self._heuristic_search(bounds)
                if heuristic_result:
                    return heuristic_result

            elapsed = time.time() - start_time
            self.logger.error(f"所有搜索策略都失败了，耗时: {elapsed:.2f}s")
            return None

        except Exception as e:
            elapsed = time.time() - start_time
            self.logger.error(f"搜索框定位异常: {e}，耗时: {elapsed:.2f}s")
            return None

    def _heuristic_search(self, bounds: Dict[str, float]) -> Optional[SearchBarResult]:
        """基于已知 UI 布局的启发式估算"""
        # 估算位置：窗口中心偏移或左侧顶部
        # 微信 Mac 版搜索框通常在侧边栏顶部
        click_x = bounds['X'] + bounds['Width'] * 0.2
        click_y = bounds['Y'] + 40  # 顶部标题栏下方
        
        # 检查是否在合理范围内
        if self._is_position_valid(click_x, click_y, bounds):
            return SearchBarResult(
                x=int(click_x),
                y=int(click_y),
                strategy=SearchStrategy.HEURISTIC_POSITION,
                confidence=30,  # 较低置信度
                metadata={'method': 'heuristic'}
            )
        return None

    async def _ocr_based_search(self, bounds: Dict[str, float]) -> Optional[SearchBarResult]:
        """基于 OCR 的搜索框定位"""
        self.logger.debug("执行 OCR 文本识别搜索")

        try:
            # 捕获窗口截图
            screenshot = self._capture_window_screenshot(bounds)
            if not screenshot:
                self.logger.warning("无法捕获窗口截图")
                return None

            # 使用 AdaptiveOCR 识别文本
            ocr_results = self.adaptive_ocr.recognize(screenshot)

            # 查找搜索框相关关键词
            search_keywords = ["搜索", "Search", "搜索框", "Search bar", "🔍", "🔎"]

            best_result = None
            best_confidence = 0

            for result in ocr_results:
                text = result.get('text', '')
                confidence = result.get('confidence', 0)

                # 检查是否包含搜索关键词
                for keyword in search_keywords:
                    if keyword.lower() in text.lower():
                        if confidence > best_confidence:
                            best_confidence = confidence
                            best_result = result
                            self.logger.debug(f"找到搜索关键词 '{keyword}': {text} (置信度: {confidence})")
                            break

            if best_result and best_confidence >= 60:  # 置信度阈值
                # 计算相对于窗口的坐标
                local_x = best_result.get('left', 0) + best_result.get('width', 0) // 2
                local_y = best_result.get('top', 0) + best_result.get('height', 0) // 2
                
                # 累加窗口偏移，转换为屏幕绝对坐标
                click_x = bounds['X'] + local_x
                click_y = bounds['Y'] + local_y

                # 验证位置是否在窗口边界内
                if self._is_position_valid(click_x, click_y, bounds):
                    result = SearchBarResult(
                        x=int(click_x),
                        y=int(click_y),
                        strategy=SearchStrategy.OCR_SEMANTIC,
                        confidence=best_confidence,
                        metadata={
                            'method': 'ocr',
                            'matched_text': best_result.get('text', ''),
                            'ocr_result': best_result
                        }
                    )

                    # 验证搜索框是否激活
                    if await self._verify_search_bar_activation(result, bounds):
                        return result
                    else:
                        self.logger.debug(f"OCR 找到位置但未激活搜索框: ({click_x}, {click_y})")

            return None

        except Exception as e:
            self.logger.error(f"OCR 搜索失败: {e}")
            return None

    async def _llm_based_search(self, bounds: Dict[str, float], llm_client) -> Optional[SearchBarResult]:
        """基于 LLM 的搜索框定位"""
        self.logger.debug("执行 LLM 视觉分析搜索")

        try:
            # 捕获窗口截图
            screenshot = self._capture_window_screenshot(bounds)
            if not screenshot:
                return None

            # 将截图发送给 LLM 进行分析
            prompt = (
                ComputerUseFallbackPromptBuilder.build_wechat_search_bar_prompt()
                if ComputerUseFallbackPromptBuilder
                else "请分析这张截图，找到微信的搜索框位置。"
            )

            # 调用 LLM 分析 - 使用 MCPBasedLLMClient
            try:
                import base64
                from io import BytesIO

                # 将截图转换为 base64
                buffered = BytesIO()
                screenshot.save(buffered, format="PNG")
                screenshot_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

                self.logger.info("调用 LLM 分析截图定位搜索框")

                if hasattr(llm_client, "computer_use_grounding"):
                    window_size = {
                        "width": getattr(screenshot, "width", 0),
                        "height": getattr(screenshot, "height", 0),
                    }
                    if ComputerUseAgentAdapter:
                        request_kwargs = ComputerUseAgentAdapter.for_wechat_search_bar(
                            window_bounds=bounds,
                            screenshot_size=window_size,
                        ).to_kwargs(screenshot_b64=screenshot_b64)
                    elif ComputerUseContextBuilder:
                        request_kwargs = {
                            "target": "微信搜索框",
                            "screenshot_b64": screenshot_b64,
                            "ui_context": ComputerUseContextBuilder.build_wechat_search_bar_context(
                                window_bounds=bounds,
                                screenshot_size=window_size,
                            ),
                        }
                    else:
                        request_kwargs = {
                            "target": "微信搜索框",
                            "screenshot_b64": screenshot_b64,
                            "ui_context": {
                                "app": "WeChat",
                                "mode": "search_bar_locator",
                                "coordinate_space": "window_screenshot",
                                "window_bounds": dict(bounds),
                                "screenshot_size": window_size,
                            },
                        }
                    llm_response = await llm_client.computer_use_grounding(**request_kwargs)
                else:
                    if hasattr(llm_client, "legacy_visual_fallback"):
                        llm_response = await llm_client.legacy_visual_fallback(
                            prompt,
                            screenshot_b64,
                        )
                    else:
                        llm_response = await llm_client.analyze_screenshot(
                            prompt,
                            screenshot_b64,
                        )

                if llm_response:
                    self.logger.info(f"LLM 响应: {llm_response}")

                    # 解析 LLM 响应
                    if isinstance(llm_response, dict):
                        x, y = self._extract_llm_point(llm_response)
                        x, y = self._restore_llm_point_to_original_screenshot(
                            x,
                            y,
                            llm_client,
                        )
                        confidence = self._coerce_confidence_percent(
                            llm_response.get('confidence', 0)
                        )

                        if x is not None and y is not None:
                            result = SearchBarResult(
                                x=int(x),
                                y=int(y),
                                strategy=SearchStrategy.LLM_VISION,
                                confidence=confidence,
                                metadata={
                                    'method': 'computer_use_grounding'
                                    if 'point' in llm_response or 'bbox' in llm_response
                                    else 'llm',
                                    'reason': llm_response.get('reason', '') or llm_response.get('description', ''),
                                    'llm_response': llm_response
                                }
                            )

                            # 转换并验证位置（LLM 返回的是相对于截图的坐标，需要加上 bounds 偏移）
                            abs_x = bounds['X'] + result.x
                            abs_y = bounds['Y'] + result.y
                            
                            if self._is_position_valid(abs_x, abs_y, bounds):
                                result.x = int(abs_x)
                                result.y = int(abs_y)
                                return result

                return None

            except Exception as e:
                self.logger.error(f"LLM 调用失败: {e}")
                return None

        except Exception as e:
            self.logger.error(f"LLM 搜索失败: {e}")
            return None

    def _extract_llm_point(self, llm_response: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
        """兼容 legacy_visual_fallback 与 computer_use_grounding 返回格式。"""
        if ComputerUseGroundingInterpreter:
            return ComputerUseGroundingInterpreter.extract_point(llm_response)
        x = llm_response.get('x')
        y = llm_response.get('y')
        point = llm_response.get('point') or {}
        bbox = llm_response.get('bbox') or {}
        if x is None:
            x = point.get('x')
        if y is None:
            y = point.get('y')
        if x is None and bbox:
            x = bbox.get('x', 0) + bbox.get('width', 0) / 2
        if y is None and bbox:
            y = bbox.get('y', 0) + bbox.get('height', 0) / 2
        return x, y

    def _coerce_confidence_percent(self, value: Any) -> float:
        if ComputerUseGroundingInterpreter:
            return ComputerUseGroundingInterpreter.coerce_confidence_percent(value)
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.0
        if confidence <= 1.0:
            confidence *= 100.0
        return max(0.0, min(confidence, 100.0))

    async def _hybrid_llm_ocr_search(self, bounds: Dict[str, float], llm_client) -> Optional[SearchBarResult]:
        """混合 OCR + LLM 协同搜索"""
        self.logger.debug("执行混合 LLM+OCR 搜索")

        try:
            # 步骤1: 使用 OCR 快速扫描，获取候选位置
            screenshot = self._capture_window_screenshot(bounds)
            if not screenshot:
                return None

            # OCR 识别所有文本
            ocr_results = self.adaptive_ocr.recognize(screenshot)

            # 步骤2: 收集搜索相关候选位置
            candidates = []
            search_keywords = ["搜索", "Search", "搜索框", "🔍"]

            for result in ocr_results:
                text = result.get('text', '')
                for keyword in search_keywords:
                    if keyword.lower() in text.lower():
                        center_x = result.get('left', 0) + result.get('width', 0) // 2
                        center_y = result.get('top', 0) + result.get('height', 0) // 2

                        if self._is_position_valid(center_x, center_y, bounds):
                            candidates.append({
                                'x': center_x,
                                'y': center_y,
                                'text': text,
                                'confidence': result.get('confidence', 0),
                                'ocr_result': result
                            })
                            break

            if not candidates:
                return None

            # 步骤3: 使用 LLM 选择最佳候选位置（如果可用）
            if candidates:
                # 简单策略：选择置信度最高的
                best_candidate = max(candidates, key=lambda c: c['confidence'])

                result = SearchBarResult(
                    x=int(best_candidate['x']),
                    y=int(best_candidate['y']),
                    strategy=SearchStrategy.HYBRID,
                    confidence=best_candidate['confidence'],
                    metadata={
                        'method': 'hybrid',
                        'matched_text': best_candidate['text'],
                        'candidates_count': len(candidates)
                    }
                )

                if await self._verify_search_bar_activation(result, bounds):
                    return result

            return None

        except Exception as e:
            self.logger.error(f"混合搜索失败: {e}")
            return None
    
    def _capture_window_screenshot(self, bounds: Dict[str, float]):
        """捕获窗口截图"""
        try:
            # 使用现有的OCR处理器捕获截图
            if hasattr(self.adaptive_ocr, 'ocr') and hasattr(self.adaptive_ocr.ocr, 'capture_screenshot'):
                screenshot = self.adaptive_ocr.ocr.capture_screenshot((bounds['X'], bounds['Y'], bounds['Width'], bounds['Height']))
                if screenshot is None:
                    self.logger.error("窗口截图捕获失败，返回空结果")
                    return None
                # 检查PIL Image对象是否有效
                if not hasattr(screenshot, 'size') or not hasattr(screenshot, 'width') or not hasattr(screenshot, 'height'):
                    self.logger.error(f"截图类型错误，期望PIL Image对象，实际为{type(screenshot)}")
                    return None
                if screenshot.size == 0 or screenshot.width == 0 or screenshot.height == 0:
                    self.logger.error("捕获的窗口截图为空图像")
                    return None
                return screenshot
            else:
                self.logger.error("OCR处理器不支持截图功能")
                return None
        except Exception as e:
            self.logger.error(f"捕获窗口截图失败: {e}")
            return None
    
    def _capture_region_screenshot(self, region: Tuple[int, int, int, int]):
        """捕获区域截图"""
        try:
            if hasattr(self.adaptive_ocr, 'ocr') and hasattr(self.adaptive_ocr.ocr, 'capture_screenshot'):
                screenshot = self.adaptive_ocr.ocr.capture_screenshot(region)
                if screenshot is None:
                    self.logger.error("区域截图捕获失败，返回空结果")
                    return None
                # 检查PIL Image对象是否有效
                if not hasattr(screenshot, 'size') or not hasattr(screenshot, 'width') or not hasattr(screenshot, 'height'):
                    self.logger.error(f"截图类型错误，期望PIL Image对象，实际为{type(screenshot)}")
                    return None
                if screenshot.size == 0 or screenshot.width == 0 or screenshot.height == 0:
                    self.logger.error("捕获的区域截图为空图像")
                    return None
                return screenshot
            else:
                self.logger.error("OCR处理器不支持截图功能")
                return None
        except Exception as e:
            self.logger.error(f"捕获区域截图失败: {e}")
            return None
    
    def _is_position_valid(self, x: float, y: float, bounds: Dict[str, float]) -> bool:
        """验证位置是否在边界内"""
        return (
            bounds['X'] <= x <= bounds['X'] + bounds['Width'] and
            bounds['Y'] <= y <= bounds['Y'] + bounds['Height']
        )
    
    def _calculate_search_region(self, center_x: float, center_y: float, bounds: Dict[str, float]) -> Tuple[int, int, int, int]:
        """计算搜索区域"""
        # 以中心点为中心的搜索区域
        search_width = 200
        search_height = 100
        
        x = max(bounds['X'], center_x - search_width // 2)
        y = max(bounds['Y'], center_y - search_height // 2)
        
        # 确保区域不超出边界
        width = min(search_width, bounds['X'] + bounds['Width'] - x)
        height = min(search_height, bounds['Y'] + bounds['Height'] - y)
        
        return (int(x), int(y), int(width), int(height))
    
    def _simulate_click(self, x: float, y: float) -> bool:
        """模拟点击"""
        try:
            # 这里应该调用实际的点击方法
            # 由于我们没有GUI自动化实例，这里返回True作为占位符
            self.logger.debug(f"模拟点击位置: ({x}, {y})")
            return True
        except Exception as e:
            self.logger.error(f"模拟点击失败: {e}")
            return False
    
    async def _verify_search_bar_activation(self, result: SearchBarResult, bounds: Dict[str, float]) -> bool:
        """验证搜索框是否激活"""
        try:
            # 点击该位置
            click_success = self._simulate_click(result.x, result.y)
            if not click_success:
                return False
            
            time.sleep(0.5)
            
            # 验证搜索框是否激活（通过检查是否有光标或焦点指示器）
            verification_region = (
                result.x - 100,
                result.y - 20,
                200,
                60
            )
            
            region_screenshot = self._capture_region_screenshot(verification_region)
            if region_screenshot is None:
                return False
            
            # 查找搜索指示器
            search_indicators = ["搜索", "Search", "🔍", "输入", "Input"]
            for indicator in search_indicators:
                ocr_results = self.adaptive_ocr.find_text(region_screenshot, indicator, fuzzy_match=True)
                if ocr_results:
                    self.logger.debug(f"验证成功: 找到 '{indicator}' 在位置 ({result.x}, {result.y})")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"验证搜索框激活失败: {e}")
            return False

"""
LLM Element Locator

Uses LLM to locate UI elements in screenshots.
坐标缩放使用共享的 ScreenshotOptimizer 确保一致性。
"""
import logging
from typing import Optional, Tuple, Dict, Any, Union

from automation.screenshot_optimizer import ScreenshotOptimizer, ScreenshotInfo

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


class LLMElementLocator:
    """Locate UI elements using LLM vision capabilities"""

    def __init__(self, llm_client, llm_enabled: bool, logger: logging.Logger):
        """
        Initialize LLM element locator

        Args:
            llm_client: LLM client instance (should have get_last_screenshot_info method)
            llm_enabled: Whether LLM is enabled
            logger: Logger instance
        """
        self.llm_client = llm_client
        self.llm_enabled = llm_enabled
        self.logger = logger
        self._screenshot_helper = None

    def set_screenshot_helper(self, screenshot_helper):
        """Set screenshot helper instance"""
        self._screenshot_helper = screenshot_helper

    def _get_screenshot_dims(self, screenshot) -> Tuple[int, int]:
        """Get screenshot dimensions"""
        if hasattr(screenshot, 'size'):
            return screenshot.size  # PIL Image: (width, height)
        elif hasattr(screenshot, 'width') and hasattr(screenshot, 'height'):
            return (screenshot.width, screenshot.height)
        else:
            return (0, 0)

    def _get_screenshot_info_from_llm(self) -> Optional[ScreenshotInfo]:
        """
        从 LLM 客户端获取截图信息
        
        LLM 客户端在处理截图时会保存截图信息，包含缩放比例
        """
        if self.llm_client and hasattr(self.llm_client, 'get_last_screenshot_info'):
            return self.llm_client.get_last_screenshot_info()
        return None

    def _detect_screen_scale(self, screenshot_width: int) -> float:
        """
        检测屏幕缩放因子（Retina 显示器通常为 2.0）
        
        pyautogui.screenshot() 返回物理像素分辨率，
        但 pyautogui.click() 和窗口边界使用逻辑坐标。
        
        Args:
            screenshot_width: 截图的物理像素宽度
            
        Returns:
            缩放因子（1.0 表示无缩放，2.0 表示 Retina 2x）
        """
        try:
            import pyautogui as _pag
            logical_width, _ = _pag.size()
            if logical_width > 0:
                scale = screenshot_width / logical_width
                # 只接受合理的缩放因子（1.0, 1.5, 2.0, 3.0 等）
                if 0.8 <= scale <= 4.0:
                    return scale
                else:
                    self.logger.warning(f"检测到异常缩放因子: {scale}，使用默认值 1.0")
                    return 1.0
            return 1.0
        except Exception as e:
            self.logger.warning(f"无法检测屏幕缩放因子: {e}，使用默认值 1.0")
            return 1.0

    def _supports_computer_use_grounding(self) -> bool:
        return bool(
            self.llm_client and hasattr(self.llm_client, "computer_use_grounding")
        )

    def _supports_legacy_visual_fallback(self) -> bool:
        return bool(
            self.llm_client and hasattr(self.llm_client, "legacy_visual_fallback")
        )

    def _build_grounding_context(
        self,
        *,
        target: str,
        mode: str,
        region: Optional[Dict[str, Any]] = None,
        original_region: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if ComputerUseContextBuilder:
            if mode == "locate_element":
                return ComputerUseContextBuilder.build_wechat_locate_context(target)
            if mode == "find_element_by_name":
                return ComputerUseContextBuilder.build_wechat_region_context(
                    target,
                    region=region or {},
                    original_region=original_region,
                )
        context = {
            "app": "WeChat",
            "mode": mode,
            "target": target,
        }
        if mode == "locate_element":
            context["coordinate_space"] = "full_screenshot"
        elif mode == "find_element_by_name":
            context["coordinate_space"] = "cropped_region"
            if original_region:
                context["original_region"] = original_region
        if region:
            context["region"] = region
        return context

    def _build_grounding_call(
        self,
        *,
        screenshot_b64: str,
        target: str,
        mode: str,
        region: Optional[Dict[str, Any]] = None,
        original_region: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if ComputerUseAgentAdapter:
            if mode == "locate_element":
                profile = ComputerUseAgentAdapter.for_wechat_locate(target)
                return profile.to_kwargs(screenshot_b64=screenshot_b64)
            if mode == "find_element_by_name":
                logical_region = dict(region or {})
                profile = ComputerUseAgentAdapter.for_wechat_region(
                    target,
                    region=logical_region,
                    original_region=original_region,
                )
                return profile.to_kwargs(
                    screenshot_b64=screenshot_b64,
                    region=logical_region,
                )

        payload: Dict[str, Any] = {
            "target": target,
            "screenshot_b64": screenshot_b64,
            "ui_context": self._build_grounding_context(
                target=target,
                mode=mode,
                region=region,
                original_region=original_region,
            ),
        }
        if region:
            payload["region"] = region
        return payload

    def _normalise_grounding_result(
        self,
        result: Optional[Dict[str, Any]],
        *,
        description: str,
        match_text: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if ComputerUseGroundingInterpreter:
            return ComputerUseGroundingInterpreter.to_legacy_locator_payload(
                result,
                description=description,
                match_text=match_text,
            )
        if result is None or not isinstance(result, dict):
            return result
        if "center_x" in result or "center_y" in result:
            return result

        point = result.get("point") or {}
        bbox = result.get("bbox") or {}
        x = point.get("x")
        y = point.get("y")
        if x is None and bbox:
            x = bbox.get("x", 0) + bbox.get("width", 1) / 2
        if y is None and bbox:
            y = bbox.get("y", 0) + bbox.get("height", 1) / 2

        if x is None or y is None:
            return {
                **result,
                "found": False,
                "description": str(result.get("description") or description),
            }

        return {
            **result,
            "found": bool(result.get("found", True)),
            "center_x": int(round(float(x))),
            "center_y": int(round(float(y))),
            "confidence": float(result.get("confidence", 0.0) or 0.0),
            "description": str(result.get("description") or description),
            "match_text": result.get("match_text") or match_text or description,
        }

    async def locate_element(self, screenshot, element_type: str) -> Optional[Tuple[int, int]]:
        """
        Locate Element position by type

        Args:
            screenshot: Screenshot image (PIL Image) - 全屏截图
            element_type: Element type (e.g., "搜索框")

        Returns:
            Element center coordinates (x, y) or None - 屏幕逻辑坐标（可直接用于 pyautogui.click）
        """
        if not self._check_llm_available():
            return None

        try:
            # Get original screenshot dimensions before any processing
            original_dims = self._get_screenshot_dims(screenshot)
            self.logger.debug(f"原始截图尺寸: {original_dims}")

            # 检测屏幕缩放因子
            screen_scale = self._detect_screen_scale(original_dims[0])
            self.logger.info(f"屏幕缩放因子: {screen_scale}")

            screenshot_b64 = self._screenshot_helper.screenshot_to_base64(screenshot)
            if not screenshot_b64:
                self.logger.error("截图转换失败")
                return None

            if self._supports_computer_use_grounding():
                self.logger.info(f"使用 computer_use_grounding 定位元素: {element_type}")
                result = await self.llm_client.computer_use_grounding(
                    **self._build_grounding_call(
                        screenshot_b64=screenshot_b64,
                        target=element_type,
                        mode="locate_element",
                    )
                )
                result = self._normalise_grounding_result(
                    result,
                    description=f"Element '{element_type}' grounded by computer_use",
                )
            else:
                prompt = self._build_locate_prompt(element_type)
                self.logger.info(f"使用 LLM 定位元素: {element_type}")
                if self._supports_legacy_visual_fallback():
                    result = await self.llm_client.legacy_visual_fallback(
                        prompt,
                        screenshot_b64,
                    )
                else:
                    result = await self.llm_client.analyze_screenshot(
                        prompt,
                        screenshot_b64,
                    )

            # 从 LLM 客户端获取截图信息（包含缩放比例）
            screenshot_info = self._get_screenshot_info_from_llm()
            
            if screenshot_info:
                self.logger.debug(
                    f"截图信息: 原始 {screenshot_info.original_width}x{screenshot_info.original_height}, "
                    f"压缩 {screenshot_info.compressed_width}x{screenshot_info.compressed_height}, "
                    f"缩放 X={screenshot_info.scale_x:.2f}, Y={screenshot_info.scale_y:.2f}"
                )
                
                # 使用截图信息进行坐标缩放（从压缩坐标转到原始截图物理坐标）
                scaled_result = self._scale_coordinates_with_info(result, screenshot_info)
            else:
                # 降级：使用旧的计算方式
                self.logger.warning("无法获取截图信息，使用降级方案")
                optimizer = ScreenshotOptimizer(logger=self.logger)
                compressed_dims = optimizer._calculate_compressed_dims(original_dims[0], original_dims[1])
                scaled_result = self._scale_coordinates_if_needed(result, original_dims, compressed_dims)
            
            # 解析坐标结果（此时坐标是物理像素坐标）
            coords = self._parse_coordinate_result(scaled_result, element_type)
            
            # 将物理像素坐标转换为逻辑坐标（用于 pyautogui.click）
            if coords and screen_scale > 1.0:
                logical_x = int(coords[0] / screen_scale)
                logical_y = int(coords[1] / screen_scale)
                self.logger.info(
                    f"Retina 坐标转换: 物理 ({coords[0]}, {coords[1]}) -> "
                    f"逻辑 ({logical_x}, {logical_y}), 缩放因子: {screen_scale}"
                )
                return (logical_x, logical_y)
            
            return coords

        except Exception as e:
            self.logger.error(f"LLM 定位元素失败: {e}", exc_info=True)
            return None

    async def find_element_by_name(
        self,
        screenshot,
        target_name: str,
        region: Dict[str, int],
        prompt: Optional[str] = None
    ) -> Optional[Tuple[int, int]]:
        """
        Find element by name in a specific region

        Args:
            screenshot: Screenshot image (PIL Image) - 全屏截图
            target_name: Target name to search for
            region: Search region {'X': x, 'Y': y, 'Width': w, 'Height': h} - 屏幕逻辑坐标
            prompt: Custom prompt (optional, will use default if not provided)

        Returns:
            Element center coordinates (x, y) or None - 屏幕逻辑坐标（可直接用于 pyautogui.click）
        """
        if not self._check_llm_available():
            return None

        try:
            # 从全屏截图中裁剪出 region 区域，只传递区域截图给 LLM
            # 这样可以提高定位精度，减少干扰
            from PIL import Image
            
            # 确保截图是 PIL Image
            if hasattr(screenshot, 'shape'):
                # numpy array, convert to PIL
                import numpy as np
                screenshot_pil = Image.fromarray(screenshot)
            elif hasattr(screenshot, 'crop'):
                # Already PIL Image
                screenshot_pil = screenshot
            else:
                self.logger.error(f"不支持的截图格式: {type(screenshot)}")
                return None
            
            # 检测屏幕缩放因子（macOS Retina 通常为 2.0）
            # pyautogui.screenshot() 返回物理像素分辨率，但 click/bounds 使用逻辑坐标
            full_width, full_height = screenshot_pil.size
            screen_scale = self._detect_screen_scale(full_width)
            self.logger.info(f"屏幕缩放因子: {screen_scale}, 截图物理尺寸: {full_width}x{full_height}")
            
            # 使用物理像素坐标裁剪 region 区域
            region_box = (
                int(region['X'] * screen_scale),
                int(region['Y'] * screen_scale),
                int((region['X'] + region['Width']) * screen_scale),
                int((region['Y'] + region['Height']) * screen_scale)
            )
            
            # 确保裁剪区域在截图范围内
            region_box = (
                max(0, region_box[0]),
                max(0, region_box[1]),
                min(full_width, region_box[2]),
                min(full_height, region_box[3])
            )
            
            region_screenshot = screenshot_pil.crop(region_box)
            self.logger.info(f"已裁剪搜索区域(物理): {region_box}, 物理尺寸: {region_screenshot.size}")
            
            # 将裁剪后的图片缩放回逻辑分辨率
            # 这样 LLM 返回的坐标直接就是逻辑坐标，可以直接加上 region 偏移用于点击
            if screen_scale > 1.0:
                logical_w = int(region_screenshot.size[0] / screen_scale)
                logical_h = int(region_screenshot.size[1] / screen_scale)
                region_screenshot = region_screenshot.resize(
                    (logical_w, logical_h), Image.Resampling.LANCZOS
                )
                self.logger.info(f"缩放至逻辑尺寸: {logical_w}x{logical_h}")
            
            # 转换区域截图为 base64
            screenshot_b64 = self._screenshot_helper.screenshot_to_base64(region_screenshot)
            if not screenshot_b64:
                self.logger.error("截图转换失败")
                return None

            # 使用改进的 prompt，针对裁剪后的区域（使用逻辑尺寸）
            analysis_prompt = prompt if prompt else self._build_find_prompt_improved(target_name, {
                'X': 0, 'Y': 0, 'Width': region_screenshot.size[0], 'Height': region_screenshot.size[1]
            })

            if self._supports_computer_use_grounding():
                self.logger.info(f"使用 computer_use_grounding 在区域内查找元素: {target_name}")
                logical_region = {
                    "X": 0,
                    "Y": 0,
                    "Width": region_screenshot.size[0],
                    "Height": region_screenshot.size[1],
                }
                result = await self.llm_client.computer_use_grounding(
                    **self._build_grounding_call(
                        screenshot_b64=screenshot_b64,
                        target=target_name,
                        mode="find_element_by_name",
                        region=logical_region,
                        original_region=region,
                    )
                )
                result = self._normalise_grounding_result(
                    result,
                    description=f"Target '{target_name}' grounded inside cropped region",
                    match_text=target_name,
                )
            else:
                self.logger.info(f"使用 LLM 在区域内查找元素: {target_name}")
                if self._supports_legacy_visual_fallback():
                    result = await self.llm_client.legacy_visual_fallback(
                        analysis_prompt,
                        screenshot_b64,
                    )
                else:
                    result = await self.llm_client.analyze_screenshot(
                        analysis_prompt,
                        screenshot_b64,
                    )

            # 从 LLM 客户端获取截图信息（包含缩放比例）
            screenshot_info = self._get_screenshot_info_from_llm()
            
            if screenshot_info:
                self.logger.debug(
                    f"截图信息: 原始 {screenshot_info.original_width}x{screenshot_info.original_height}, "
                    f"压缩 {screenshot_info.compressed_width}x{screenshot_info.compressed_height}, "
                    f"缩放 X={screenshot_info.scale_x:.2f}, Y={screenshot_info.scale_y:.2f}"
                )
                
                # 使用截图信息进行坐标缩放（从压缩坐标转到区域截图原始坐标）
                scaled_result = self._scale_coordinates_with_info(result, screenshot_info)
            else:
                # 降级：直接使用结果
                self.logger.warning("无法获取截图信息，使用原始结果")
                scaled_result = result

            # 解析结果，并将坐标转换为屏幕绝对坐标
            # 此时 scaled_result 中的坐标是逻辑坐标（相对于裁剪区域），
            # _parse_find_result_with_offset 会加上 region 的逻辑偏移
            return self._parse_find_result_with_offset(scaled_result, target_name, region)
        except Exception as e:
            self.logger.error(f"LLM 查找元素失败: {e}", exc_info=True)
            return None

    def _scale_coordinates_with_info(
        self,
        result: Optional[Dict[str, Any]],
        screenshot_info: ScreenshotInfo
    ) -> Optional[Dict[str, Any]]:
        """
        使用截图信息缩放坐标
        
        Args:
            result: LLM 响应结果
            screenshot_info: 截图信息
            
        Returns:
            缩放后的结果
        """
        if not result or not isinstance(result, dict):
            return result
        
        if not result.get('found', False):
            return result
        
        if not screenshot_info or not screenshot_info.was_compressed:
            self.logger.debug("截图未被压缩，无需缩放坐标")
            return result
        
        x = result.get('center_x')
        y = result.get('center_y')
        
        if x is not None and y is not None:
            # 从压缩坐标转到原始坐标（使用 scale_x 和 scale_y）
            # scale_x = compressed_width / original_width
            # 所以 original_x = compressed_x / scale_x
            scaled_x = int(x / screenshot_info.scale_x)
            scaled_y = int(y / screenshot_info.scale_y)
            
            self.logger.info(
                f"坐标缩放: ({x}, {y}) -> ({scaled_x}, {scaled_y}), "
                f"比例 X={screenshot_info.scale_x:.2f}, Y={screenshot_info.scale_y:.2f}"
            )
            
            return {
                **result,
                'center_x': scaled_x,
                'center_y': scaled_y,
                '_scaled': True,
                '_scale_factor_x': 1.0 / screenshot_info.scale_x,
                '_scale_factor_y': 1.0 / screenshot_info.scale_y
            }
        
        return result

    def _scale_coordinates_if_needed(
        self, 
        result: Optional[Dict[str, Any]], 
        original_dims: Tuple[int, int],
        compressed_dims: Tuple[int, int]
    ) -> Optional[Dict[str, Any]]:
        """
        降级方案：使用计算得到的压缩尺寸缩放坐标
        
        Args:
            result: LLM 响应结果
            original_dims: 原始尺寸
            compressed_dims: 压缩后尺寸
            
        Returns:
            缩放后的结果
        """
        if not result or not isinstance(result, dict):
            return result

        if not result.get('found', False):
            return result

        original_width, original_height = original_dims
        compressed_width, compressed_height = compressed_dims
        
        if original_width <= 0 or original_height <= 0:
            return result

        if compressed_width <= 0 or compressed_height <= 0:
            return result

        # Check if scaling is needed
        if original_width == compressed_width and original_height == compressed_height:
            return result

        # Calculate scale factors for width and height
        scale_x = original_width / compressed_width if compressed_width > 0 else 1.0
        scale_y = original_height / compressed_height if compressed_height > 0 else 1.0
        
        self.logger.debug(f"坐标缩放: 原始 {original_dims} -> 压缩 {compressed_dims}, 比例 X={scale_x:.2f}, Y={scale_y:.2f}")
        
        # Scale coordinates
        x = result.get('center_x')
        y = result.get('center_y')
        
        if x is not None and y is not None:
            scaled_x = int(x * scale_x)
            scaled_y = int(y * scale_y)
            
            self.logger.info(f"坐标缩放: ({x}, {y}) -> ({scaled_x}, {scaled_y}), 比例 X={scale_x:.2f}, Y={scale_y:.2f}")
            
            return {
                **result,
                'center_x': scaled_x,
                'center_y': scaled_y,
                '_scaled': True,
                '_scale_factor_x': scale_x,
                '_scale_factor_y': scale_y
            }
        
        return result

    def _check_llm_available(self) -> bool:
        """Check if LLM is available"""
        if not self.llm_enabled:
            self.logger.warning("LLM 未启用，无法使用 LLM 定位")
            return False
        if not self.llm_client:
            self.logger.warning("LLM 客户端不可用")
            return False
        if not self._screenshot_helper:
            self.logger.warning("截图辅助类未设置")
            return False
        return True

    def _build_locate_prompt(self, element_type: str) -> str:
        """Build prompt for locatingElement by type"""
        if ComputerUseFallbackPromptBuilder:
            return ComputerUseFallbackPromptBuilder.build_wechat_locate_prompt(
                element_type
            )
        return f'请分析截图，找出"{element_type}"的位置。'

    def _build_find_prompt(self, target_name: str, region: Dict[str, int]) -> str:
        """Build prompt for finding element by name in region"""
        if ComputerUseFallbackPromptBuilder:
            return ComputerUseFallbackPromptBuilder.build_wechat_region_prompt(
                target_name,
                region,
            )
        return f'请分析截图，在搜索结果区域中找"{target_name}"的元素。'

    def _build_find_prompt_improved(self, target_name: str, region: Dict[str, int]) -> str:
        """Build improved prompt for finding element by name in region
        
        这是改进版的 prompt，针对裁剪后的区域截图设计，更精确地指导 LLM 定位目标元素。
        """
        return self._build_find_prompt(target_name, region)

    def _parse_find_result_with_offset(
        self,
        result: Any,
        target_name: str,
        region: Dict[str, int]
    ) -> Optional[Tuple[int, int]]:
        """Parse find element result and convert to screen absolute coordinates
        
        Args:
            result: LLM 响应结果（区域截图坐标系）
            target_name: 目标名称
            region: 搜索区域（屏幕绝对坐标）
            
        Returns:
            屏幕绝对坐标 (x, y) 或 None
        """
        if result == []:
            self.logger.warning(f"LLM 返回空结果 []，未找到 {target_name}")
            return None

        if result is None:
            self.logger.error("LLM 返回 None")
            return None

        if not isinstance(result, dict):
            self.logger.warning(f"LLM 返回了非字典结果: {type(result)}")
            return None

        if not result.get('found', False):
            self.logger.warning(f"LLM 未找到 {target_name}")
            return None

        x = result.get('center_x')
        y = result.get('center_y')
        confidence = result.get('confidence', 0.0)
        match_text = result.get('match_text', '')
        
        scaled = result.get('_scaled', False)
        scale_x = result.get('_scale_factor_x', 1.0)
        scale_y = result.get('_scale_factor_y', 1.0)

        if x is None or y is None:
            return None

        # 验证坐标是否在区域截图范围内（允许一定的边界误差）
        margin = 10  # 允许的边界误差
        if not (-margin <= x <= region['Width'] + margin and -margin <= y <= region['Height'] + margin):
            self.logger.warning(
                f"LLM 返回的坐标 ({x}, {y}) 超出区域截图范围 "
                f"(范围: 0-{region['Width']}, 0-{region['Height']})，将进行坐标修正"
            )

        # 坐标修正：将超出范围的坐标钳制到有效范围内
        x = max(0, min(x, region['Width']))
        y = max(0, min(y, region['Height']))

        # 将区域截图坐标转换为屏幕绝对坐标
        # region 是屏幕绝对坐标，x,y 是相对于 region 左上角的坐标
        screen_x = int(region['X'] + x)
        screen_y = int(region['Y'] + y)

        self.logger.info(
            f"LLM 找到 {target_name} (匹配文本: {match_text}): "
            f"区域坐标 ({x}, {y}) -> 屏幕坐标 ({screen_x}, {screen_y}), "
            f"置信度: {confidence:.2f}, 已缩放: {scaled}"
        )
        return (screen_x, screen_y)

    def _parse_coordinate_result(
        self,
        result: Any,
        element_type: str
    ) -> Optional[Tuple[int, int]]:
        """Parse coordinate result from LLM response"""
        if result == []:
            self.logger.warning(f"LLM 返回空结果 []，未找到 {element_type}")
            return None

        if result is None:
            self.logger.error("LLM 返回 None")
            return None

        if not isinstance(result, dict):
            self.logger.warning(f"LLM 返回了非字典结果: {type(result)}")
            return None

        if not result.get('found', False):
            self.logger.warning(f"LLM 未找到 {element_type}: {result.get('description', '无描述')}")
            return None

        x = result.get('center_x')
        y = result.get('center_y')
        confidence = result.get('confidence', 0.0)
        
        scaled = result.get('_scaled', False)
        scale_x = result.get('_scale_factor_x', 1.0)
        scale_y = result.get('_scale_factor_y', 1.0)

        if x is not None and y is not None:
            self.logger.info(f"LLM 找到 {element_type}: ({x}, {y}), 置信度: {confidence:.2f}, 已缩放: {scaled}, 缩放比例: X={scale_x:.2f}, Y={scale_y:.2f}")
            return (int(x), int(y))

        return None

    def _parse_find_result(
        self,
        result: Any,
        target_name: str,
        region: Dict[str, int]
    ) -> Optional[Tuple[int, int]]:
        """Parse find element result from LLM response"""
        if result == []:
            self.logger.warning(f"LLM 返回空结果 []，未找到 {target_name}")
            return None

        if result is None:
            self.logger.error("LLM 返回 None")
            return None

        if not isinstance(result, dict):
            self.logger.warning(f"LLM 返回了非字典结果: {type(result)}")
            return None

        if not result.get('found', False):
            self.logger.warning(f"LLM 未找到 {target_name}")
            return None

        x = result.get('center_x')
        y = result.get('center_y')
        confidence = result.get('confidence', 0.0)
        match_text = result.get('match_text', '')
        
        scaled = result.get('_scaled', False)
        scale_x = result.get('_scale_factor_x', 1.0)
        scale_y = result.get('_scale_factor_y', 1.0)

        if x is None or y is None:
            return None

        # Validate coordinates are within region
        if (region['X'] <= x <= region['X'] + region['Width'] and
            region['Y'] <= y <= region['Y'] + region['Height']):
            self.logger.info(f"LLM 找到 {target_name} (匹配文本: {match_text}): ({x}, {y}), 置信度: {confidence:.2f}, 已缩放: {scaled}, 缩放比例: X={scale_x:.2f}, Y={scale_y:.2f}")
            return (int(x), int(y))
        else:
            self.logger.warning(f"LLM 返回的坐标 ({x}, {y}) 不在指定区域内 (区域: X={region['X']}, Y={region['Y']}, W={region['Width']}, H={region['Height']})")
            return None

"""
Screenshot Optimizer

负责截图优化（压缩）和尺寸计算的共享模块。
被 LLM 协议和元素定位器共同使用，确保坐标缩放一致性。
"""
import base64
import logging
from io import BytesIO
from typing import Tuple, Optional
from dataclasses import dataclass


@dataclass
class ScreenshotInfo:
    """截图信息数据类"""
    original_width: int
    original_height: int
    compressed_width: int
    compressed_height: int
    scale_x: float
    scale_y: float
    was_compressed: bool


class ScreenshotOptimizer:
    """
    截图优化器
    
    负责：
    1. 截图压缩以减少传输数据量
    2. 计算原始尺寸和压缩尺寸之间的缩放比例
    3. 提供坐标转换方法
    """
    
    DEFAULT_MAX_SIZE_KB = 40  # 减小到 40KB，base64 编码后约 53KB，符合 Kimi Web API 限制
    DEFAULT_MAX_DIMENSION = 768  # 减小最大尺寸以减小文件大小
    
    def __init__(
        self, 
        logger: Optional[logging.Logger] = None,
        max_size_kb: int = DEFAULT_MAX_SIZE_KB,
        max_dimension: int = DEFAULT_MAX_DIMENSION
    ):
        """
        初始化截图优化器
        
        Args:
            logger: 日志记录器
            max_size_kb: 最大目标大小（KB）
            max_dimension: 最大边长（像素）
        """
        self.logger = logger or logging.getLogger(__name__)
        self.max_size_kb = max_size_kb
        self.max_dimension = max_dimension
    
    def optimize(self, screenshot_b64: str) -> Tuple[str, ScreenshotInfo]:
        """
        优化截图：压缩和调整尺寸
        
        Args:
            screenshot_b64: 原始截图的 base64 编码
            
        Returns:
            Tuple of (优化后的 base64 编码, 截图信息)
        """
        try:
            from PIL import Image
            
            # 解码 base64
            image_data = base64.b64decode(screenshot_b64)
            img = Image.open(BytesIO(image_data))
            
            # 获取原始尺寸
            original_width, original_height = img.size
            
            # 转换为 RGB（如果需要）
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # 计算压缩后的尺寸
            compressed_width, compressed_height = self._calculate_compressed_dims(
                original_width, original_height
            )
            
            # 如果尺寸过大，按比例缩放
            if max(original_width, original_height) > self.max_dimension:
                ratio = self.max_dimension / max(original_width, original_height)
                new_width = int(original_width * ratio)
                new_height = int(original_height * ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                compressed_width, compressed_height = new_width, new_height
                self.logger.info(f"截图缩放: {original_width}x{original_height} -> {new_width}x{new_height}")
            
            # 逐步压缩直到满足大小要求
            quality = 85
            buffer = BytesIO()
            
            while quality > 10:
                buffer.seek(0)
                buffer.truncate()
                img.save(buffer, format='JPEG', quality=quality, optimize=True)
                
                current_size_kb = len(buffer.getvalue()) / 1024
                self.logger.debug(f"JPEG 压缩质量 {quality}: {current_size_kb:.1f} KB")
                
                if current_size_kb <= self.max_size_kb:
                    break
                
                quality -= 10
            
            # 如果质量降到最低仍然超过大小，进一步缩小尺寸
            if len(buffer.getvalue()) / 1024 > self.max_size_kb:
                self.logger.warning(f"截图仍然过大，尝试进一步缩放")
                ratio = 0.8
                while len(buffer.getvalue()) / 1024 > self.max_size_kb and ratio > 0.3:
                    new_width = int(img.size[0] * ratio)
                    new_height = int(img.size[1] * ratio)
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    buffer.seek(0)
                    buffer.truncate()
                    img.save(buffer, format='JPEG', quality=75, optimize=True)
                    ratio -= 0.1
                compressed_width, compressed_height = img.size
            
            # 编码为 base64
            optimized_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            final_size_kb = len(optimized_b64) / 1024
            
            # 计算缩放比例
            scale_x = compressed_width / original_width if original_width > 0 else 1.0
            scale_y = compressed_height / original_height if original_height > 0 else 1.0
            was_compressed = original_width != compressed_width or original_height != compressed_height
            
            screenshot_info = ScreenshotInfo(
                original_width=original_width,
                original_height=original_height,
                compressed_width=compressed_width,
                compressed_height=compressed_height,
                scale_x=scale_x,
                scale_y=scale_y,
                was_compressed=was_compressed
            )
            
            self.logger.info(
                f"截图优化完成: {original_width}x{original_height} -> "
                f"{compressed_width}x{compressed_height}, 压缩后大小: {final_size_kb:.1f} KB"
            )
            
            return optimized_b64, screenshot_info
            
        except Exception as e:
            self.logger.warning(f"截图优化失败，使用原始截图: {e}")
            # 返回原始截图和空信息
            return screenshot_b64, ScreenshotInfo(
                original_width=0,
                original_height=0,
                compressed_width=0,
                compressed_height=0,
                scale_x=1.0,
                scale_y=1.0,
                was_compressed=False
            )
    
    def _calculate_compressed_dims(self, width: int, height: int) -> Tuple[int, int]:
        """
        计算压缩后的尺寸（不实际压缩，只计算结果）
        
        Args:
            width: 原始宽度
            height: 原始高度
            
        Returns:
            Tuple of (压缩后宽度, 压缩后高度)
        """
        if width <= 0 or height <= 0:
            return (0, 0)
        
        if max(width, height) > self.max_dimension:
            ratio = self.max_dimension / max(width, height)
            return (int(width * ratio), int(height * ratio))
        
        return (width, height)
    
    def scale_coordinates(
        self, 
        x: int, 
        y: int, 
        screenshot_info: ScreenshotInfo,
        to_original: bool = True
    ) -> Tuple[int, int]:
        """
        缩放坐标
        
        Args:
            x: X 坐标
            y: Y 坐标
            screenshot_info: 截图信息
            to_original: True 表示从压缩坐标转到原始坐标，False 表示从原始坐标转到压缩坐标
            
        Returns:
            Tuple of (缩放后的 X, 缩放后的 Y)
        """
        if not screenshot_info.was_compressed:
            return (x, y)
        
        if to_original:
            # 从压缩坐标转到原始坐标
            scaled_x = int(x / screenshot_info.scale_x)
            scaled_y = int(y / screenshot_info.scale_y)
        else:
            # 从原始坐标转到压缩坐标
            scaled_x = int(x * screenshot_info.scale_x)
            scaled_y = int(y * screenshot_info.scale_y)
        
        return (scaled_x, scaled_y)
    
    def get_compression_params(self) -> dict:
        """获取压缩参数"""
        return {
            "max_size_kb": self.max_size_kb,
            "max_dimension": self.max_dimension
        }

"""
Screenshot Helper

Helper class for screenshot processing and base64 conversion.
"""
import base64
import logging
from io import BytesIO
from typing import Optional


class ScreenshotHelper:
    """Helper class for screenshot operations"""

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize screenshot helper

        Args:
            logger: Logger instance
        """
        self.logger = logger or logging.getLogger(__name__)

    def screenshot_to_base64(self, screenshot) -> Optional[str]:
        """
        Convert screenshot to base64 string

        Args:
            screenshot: PIL Image object, bytes, or other supported format

        Returns:
            Base64 encoded string or None if conversion fails
        """
        try:
            if hasattr(screenshot, 'save'):
                # PIL Image 对象
                buffer = BytesIO()
                screenshot.save(buffer, format='PNG')
                return base64.b64encode(buffer.getvalue()).decode('utf-8')
            elif hasattr(screenshot, 'encodebytes'):
                # 老版本的 PIL
                return base64.encodebytes(screenshot).decode('utf-8')
            elif isinstance(screenshot, bytes):
                # 已经是字节
                return base64.b64encode(screenshot).decode('utf-8')
            elif isinstance(screenshot, str):
                # 已经是 base64 字符串
                return screenshot
            else:
                self.logger.error(f"不支持的截图类型: {type(screenshot)}")
                return None
        except Exception as e:
            self.logger.error(f"截图转 base64 失败: {e}", exc_info=True)
            return None

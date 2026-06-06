"""
OCR Processor - Facade Module

Provides OCR functionality by wrapping the core OCR processor.
This module bridges the high-level OCR interface with the core implementation.
"""

from mcp_core.ocr_processor import OCRProcessor as _CoreOCRProcessor


class OCRProcessor:
    """
    High-level OCR Processor that wraps the core implementation.
    
    This class provides a simplified interface for OCR operations,
    delegating to the core OCR processor from mcp_core.
    """
    
    def __init__(self, dep_manager):
        """
        Initialize OCR Processor with dependency manager.
        
        Args:
            dep_manager: Dependency manager instance for accessing required libraries
        """
        self._core = _CoreOCRProcessor(dep_manager)
        self._dep_manager = dep_manager
    
    def capture_screenshot(self, region=None):
        """Capture screenshot of screen or region"""
        return self._core.capture_screenshot(region)
    
    def find_text(self, image, text, fuzzy_match=False):
        """Find text in image.

        The core implementation accepts only (image, text); fuzzy matching is
        built into ``find_text_in_image``. We delegate there so callers can
        pass ``fuzzy_match`` without breaking positional arity.
        """
        return self._core.find_text_in_image(image, text)
    
    def recognize(self, image):
        """Recognize all text in image"""
        return self._core.recognize(image)

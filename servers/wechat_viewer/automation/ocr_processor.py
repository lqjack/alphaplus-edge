"""
OCR and Image Processing Component

Handles all OCR operations, image capture, text recognition, and image analysis.
"""

import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime

try:
    import numpy as np
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    np = None
    cv2 = None
    CV2_AVAILABLE = False

from PIL import Image

# Handle mcp_core imports gracefully - commented out to avoid dependency issues
# try:
#     from mcp_core.interfaces import IOCRProcessor
#     MCP_CORE_INTERFACES_AVAILABLE = True
# except ImportError:
#     pass

# Define minimal fallback interface directly to avoid mcp_core dependency issues
MCP_CORE_INTERFACES_AVAILABLE = False

class IOCRProcessor: pass
from automation.adaptive_ocr import AdaptiveOCR

if TYPE_CHECKING:
    import numpy as np


@dataclass
class OCRResult:
    """OCR result data structure"""
    text: str
    confidence: float
    position: Dict[str, int]


@dataclass
class ScreenshotRegion:
    """Screenshot region data structure"""
    x: int
    y: int
    width: int
    height: int


class OCRProcessor:
    """Handles all OCR and image processing operations"""
    
    def __init__(self, ocr_processor: IOCRProcessor, adaptive_ocr: AdaptiveOCR):
        self.ocr_processor = ocr_processor
        self.adaptive_ocr = adaptive_ocr
        self.logger = logging.getLogger("mcp-server-wechat-viewer-mcp.ocr_processor")
        
        # Initialize screenshot directory
        self.screenshot_dir = Path("temp_screenshots")
        self.screenshot_dir.mkdir(exist_ok=True)
    
    def capture_screenshot(self, region: Optional[Tuple[int, int, int, int]] = None) -> Optional["np.ndarray"]:
        """Capture screenshot of specified region"""
        try:
            if region:
                screenshot = self.ocr_processor.capture_screenshot(region)
            else:
                screenshot = self.ocr_processor.capture_screenshot()
            
            if screenshot is None:
                self.logger.error("Screenshot capture failed")
                return None
            
            # Ensure numpy array format
            if hasattr(screenshot, 'shape'):
                # Already numpy array
                return screenshot
            else:
                # PIL Image, convert to numpy array
                return np.array(screenshot)
                
        except Exception as e:
            self.logger.error(f"Error capturing screenshot: {e}")
            return None
    
    def find_text_in_image(self, image: "np.ndarray", text: str, fuzzy_match: bool = False) -> List[OCRResult]:
        """Find text in image using OCR"""
        try:
            results = self.adaptive_ocr.find_text(image, text, fuzzy_match=fuzzy_match)
            ocr_results = []
            
            for result in results:
                ocr_result = OCRResult(
                    text=result.get('text', ''),
                    confidence=result.get('confidence', 0),
                    position=result.get('position', {})
                )
                ocr_results.append(ocr_result)
            
            return ocr_results
            
        except Exception as e:
            self.logger.error(f"Error finding text in image: {e}")
            return []
    
    def recognize(self, image: "np.ndarray") -> List[OCRResult]:
        """Recognize all text in image"""
        try:
            results = self.adaptive_ocr.recognize(image)
            ocr_results = []
            
            for result in results:
                ocr_result = OCRResult(
                    text=result.get('text', ''),
                    confidence=result.get('confidence', 0),
                    position=result.get('position', {})
                )
                ocr_results.append(ocr_result)
            
            return ocr_results
            
        except Exception as e:
            self.logger.error(f"Error recognizing text in image: {e}")
            return []
    
    def get_window_title(self) -> Optional[str]:
        """Get current window title"""
        try:
            return self.ocr_processor.get_window_title()
        except Exception as e:
            self.logger.error(f"Error getting window title: {e}")
            return None
    
    def save_screenshot(self, image: "np.ndarray", prefix: str = "screenshot") -> Optional[str]:
        """Save screenshot to project directory"""
        try:
            if not CV2_AVAILABLE:
                self.logger.error("cv2 not available, cannot save screenshot")
                return None
                
            # Generate unique filename
            timestamp = int(time.time() * 1000)  # Millisecond timestamp
            filename = f"{prefix}_{timestamp}.png"
            filepath = self.screenshot_dir / filename
            
            # Save screenshot
            cv2.imwrite(str(filepath), image)
            
            self.logger.debug(f"Screenshot saved to: {filepath}")
            return str(filepath)
            
        except Exception as e:
            self.logger.error(f"Error saving screenshot: {e}")
            return None
    
    def cleanup_screenshot(self, filepath: str):
        """Clean up screenshot file"""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                self.logger.debug(f"Deleted screenshot: {filepath}")
        except Exception as e:
            self.logger.warning(f"Error deleting screenshot: {e}")
    
    def cleanup_all_screenshots(self):
        """Clean up all screenshot files"""
        try:
            for screenshot_file in self.screenshot_dir.glob("*.png"):
                os.remove(screenshot_file)
            self.logger.info("All screenshot files cleaned up")
        except Exception as e:
            self.logger.error(f"Error cleaning up screenshots: {e}")
    
    def analyze_screenshot_with_llm(self, screenshot: "np.ndarray", prompt: str) -> Optional[Dict[str, Any]]:
        """Analyze screenshot using LLM (placeholder for future implementation)"""
        try:
            # This would integrate with LLM for advanced image analysis
            # For now, return None to indicate not implemented
            self.logger.debug("LLM screenshot analysis not yet implemented")
            return None
        except Exception as e:
            self.logger.error(f"Error in LLM screenshot analysis: {e}")
            return None

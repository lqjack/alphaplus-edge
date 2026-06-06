"""
OCR Processor Core

Handles screenshot capture and OCR text recognition operations.
"""
import logging
import re
import os
import platform
import tempfile
from typing import Dict, Optional, Any, List


from .interfaces import IOCRProcessor, TextResult

class OCRProcessor(IOCRProcessor):
    """Handles OCR operations for GUI automation"""

    def __init__(self, dep_manager):
        self.dep_manager = dep_manager
        self.logger = logging.getLogger("mcp-server-wechat-viewer-mcp.ocr_processor")
        self._tesseract_available = None

    def _is_tesseract_available(self, pytesseract) -> bool:
        """Return whether the native tesseract binary can be executed."""
        if self._tesseract_available is not None:
            return self._tesseract_available

        if not pytesseract:
            self._tesseract_available = False
            return False

        try:
            pytesseract.get_tesseract_version()
            self._tesseract_available = True
        except Exception as exc:
            self.logger.warning("Native tesseract unavailable, using OCR fallback when possible: %s", exc)
            self._tesseract_available = False
        return self._tesseract_available

    def _to_pil_image(self, image):
        """Convert a PIL/numpy image to a PIL image for OCR backends."""
        if image is None:
            return None
        if hasattr(image, "convert") and hasattr(image, "size"):
            return image
        try:
            import numpy as np
            from PIL import Image

            if isinstance(image, np.ndarray):
                return Image.fromarray(image)
        except Exception as exc:
            self.logger.debug("Failed to convert image to PIL: %s", exc)
        return None

    def _recognize_with_macos_vision(self, image) -> List[TextResult]:
        """Recognize text with Apple's Vision framework when tesseract is not installed."""
        if platform.system().lower() != "darwin":
            return []

        pil_image = self._to_pil_image(image)
        if pil_image is None:
            return []

        temp_path = None
        try:
            from Foundation import NSURL
            try:
                from Vision import (
                    VNImageRequestHandler,
                    VNRecognizeTextRequest,
                    VNRequestTextRecognitionLevelAccurate,
                )
            except Exception:
                import objc
                from Foundation import NSBundle

                vision_bundle = NSBundle.bundleWithPath_("/System/Library/Frameworks/Vision.framework")
                if vision_bundle is None or not vision_bundle.load():
                    raise
                VNImageRequestHandler = objc.lookUpClass("VNImageRequestHandler")
                VNRecognizeTextRequest = objc.lookUpClass("VNRecognizeTextRequest")
                VNRequestTextRecognitionLevelAccurate = 0

            width, height = pil_image.size
            if width <= 0 or height <= 0:
                return []

            if pil_image.mode not in ("RGB", "RGBA", "L"):
                pil_image = pil_image.convert("RGB")

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
                temp_path = temp_file.name
            pil_image.save(temp_path)

            request = VNRecognizeTextRequest.alloc().init()
            request.setRecognitionLanguages_(["zh-Hans", "zh-Hant", "en-US"])
            request.setRecognitionLevel_(VNRequestTextRecognitionLevelAccurate)
            if hasattr(request, "setUsesLanguageCorrection_"):
                request.setUsesLanguageCorrection_(True)

            handler = VNImageRequestHandler.alloc().initWithURL_options_(
                NSURL.fileURLWithPath_(temp_path),
                {},
            )
            perform_result = handler.performRequests_error_([request], None)
            if isinstance(perform_result, tuple):
                success, error = perform_result
            else:
                success, error = bool(perform_result), None
            if not success:
                self.logger.warning("macOS Vision OCR request failed: %s", error)
                return []

            results = []
            for observation in request.results() or []:
                candidates = observation.topCandidates_(1)
                if not candidates:
                    continue
                candidate = candidates[0]
                text = (candidate.string() or "").strip()
                if not text:
                    continue

                confidence = float(candidate.confidence() or 0)
                if confidence <= 1.0:
                    confidence *= 100

                bbox = observation.boundingBox()
                x = float(bbox.origin.x) * width
                box_width = float(bbox.size.width) * width
                box_height = float(bbox.size.height) * height
                y = (1.0 - float(bbox.origin.y) - float(bbox.size.height)) * height

                results.append(TextResult(
                    text=text,
                    confidence=confidence,
                    position={
                        "x": max(0.0, x),
                        "y": max(0.0, y),
                        "width": max(1.0, box_width),
                        "height": max(1.0, box_height),
                    },
                ))

            results.sort(key=lambda item: (item.position["y"], item.position["x"]))
            self.logger.info("macOS Vision OCR recognized %d text elements", len(results))
            return results
        except Exception as exc:
            self.logger.warning("macOS Vision OCR failed: %s", exc, exc_info=True)
            return []
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def _filter_text_results(
        self,
        results: List[TextResult],
        search_text: str,
        confidence_threshold: int = 60,
    ) -> List[Dict[str, Any]]:
        """Filter OCR text results for a target string using fuzzy substring variants."""
        if not search_text:
            return []

        search_text_lower = search_text.lower()
        compact_lower = search_text.replace(" ", "").lower()
        search_variants = [
            search_text_lower,
            compact_lower,
            "".join([word.capitalize() for word in search_text.split()]).lower(),
            search_text.upper().lower(),
        ]

        matches = []
        for result in results:
            text = (result.get("text") or "").strip()
            text_lower = text.lower()
            compact_text_lower = text.replace(" ", "").lower()
            confidence = float(result.get("confidence") or 0)
            if confidence < max(20, confidence_threshold - 40):
                continue

            matched_variant = None
            for variant in search_variants:
                if variant and (variant in text_lower or variant in compact_text_lower):
                    matched_variant = variant
                    break
            if not matched_variant:
                continue

            match_quality = min(1.0, len(matched_variant) / max(1, len(compact_text_lower)))
            matches.append({
                "text": text,
                "confidence": min(100, confidence + int(match_quality * 20)),
                "position": result.get("position", {}),
                "match_quality": match_quality,
            })

        matches.sort(key=lambda item: (-item["confidence"], -item["match_quality"]))
        return matches

    def capture_screenshot(self, region: Optional[Any] = None):
        """Capture screenshot of the screen or a region with enhanced error handling"""
        self.logger.info(f"Attempting to capture screenshot with region: {region}")
        pyautogui = self.dep_manager.get_dependency("pyautogui")
        if not pyautogui:
            self.logger.error("pyautogui dependency not available")
            return None

        screenshot_region = None
        logical_screen_size = None
        window_capture_id = None
        window_capture_bounds = None
        try:
            screen_size = pyautogui.size()
            if isinstance(screen_size, tuple) and len(screen_size) == 2:
                logical_screen_size = (int(screen_size[0]), int(screen_size[1]))
        except Exception as exc:
            self.logger.debug("Failed to read logical screen size from pyautogui: %s", exc)

        # Enhanced region validation and conversion
        if region:
            # Convert region to tuple format (x, y, width, height)
            if isinstance(region, dict):
                window_capture_id = region.get("_window_id") or region.get("window_id")
                window_capture_bounds = region.get("_window_bounds") or region.get("window_bounds")
                # Handle different key formats
                x = region.get('X') or region.get('x') or region.get('left') or 0
                y = region.get('Y') or region.get('y') or region.get('top') or 0
                width = region.get('Width') or region.get('width') or region.get('w') or 0
                height = region.get('Height') or region.get('height') or region.get('h') or 0

                # Validate values
                if not all(isinstance(val, (int, float)) for val in [x, y, width, height]):
                    self.logger.warning(f"Invalid region values: {region}")
                    return None

                # Ensure positive dimensions
                width = max(1, int(width))
                height = max(1, int(height))

                screenshot_region = (int(x), int(y), width, height)
                self.logger.debug(f"Region converted to: {screenshot_region}")
            elif isinstance(region, (tuple, list)) and len(region) == 4:
                # Validate tuple/list format
                if all(isinstance(val, (int, float)) for val in region):
                    screenshot_region = tuple(int(val) for val in region)
                    self.logger.debug(f"Region converted to: {screenshot_region}")
                else:
                    self.logger.warning(f"Invalid region format in tuple: {region}")
                    return None
            else:
                self.logger.warning(f"Invalid region format: {region}")
                return None

            # Validate region bounds
            if screenshot_region[2] <= 0 or screenshot_region[3] <= 0:
                self.logger.warning(f"Invalid region dimensions: {screenshot_region}")
                return None

        try:
            if (
                window_capture_id
                and platform.system().lower() == "darwin"
            ):
                screenshot = self._capture_macos_window(
                    int(window_capture_id),
                    screenshot_region,
                    window_capture_bounds,
                    logical_screen_size=logical_screen_size,
                )
                if screenshot is not None:
                    self.logger.info(
                        "Successfully captured macOS window screenshot: %sx%s window_id=%s",
                        screenshot.width,
                        screenshot.height,
                        window_capture_id,
                    )
                    return screenshot
                self.logger.warning(
                    "Window-scoped macOS screenshot failed for window_id=%s; falling back to screen capture",
                    window_capture_id,
                )

            # Capture screenshot
            if region:
                screenshot = pyautogui.screenshot(region=screenshot_region)
                self.logger.debug(f"Screenshot captured with region: {screenshot_region}")
            else:
                # Capture full screen
                self.logger.debug("Capturing full screen screenshot")
                screenshot = pyautogui.screenshot()
                self.logger.debug("Full screen screenshot captured successfully")

            # Validate screenshot
            if screenshot is None:
                self.logger.error("Screenshot capture returned None")
                return None

            # Check if screenshot is valid PIL Image
            if not hasattr(screenshot, 'size') or not hasattr(screenshot, 'width') or not hasattr(screenshot, 'height'):
                self.logger.error(f"Invalid screenshot object type: {type(screenshot)}")
                return None

            # Check if screenshot has valid dimensions
            if screenshot.width <= 0 or screenshot.height <= 0:
                self.logger.error(f"Screenshot has invalid dimensions: {screenshot.width}x{screenshot.height}")
                return None

            if hasattr(screenshot, "info") and isinstance(screenshot.info, dict):
                if region and screenshot_region:
                    screenshot.info["_logical_capture_region"] = {
                        "X": int(screenshot_region[0]),
                        "Y": int(screenshot_region[1]),
                        "Width": int(screenshot_region[2]),
                        "Height": int(screenshot_region[3]),
                    }
                elif logical_screen_size:
                    screenshot.info["_logical_capture_region"] = {
                        "X": 0,
                        "Y": 0,
                        "Width": int(logical_screen_size[0]),
                        "Height": int(logical_screen_size[1]),
                    }
                if logical_screen_size:
                    screenshot.info["_screen_logical_size"] = {
                        "Width": int(logical_screen_size[0]),
                        "Height": int(logical_screen_size[1]),
                    }

            self.logger.info(f"Successfully captured screenshot: {screenshot.width}x{screenshot.height}")
            return screenshot

        except Exception as e:
            self.logger.error(f"Failed to capture screenshot: {e}", exc_info=True)
            # Fast fail as requested - don't try fallback methods that mask the real issue
            return None

    def _capture_macos_window(
        self,
        window_id: int,
        screenshot_region: Optional[Any] = None,
        window_bounds: Optional[Dict[str, Any]] = None,
        *,
        logical_screen_size: Optional[Any] = None,
    ):
        """Capture a specific macOS window and crop inside that window when needed."""
        import subprocess
        from PIL import Image

        if window_id <= 0:
            return None

        temp_file = os.path.join(tempfile.gettempdir(), f"mcp_window_capture_{os.getpid()}.png")
        try:
            cmd = ["screencapture", "-x", "-o", "-l", str(int(window_id)), temp_file]
            subprocess.run(cmd, check=True, capture_output=True, timeout=5)

            if not os.path.exists(temp_file):
                return None

            img = Image.open(temp_file)
            img.load()

            normalized_window_bounds = self._normalize_window_bounds(window_bounds)
            if screenshot_region and normalized_window_bounds:
                crop_box = self._window_region_to_crop_box(
                    screenshot_region,
                    normalized_window_bounds,
                    img.size,
                )
                if crop_box:
                    img = img.crop(crop_box)

            if hasattr(img, "info") and isinstance(img.info, dict):
                logical_region = screenshot_region
                if logical_region is None and normalized_window_bounds:
                    logical_region = (
                        int(normalized_window_bounds["X"]),
                        int(normalized_window_bounds["Y"]),
                        int(normalized_window_bounds["Width"]),
                        int(normalized_window_bounds["Height"]),
                    )
                if logical_region:
                    img.info["_logical_capture_region"] = {
                        "X": int(logical_region[0]),
                        "Y": int(logical_region[1]),
                        "Width": int(logical_region[2]),
                        "Height": int(logical_region[3]),
                    }
                if logical_screen_size:
                    img.info["_screen_logical_size"] = {
                        "Width": int(logical_screen_size[0]),
                        "Height": int(logical_screen_size[1]),
                    }

            return img
        except Exception as exc:
            self.logger.debug(
                "Failed to capture macOS window screenshot for window_id=%s: %s",
                window_id,
                exc,
            )
            return None
        finally:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass

    def _normalize_window_bounds(self, bounds: Optional[Dict[str, Any]]) -> Optional[Dict[str, float]]:
        if not isinstance(bounds, dict):
            return None
        try:
            return {
                "X": float(bounds.get("X", bounds.get("x", 0)) or 0),
                "Y": float(bounds.get("Y", bounds.get("y", 0)) or 0),
                "Width": float(bounds.get("Width", bounds.get("width", 0)) or 0),
                "Height": float(bounds.get("Height", bounds.get("height", 0)) or 0),
            }
        except Exception:
            return None

    def _window_region_to_crop_box(
        self,
        screenshot_region: Any,
        window_bounds: Dict[str, float],
        image_size: Any,
    ) -> Optional[Any]:
        if not screenshot_region or not window_bounds:
            return None
        width = float(window_bounds.get("Width", 0) or 0)
        height = float(window_bounds.get("Height", 0) or 0)
        if width <= 0 or height <= 0:
            return None

        try:
            scale_x = float(image_size[0]) / width
            scale_y = float(image_size[1]) / height
            rel_x = max(0.0, float(screenshot_region[0]) - float(window_bounds["X"]))
            rel_y = max(0.0, float(screenshot_region[1]) - float(window_bounds["Y"]))
            left = int(round(rel_x * scale_x))
            top = int(round(rel_y * scale_y))
            right = int(round((rel_x + float(screenshot_region[2])) * scale_x))
            bottom = int(round((rel_y + float(screenshot_region[3])) * scale_y))
            right = min(int(image_size[0]), max(left + 1, right))
            bottom = min(int(image_size[1]), max(top + 1, bottom))
            return (left, top, right, bottom)
        except Exception as exc:
            self.logger.debug("Failed to compute window crop box: %s", exc)
            return None

    def _capture_macos_builtin(self, region: Optional[Any] = None):
        """macOS specific screenshot using screencapture command"""
        import subprocess
        import os
        import tempfile
        from PIL import Image
        
        temp_file = os.path.join(tempfile.gettempdir(), f"mcp_screenshot_{os.getpid()}.png")
        try:
            cmd = ["screencapture", "-x", temp_file]
            # screencapture doesn't support region directly in the same way, 
            # so we capture full screen and crop if needed
            subprocess.run(cmd, check=True, capture_output=True)
            
            if os.path.exists(temp_file):
                img = Image.open(temp_file)
                # Ensure image is loaded into memory before deleting file
                img.load()
                
                if region:
                    # Convert region to crop box (left, top, right, bottom)
                    if isinstance(region, dict):
                        x = region.get('X') or region.get('x') or region.get('left') or 0
                        y = region.get('Y') or region.get('y') or region.get('top') or 0
                        w = region.get('Width') or region.get('width') or 0
                        h = region.get('Height') or region.get('height') or 0
                    else:
                        x, y, w, h = region
                        
                    img = img.crop((int(x), int(y), int(x+w), int(y+h)))
                
                return img
        finally:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
        return None

    def recognize_text(self, image, lang: str = 'chi_sim+eng') -> str:
        """Perform OCR on an image with enhanced preprocessing and error handling"""
        pytesseract = self.dep_manager.get_dependency("pytesseract")
        if not self._is_tesseract_available(pytesseract):
            vision_results = self._recognize_with_macos_vision(image)
            return "\n".join(result.text for result in vision_results)

        try:
            # Validate image
            if image is None:
                self.logger.error("Image is None, cannot perform OCR")
                return ""
            
            # Convert image to appropriate format if needed
            try:
                import numpy as np
                if isinstance(image, np.ndarray):
                    # Convert numpy array to PIL Image
                    from PIL import Image
                    image = Image.fromarray(image)
                elif not hasattr(image, 'convert'):
                    self.logger.error(f"Unsupported image format: {type(image)}")
                    return ""
            except Exception as format_error:
                self.logger.warning(f"Image format conversion failed: {format_error}")
            
            # Preprocess image for better OCR results
            try:
                # Convert to grayscale for better text recognition
                gray_image = image.convert('L')
                
                # Apply some basic image processing
                from PIL import ImageEnhance
                enhancer = ImageEnhance.Contrast(gray_image)
                enhanced_image = enhancer.enhance(2.0)  # Increase contrast
                
                # Perform OCR
                text = pytesseract.image_to_string(enhanced_image, lang=lang)
                
                # Clean up text
                cleaned_text = text.strip()
                cleaned_text = re.sub(r'\n\s*\n', '\n', cleaned_text)  # Remove empty lines
                cleaned_text = re.sub(r'\s+', ' ', cleaned_text)  # Remove extra spaces
                
                self.logger.debug(f"Recognized text: {cleaned_text[:100]}...")  # Log first 100 chars
                return cleaned_text
                
            except Exception as preprocess_error:
                self.logger.warning(f"Image preprocessing failed, trying direct OCR: {preprocess_error}")
                # Try direct OCR without preprocessing
                text = pytesseract.image_to_string(image, lang=lang)
                return text.strip()
                
        except Exception as e:
            self.logger.error(f"Failed to recognize text: {e}", exc_info=True)
            # Try alternative approach with different language
            try:
                text = pytesseract.image_to_string(image, lang='eng')
                return text.strip()
            except Exception as alt_e:
                self.logger.error(f"Alternative OCR also failed: {alt_e}")
                return ""

    def recognize(self, image, target_hint: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Recognize text in an image and return detailed results with enhanced processing.
        Compatible with the interface used by multi_layer_locator.
        
        Args:
            image: Input image (numpy array or PIL Image)
            target_hint: Optional hint for expected text (for semantic correction)
            
        Returns:
            List of dictionaries containing recognized text with confidence and position
        """
        pytesseract = self.dep_manager.get_dependency("pytesseract")
        if not self._is_tesseract_available(pytesseract):
            return self._recognize_with_macos_vision(image)
        
        try:
            # Validate image
            if image is None:
                self.logger.error("Image is None, cannot perform OCR")
                return []
            
            # Convert image to appropriate format if needed
            try:
                import numpy as np
                if isinstance(image, np.ndarray):
                    # Convert numpy array to PIL Image
                    from PIL import Image
                    image = Image.fromarray(image)
                elif not hasattr(image, 'convert'):
                    self.logger.error(f"Unsupported image format: {type(image)}")
                    return []
            except Exception as format_error:
                self.logger.warning(f"Image format conversion failed: {format_error}")
            
            # Preprocess image for better OCR results
            try:
                # Convert to grayscale
                gray_image = image.convert('L')
                
                # Check if it's a dark theme (low average brightness)
                import numpy as np
                avg_brightness = np.mean(np.array(gray_image))
                if avg_brightness < 100:
                    self.logger.debug(f"Detecting dark theme (brightness: {avg_brightness:.2f}), inverting image for OCR")
                    from PIL import ImageOps
                    processed_image = ImageOps.invert(gray_image)
                else:
                    processed_image = gray_image
                
                # Further enhance contrast
                from PIL import ImageEnhance
                enhancer = ImageEnhance.Contrast(processed_image)
                processed_image = enhancer.enhance(2.0)
                
                # Use processed image for OCR
                # PSM 3: Fully automatic page segmentation, but no OSD. (Better for sparse/complex layouts)
                # PSM 6: Assume a single uniform block of text. (Worse for lists)
                psm_mode = 3 
                data = pytesseract.image_to_data(
                    processed_image, 
                    output_type=pytesseract.Output.DICT,
                    config=f'--psm {psm_mode}'
                )
                self.logger.debug(f"OCR detected {len(data['text'])} potential text boxes using PSM {psm_mode}")
            except Exception as preprocess_error:
                self.logger.warning(f"Image preprocessing or OCR failed, trying default: {preprocess_error}")
                data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            
            results = []
            n_boxes = len(data['text'])
            
            for i in range(n_boxes):
                confidence = int(data['conf'][i])
                text = data['text'][i].strip()
                
                # Filter and process results
                if confidence > 30 and text:
                    # Enhance text processing
                    processed_text = text.strip()
                    processed_text = re.sub(r'\s+', ' ', processed_text)  # Remove extra spaces
                    
                    # Add semantic correction if target_hint is provided
                    if target_hint and target_hint.lower() in processed_text.lower():
                        confidence = min(100, confidence + 10)  # Boost confidence for relevant text
                   
                    results.append(TextResult(
                        text=processed_text,
                        confidence=float(confidence),
                        position={
                            'x': data['left'][i],
                            'y': data['top'][i],
                            'width': data['width'][i],
                            'height': data['height'][i]
                        }
                    ))
            
            # Sort by top-to-bottom, left-to-right
            results.sort(key=lambda r: (r.position['y'], r.position['x']))
            
            # Filter out very low confidence results
            filtered_results = [r for r in results if r.confidence >= 40]
            
            self.logger.debug(f"Recognized {len(filtered_results)} text elements with confidence >= 40")
            return filtered_results
            
        except Exception as e:
            self.logger.error(f"Failed to recognize image: {e}", exc_info=True)
            vision_results = self._recognize_with_macos_vision(image)
            if vision_results:
                return vision_results
            # Try alternative approach with different configuration
            try:
                data = pytesseract.image_to_data(
                    image, 
                    output_type=pytesseract.Output.DICT,
                    config='--psm 7'  # Treat image as a single line of text
                )
                
                results = []
                n_boxes = len(data['text'])
                
                for i in range(n_boxes):
                    confidence = int(data['conf'][i])
                    text = data['text'][i].strip()
                    
                    if confidence > 20 and text:
                        results.append({
                            'text': text.strip(),
                            'confidence': confidence,
                            'position': {
                                'x': data['left'][i],
                                'y': data['top'][i],
                                'width': data['width'][i],
                                'height': data['height'][i]
                            }
                        })
                
                return results
                
            except Exception as alt_e:
                self.logger.error(f"Alternative OCR also failed: {alt_e}")
                return []

    def find_text(self, image: Any, text: str) -> List[Dict[str, Any]]:
        """Implementation of IOCRProcessor.find_text"""
        return self.find_text_in_image(image, text)

    def find_text_in_image(self, image, search_text: str, confidence_threshold: int = 60) -> List[Dict[str, Any]]:
        """Find specific text in an image using OCR with enhanced search capabilities"""
        pytesseract = self.dep_manager.get_dependency("pytesseract")
        if not self._is_tesseract_available(pytesseract):
            return self._filter_text_results(
                self._recognize_with_macos_vision(image),
                search_text,
                confidence_threshold,
            )

        try:
            # Validate inputs
            if not search_text:
                self.logger.warning("Empty search text provided")
                return []
            
            # Get detailed OCR data with enhanced configuration
            try:
                # Try with page segmentation mode for better results
                data = pytesseract.image_to_data(
                    image, 
                    output_type=pytesseract.Output.DICT,
                    config='--psm 6'  # Assume a single uniform block of text
                )
            except Exception as config_error:
                self.logger.warning(f"Enhanced OCR config failed, using default: {config_error}")
                data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            
            results = []
            n_boxes = len(data['text'])

            # Enhanced search with multiple strategies
            search_text_lower = search_text.lower()
            search_variants = [
                search_text_lower,
                search_text.replace(' ', ''),  # Remove spaces
                ''.join([word.capitalize() for word in search_text.split()]),  # Capitalize words
                search_text.upper()  # All uppercase
            ]
            
            for i in range(n_boxes):
                confidence = int(data['conf'][i])
                text = data['text'][i].strip()
                text_lower = text.lower()
                
                # Check if text matches any search variant
                if confidence > confidence_threshold and any(variant in text_lower for variant in search_variants):
                    # Calculate match quality
                    match_quality = 0
                    for variant in search_variants:
                        if variant in text_lower:
                            match_quality = max(match_quality, len(variant) / len(text_lower))
                    
                    # Boost confidence for better matches
                    adjusted_confidence = min(100, confidence + int(match_quality * 20))
                    
                    results.append({
                        'text': text,
                        'confidence': adjusted_confidence,
                        'position': {
                            'x': data['left'][i],
                            'y': data['top'][i],
                            'width': data['width'][i],
                            'height': data['height'][i]
                        },
                        'match_quality': match_quality
                    })
            
            # Sort results by confidence and match quality
            results.sort(key=lambda x: (-x['confidence'], -x['match_quality']))
            
            # Filter out very low confidence results
            filtered_results = [r for r in results if r['confidence'] >= max(40, confidence_threshold - 20)]
            
            self.logger.debug(f"Found {len(filtered_results)} matches for '{search_text}'")
            return filtered_results

        except Exception as e:
            self.logger.error(f"Failed to find text in image: {e}", exc_info=True)
            vision_matches = self._filter_text_results(
                self._recognize_with_macos_vision(image),
                search_text,
                confidence_threshold,
            )
            if vision_matches:
                return vision_matches
            # Try alternative approach with different configuration
            try:
                data = pytesseract.image_to_data(
                    image, 
                    output_type=pytesseract.Output.DICT,
                    config='--psm 7'  # Treat image as a single line of text
                )
                
                results = []
                n_boxes = len(data['text'])
                
                for i in range(n_boxes):
                    confidence = int(data['conf'][i])
                    text = data['text'][i].strip()
                    
                    if confidence > max(20, confidence_threshold - 40) and search_text_lower in text.lower():
                        results.append({
                            'text': text,
                            'confidence': confidence,
                            'position': {
                                'x': data['left'][i],
                                'y': data['top'][i],
                                'width': data['width'][i],
                                'height': data['height'][i]
                            }
                        })
                
                return results
                
            except Exception as alt_e:
                self.logger.error(f"Alternative OCR also failed: {alt_e}")
                return []

    def get_window_title(self) -> str:
        """Get the current frontmost window title using platform-specific methods"""
        if self._is_macos():
            return self._get_window_title_macos()
        elif self._is_windows():
            return self._get_window_title_windows()
        elif self._is_linux():
            return self._get_window_title_linux()
        else:
            self.logger.error(f"Unsupported platform for window title detection")
            return ""

    def _is_macos(self) -> bool:
        """Check if running on macOS"""
        import platform
        return platform.system().lower() == "darwin"

    def _is_windows(self) -> bool:
        """Check if running on Windows"""
        import platform
        return platform.system().lower() == "windows"

    def _is_linux(self) -> bool:
        """Check if running on Linux"""
        import platform
        return platform.system().lower() == "linux"

    def _get_window_title_macos(self) -> str:
        """Get window title on macOS using AppleScript"""
        subprocess = self.dep_manager.get_dependency("subprocess")
        if not subprocess:
            self.logger.error("subprocess dependency not available")
            return ""

        try:
            script = """
            tell application "System Events"
                set frontApp to first application process whose frontmost is true
                set frontAppName to name of frontApp
                tell process frontAppName
                    if (count of windows) > 0 then
                        return name of front window
                    else
                        return ""
                    end if
                end tell
            end tell
            """
            result = subprocess.run(["osascript", "-e", script],
                                  capture_output=True, text=True, timeout=5)
            return result.stdout.strip()
        except Exception as e:
            self.logger.error(f"Failed to get window title on macOS: {e}", exc_info=True)
            return ""

    def _get_window_title_windows(self) -> str:
        """Get window title on Windows using win32gui"""
        try:
            win32gui = self.dep_manager.get_dependency("win32gui")
            if not win32gui:
                self.logger.error("win32gui dependency not available")
                return ""

            def enum_windows_callback(hwnd, _):
                if win32gui.IsWindowVisible(hwnd) and win32gui.IsWindowEnabled(hwnd):
                    window_text = win32gui.GetWindowText(hwnd)
                    if window_text:
                        # Store the first visible window title found
                        enum_windows_callback.title = window_text
                        return False  # Stop enumeration
                return True  # Continue enumeration

            enum_windows_callback.title = ""
            win32gui.EnumWindows(enum_windows_callback, None)
            return enum_windows_callback.title

        except Exception as e:
            self.logger.error(f"Failed to get window title on Windows: {e}", exc_info=True)
            return ""

    def _get_window_title_linux(self) -> str:
        """Get window title on Linux using wmctrl or xdotool"""
        subprocess = self.dep_manager.get_dependency("subprocess")
        if not subprocess:
            self.logger.error("subprocess dependency not available")
            return ""

        try:
            # Try to get active window title using xdotool
            try:
                result = subprocess.run(["xdotool", "getactivewindow", "getwindowname"],
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    return result.stdout.strip()
            except:
                pass

            # Fallback: try wmctrl
            try:
                result = subprocess.run(["wmctrl", "-l", "-G"],
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines:
                        parts = line.split()
                        if len(parts) >= 8:
                            # Check if this window is active (usually marked with '1' in desktop column)
                            if parts[1] == '1':
                                window_title = ' '.join(parts[7:])
                                return window_title
            except:
                pass

            return ""

        except Exception as e:
            self.logger.error(f"Failed to get window title on Linux: {e}", exc_info=True)
            return ""

"""
OpenAI Vision Locator (Gateway Version)
Uses gateway to call AI service for multimodal visual understanding with YOLO pre-screening.
"""

import base64
import logging
import json
import os
import tempfile
from typing import Optional, Tuple, Dict, Any
import cv2
import requests
from ultralytics import YOLO

from automation.screenshot_optimizer import ScreenshotOptimizer, ScreenshotInfo


class OpenAIVisionLocator:
    """Locate UI elements using OpenAI-compatible vision API with YOLO pre-screening"""

    def __init__(self, gateway_url: str = "", api_key: str = "", logger: logging.Logger = None):
        """
        Initialize OpenAI vision locator (gateway version)

        Args:
            gateway_url: Base URL for the gateway service
            api_key: API key for the gateway service
            logger: Logger instance
        """
        self.gateway_url = gateway_url.rstrip('/') if gateway_url else ""
        self.api_key = api_key
        self.logger = logger or logging.getLogger(__name__)
        self._screenshot_helper = None
        self._yolo_model = None

        # Initialize YOLO model for pre-screening
        self._init_yolo_model()

    def update_config(self, gateway_url: str, api_key: str):
        """Update vision locator configuration"""
        self.gateway_url = gateway_url.rstrip('/') if gateway_url else ""
        self.api_key = api_key
        self.logger.info(f"Vision locator configuration updated: gateway @ {self.gateway_url}")

    def set_screenshot_helper(self, screenshot_helper):
        """Set screenshot helper instance"""
        self._screenshot_helper = screenshot_helper

    def _init_yolo_model(self):
        """Initialize YOLO model for pre-screening"""
        try:
            # Use YOLOv8 nano model for fast pre-screening
            self._yolo_model = YOLO('yolov8n.pt')
            self.logger.info("YOLO model initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize YOLO model: {e}")
            self._yolo_model = None

    def _encode_image_to_base64(self, image_path: str) -> str:
        """Encode image to base64 string"""
        with open(image_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode("utf-8")

    def _call_gateway_vision(self, image_path: str, prompt: str) -> str:
        """
        Call gateway to access AI service for multimodal understanding

        Args:
            image_path: Path to the image to analyze
            prompt: Text prompt for the model

        Returns:
            Model's text response
        """
        try:
            image_b64 = self._encode_image_to_base64(image_path)

            headers = {
                "Content-Type": "application/json"
            }

            # Add API key if available
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            # Based on the servers_capabilities.json, the AI service has:
            # - analyze_content: 分析文本内容，提取关键信息和情感
            # - generate_text: 生成文本内容，支持多种风格和格式
            # We'll use analyze_content for vision tasks, passing the image as base64

            payload = {
                "content": f"[IMAGE_BASE64:{image_b64}] {prompt}",
                "analysis_type": "vision",
                "task": "object_detection"
            }

            # Call the AI service via gateway
            response = requests.post(
                f"{self.gateway_url}/ai/analyze_content",
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            resp_json = response.json()

            # Extract the result from the response
            # Based on typical API structure, the result might be in various fields
            if isinstance(resp_json, dict):
                # Try common response fields
                for field in ['result', 'content', 'text', 'analysis', 'output']:
                    if field in resp_json and isinstance(resp_json[field], str):
                        return resp_json[field]

                # If no string field found, return the whole JSON as string
                return json.dumps(resp_json, ensure_ascii=False)
            else:
                return str(resp_json)

        except Exception as e:
            self.logger.error(f"Gateway vision API call failed: {e}")
            raise

    def find_target_in_screenshot(self, screenshot_path: str, target_description: str) -> Tuple[Optional[Tuple[int, int, int, int]], str]:
        """
        Find target element in screenshot using YOLO pre-screening + OpenAI vision

        Args:
            screenshot_path: Path to the full screenshot
            target_description: Description of the target element to find

        Returns:
            Tuple of (bounding_box, result_message) where bounding_box is (x, y, width, height) or None
        """
        if not self._yolo_model:
            self.logger.error("YOLO model not available")
            return None, "YOLO model not initialized"

        if not self._screenshot_helper:
            self.logger.error("Screenshot helper not set")
            return None, "Screenshot helper not configured"

        try:
            # Step 1: YOLO pre-screening to get candidate regions
            self.logger.info(f"Running YOLO pre-screening for target: {target_description}")
            results = self._yolo_model(screenshot_path)

            # Extract bounding boxes from YOLO results
            if len(results) == 0 or len(results[0].boxes) == 0:
                self.logger.warning("YOLO detected no objects in screenshot")
                return None, "YOLO detected no objects"

            candidates = results[0].boxes.xyxy.cpu().numpy()
            self.logger.info(f"YOLO found {len(candidates)} candidate regions")

            image = cv2.imread(screenshot_path)
            if image is None:
                self.logger.error("Failed to read screenshot image")
                return None, "Failed to read screenshot"
            img_h, img_w = image.shape[:2]

            # Step 2: Process each candidate with OpenAI vision
            for i, bbox in enumerate(candidates):
                x1, y1, x2, y2 = bbox.astype(int)

                # Validate bounding box
                if x2 <= x1 or y2 <= y1:
                    self.logger.warning(f"Invalid bounding box from YOLO: {bbox}")
                    continue

                # Step 2a: Crop candidate region
                self.logger.debug(f"Processing candidate {i}: bbox={bbox}")
                crop = image[y1:y2, x1:x2]
                crop_h, crop_w = crop.shape[:2]
                if crop_h <= 0 or crop_w <= 0:
                    self.logger.warning(f"Empty crop for YOLO candidate {i}: bbox={bbox}")
                    continue
                tmp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                crop_path = tmp_file.name
                tmp_file.close()
                cv2.imwrite(crop_path, crop)

                # Step 2b: Ask OpenAI vision model
                prompt = (
                    f"请判断这张图片是否包含 {target_description}。"
                    f"如果是，请以 JSON 格式输出坐标，例如 {{\"x\": 0.1, \"y\": 0.2, \"w\": 0.3, \"h\": 0.4}}（相对坐标，0~1之间）。"
                    f"如果不是，请只回答 'no'。"
                )

                try:
                    response = self._call_gateway_vision(crop_path, prompt)
                    self.logger.debug(f"Gateway vision response for candidate {i}: {response}")

                    # Step 2c: Parse response
                    if "no" not in response.lower():
                        try:
                            # Try to extract JSON from response
                            start = response.find("{")
                            end = response.rfind("}") + 1
                            if start != -1 and end != 0:
                                json_str = response[start:end]
                                coord = json.loads(json_str)

                                # Convert coordinates returned for the cropped
                                # candidate back into full-screenshot pixels.
                                raw_x = float(coord["x"])
                                raw_y = float(coord["y"])
                                raw_w = float(coord["w"])
                                raw_h = float(coord["h"])
                                local_x = raw_x * crop_w if 0 <= raw_x <= 1 else raw_x
                                local_y = raw_y * crop_h if 0 <= raw_y <= 1 else raw_y
                                local_w = raw_w * crop_w if 0 <= raw_w <= 1 else raw_w
                                local_h = raw_h * crop_h if 0 <= raw_h <= 1 else raw_h
                                abs_x = int(x1 + local_x)
                                abs_y = int(y1 + local_y)
                                abs_w = int(local_w)
                                abs_h = int(local_h)

                                # Ensure coordinates are within image bounds
                                abs_x = max(0, min(abs_x, img_w))
                                abs_y = max(0, min(abs_y, img_h))
                                abs_w = max(1, min(abs_w, img_w - abs_x))
                                abs_h = max(1, min(abs_h, img_h - abs_y))

                                result_bbox = (abs_x, abs_y, abs_w, abs_h)
                                self.logger.info(f"Found target at absolute coordinates: {result_bbox}")
                                return result_bbox, response

                        except Exception as parse_error:
                            self.logger.warning(f"Failed to parse OpenAI response: {parse_error}")
                            # Fallback: return YOLO bbox if parsing fails
                            return (int(x1), int(y1), int(x2 - x1), int(y2 - y1)), response
                    else:
                        self.logger.debug(f"OpenAI vision model rejected candidate {i}")

                except Exception as vision_error:
                    self.logger.error(f"OpenAI vision API error for candidate {i}: {vision_error}")
                    continue
                finally:
                    try:
                        os.unlink(crop_path)
                    except OSError:
                        pass

            # If we get here, no candidates were accepted by the vision model
            self.logger.warning(f"No candidates matched target description: {target_description}")
            return None, "未找到目标 (No target found)"

        except Exception as e:
            self.logger.error(f"Error in find_target_in_screenshot: {e}", exc_info=True)
            return None, f"Error: {str(e)}"

    def locate_element_by_description(self, screenshot, target_description: str) -> Optional[Tuple[int, int]]:
        """
        Locate element center point by description using OpenAI vision

        Args:
            screenshot: Screenshot image (numpy array or PIL Image)
            target_description: Description of target element

        Returns:
            Tuple of (center_x, center_y) or None if not found
        """
        try:
            # Save screenshot to temporary file
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                temp_path = tmp_file.name

            # Convert screenshot to format suitable for OpenCV
            if hasattr(screenshot, 'save'):  # PIL Image
                screenshot.save(temp_path)
            else:  # Assume numpy array
                cv2.imwrite(temp_path, screenshot)

            # Find target using our method
            bbox, result_msg = self.find_target_in_screenshot(temp_path, target_description)

            # Clean up temp file
            try:
                os.unlink(temp_path)
            except:
                pass

            if bbox is None:
                self.logger.warning(f"Could not locate element: {result_msg}")
                return None

            # Return center point of bounding box
            x, y, w, h = bbox
            center_x = x + w // 2
            center_y = y + h // 2

            self.logger.info(f"Located element '{target_description}' at center ({center_x}, {center_y})")
            return (center_x, center_y)

        except Exception as e:
            self.logger.error(f"Error locating element by description: {e}", exc_info=True)
            return None

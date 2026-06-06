"""
Adaptive Element Locator

Provides robust UI element identification that adapts to interface changes:
- Multi-Modal Strategy: Combines accessibility APIs, OCR, template matching, and LLM visual understanding
- Self-Healing Capability: Automatically tries alternative locating methods when primary fails
- Confidence Scoring: Provides quantitative confidence metrics for identification reliability
- Learning Mechanism: Remembers and prioritizes successful locator strategies for future similar tasks
"""
import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from .interfaces import IAdaptiveElementLocator, ElementLocation
from .dependency_types import (
    MACOS_ADAPTER,
    WINDOWS_ADAPTER,
    ADAPTIVE_ELEMENT_LOCATOR
)


class AdaptiveElementLocator(IAdaptiveElementLocator):
    """Adaptive element locator with multi-modal strategies and learning capabilities"""

    def __init__(self, dependency_manager):
        self.dep_manager = dependency_manager
        self.logger = logging.getLogger("mcp-server-wechat-viewer-mcp.adaptive_locator")

        # Learned strategies cache: maps target descriptions to successful strategies
        self._learned_strategies: Dict[str, List[str]] = {}

        # Strategy priority order (can be adjusted based on learned data)
        self._default_strategy_order = ["accessibility", "ocr", "llm_vision", "openai_vision"]

        # Initializelocator
        self._logger = logging.getLogger(__name__)

    def locate_element(self,
                      target_description: str,
                      fallback_strategies: List[str] = None,
                      timeout: float = 10.0) -> Optional[ElementLocation]:
        """Locate a single element using adaptive strategies with fallback"""
        start_time = time.time()

        # Use learned strategies if available, otherwise use default order
        strategies_to_try = self._get_strategy_order(target_description, fallback_strategies)

        self.logger.debug(f"Locating element '{target_description}' using strategies: {strategies_to_try}")

        # Try each strategy in order until one succeeds or timeout
        for strategy in strategies_to_try:
            # Check if we've exceeded timeout
            if time.time() - start_time > timeout:
                self.logger.warning(f"Timeout exceeded while locating element '{target_description}'")
                break

            try:
                self.logger.debug(f"Trying strategy '{strategy}' for element '{target_description}'")
                location = self._locate_with_strategy(target_description, strategy)

                if location is not None:
                    # Calculate confidence based on strategy and historical success
                    confidence = self._calculate_confidence(strategy, target_description, location)

                    # Create ElementLocation with confidence and strategy info
                    element_location = ElementLocation(
                        x=location.get('x', 0),
                        y=location.get('y', 0),
                        width=location.get('width', 0),
                        height=location.get('height', 0),
                        confidence=confidence,
                        strategy_used=strategy,
                        element_id=location.get('element_id'),
                        element_name=location.get('element_name'),
                        metadata=location.get('metadata', {})
                    )

                    # Record this successful strategy for future use
                    self.record_successful_strategy(target_description, strategy, element_location)

                    self.logger.info(f"Successfully located element '{target_description}' using '{strategy}' "
                                   f"at ({element_location.x}, {element_location.y}) with confidence {confidence:.2f}")
                    return element_location

            except Exception as e:
                self.logger.debug(f"Strategy '{strategy}' failed for element '{target_description}': {e}")
                continue  # Try next strategy

        self.logger.warning(f"All strategies failed to locate element '{target_description}' within {timeout}s")
        return None

    def locate_elements(self,
                       target_description: str,
                       fallback_strategies: List[str] = None,
                       timeout: float = 10.0) -> List[ElementLocation]:
        """Locate multiple elements using adaptive strategies"""
        start_time = time.time()

        # Use learned strategies if available, otherwise use default order
        strategies_to_try = self._get_strategy_order(target_description, fallback_strategies)

        self.logger.debug(f"Locating elements '{target_description}' using strategies: {strategies_to_try}")

        all_elements = []

        # Try each strategy in order
        for strategy in strategies_to_try:
            # Check if we've exceeded timeout
            if time.time() - start_time > timeout:
                self.logger.warning(f"Timeout exceeded while locating elements '{target_description}'")
                break

            try:
                self.logger.debug(f"Trying strategy '{strategy}' for elements '{target_description}'")
                elements = self._locate_multiple_with_strategy(target_description, strategy)

                if elements:
                    # Calculate confidence for each element
                    for element in elements:
                        confidence = self._calculate_confidence(strategy, target_description, element)

                        element_location = ElementLocation(
                            x=element.get('x', 0),
                            y=element.get('y', 0),
                            width=element.get('width', 0),
                            height=element.get('height', 0),
                            confidence=confidence,
                            strategy_used=strategy,
                            element_id=element.get('element_id'),
                            element_name=element.get('element_name'),
                            metadata=element.get('metadata', {})
                        )
                        all_elements.append(element_location)

                    # If we found elements with this strategy, we might not need to try others
                    # depending on the use case - for now, we'll continue to try other strategies
                    # to potentially find more elements

            except Exception as e:
                self.logger.debug(f"Strategy '{strategy}' failed for elements '{target_description}': {e}")
                continue  # Try next strategy

        # Remove duplicates based on position proximity
        unique_elements = self._remove_duplicate_elements(all_elements)

        self.logger.info(f"Located {len(unique_elements)} elements for '{target_description}' "
                        f"using strategies: {[e.strategy_used for e in unique_elements]}")
        return unique_elements

    def record_successful_strategy(self,
                                  target_description: str,
                                  strategy_used: str,
                                  location: ElementLocation):
        """Record a successful element location strategy for future use"""
        if target_description not in self._learned_strategies:
            self._learned_strategies[target_description] = []

        # Add strategy to the list if not already present (maintain order of success)
        if strategy_used not in self._learned_strategies[target_description]:
            self._learned_strategies[target_description].append(strategy_used)
            self.logger.debug(f"Recorded successful strategy '{strategy_used}' for '{target_description}'")

        # Keep only the most recent strategies to prevent unbounded growth
        max_strategies_per_target = 10
        if len(self._learned_strategies[target_description]) > max_strategies_per_target:
            self._learned_strategies[target_description] = \
                self._learned_strategies[target_description][-max_strategies_per_target:]

    def get_learned_strategies(self) -> Dict[str, List[str]]:
        """Get learned element location strategies"""
        return self._learned_strategies.copy()

    # Private helper methods

    def _get_strategy_order(self, target_description: str,
                           fallback_strategies: List[str] = None) -> List[str]:
        """Determine the order of strategies to try for a target description"""
        # Start with learned strategies for this target if available
        if target_description in self._learned_strategies:
            learned_strategies = self._learned_strategies[target_description].copy()
        else:
            learned_strategies = []

        # Use fallback strategies if provided
        if fallback_strategies:
            strategies_to_try = learned_strategies + [s for s in fallback_strategies
                                                    if s not in learned_strategies]
        else:
            # Use default strategy order, adding any learned strategies at the front
            strategies_to_try = learned_strategies + [s for s in self._default_strategy_order
                                                    if s not in learned_strategies]

        # If fallback strategies were provided, also add any default strategies
        # that aren't already covered by learned or fallback strategies
        if fallback_strategies:
            additional_defaults = [s for s in self._default_strategy_order
                                 if s not in learned_strategies and s not in fallback_strategies]
            strategies_to_try.extend(additional_defaults)

        return strategies_to_try

    def _locate_with_strategy(self, target_description: str, strategy: str) -> Optional[Dict[str, Any]]:
        """Locate element using a specific strategy"""
        self.logger.debug(f"Attempting to locate '{target_description}' using strategy '{strategy}'")

        if strategy == "accessibility":
            return self._locate_via_accessibility(target_description)
        elif strategy == "ocr":
            return self._locate_via_ocr(target_description)
        elif strategy == "llm_vision":
            return self._locate_via_llm_vision(target_description)
        else:
            self.logger.warning(f"Unknown strategy: {strategy}")
            return None

    def _locate_multiple_with_strategy(self, target_description: str, strategy: str) -> List[Dict[str, Any]]:
        """Locate multiple elements using a specific strategy"""
        self.logger.debug(f"Attempting to locate multiple '{target_description}' using strategy '{strategy}'")

        if strategy == "accessibility":
            return self._locate_multiple_via_accessibility(target_description)
        elif strategy == "ocr":
            return self._locate_multiple_via_ocr(target_description)
        elif strategy == "llm_vision":
            return self._locate_multiple_via_llm_vision(target_description)
        else:
            self.logger.warning(f"Unknown strategy: {strategy}")
            return []

    def _calculate_confidence(self, strategy: str, target_description: str,
                            location_data: Dict[str, Any]) -> float:
        """Calculate confidence score for a located element"""
        # Base confidence by strategy type
        strategy_base_confidence = {
            "accessibility": 0.9,  # High confidence for accessibility API
            "ocr": 0.7,            # Medium confidence for OCR
            "llm_vision": 0.8,     # Good confidence for LLM vision
            "openai_vision": 0.85  # High confidence for OpenAI vision (better than local LLM)
        }

        base_confidence = strategy_base_confidence.get(strategy, 0.5)

        # Boost confidence if we've successfully used this strategy before for this target
        learned_boost = 0.0
        if target_description in self._learned_strategies:
            if strategy in self._learned_strategies[target_description]:
                # More recent successes get higher boost
                strategy_index = self._learned_strategies[target_description].index(strategy)
                recency_factor = (len(self._learned_strategies[target_description]) - strategy_index) / len(self._learned_strategies[target_description])
                learned_boost = 0.1 * recency_factor  # Up to 0.1 boost for recent successes

        # Calculate final confidence (capped at 1.0)
        final_confidence = min(1.0, base_confidence + learned_boost)

        # Apply any confidence modifier from the location data itself
        if 'confidence' in location_data:
            # If the underlying method provided a confidence, combine them
            method_confidence = location_data['confidence']
            final_confidence = (final_confidence + method_confidence) / 2

        return final_confidence

    def _remove_duplicate_elements(self, elements: List[ElementLocation]) -> List[ElementLocation]:
        """Remove duplicate elements based on proximity"""
        if not elements:
            return elements

        unique_elements = []
        proximity_threshold = 25  # pixels

        for element in elements:
            is_duplicate = False
            for unique_element in unique_elements:
                # Check if elements are close enough to be considered duplicates
                distance = ((element.x - unique_element.x) ** 2 +
                           (element.y - unique_element.y) ** 2) ** 0.5
                if distance < proximity_threshold:
                    is_duplicate = True
                    # Keep the one with higher confidence
                    if element.confidence > unique_element.confidence:
                        unique_elements.remove(unique_element)
                        unique_elements.append(element)
                    break

            if not is_duplicate:
                unique_elements.append(element)

        return unique_elements

    # Strategy implementations (placeholders - would be implemented with actual APIs)

    def _locate_via_accessibility(self, target_description: str) -> Optional[Dict[str, Any]]:
        """Locate element using accessibility APIs"""
        self.logger.debug(f"Attempting accessibility-based lookup for: {target_description}")

        try:
            # Get the appropriate platform adapter
            import platform
            platform_name = platform.system().lower()
            
            adapter_key = MACOS_ADAPTER if platform_name == "darwin" else WINDOWS_ADAPTER
            adapter = self.dep_manager.get_dependency(adapter_key)
            
            if not adapter:
                self.logger.warning(f"Platform adapter '{adapter_key}' not available for accessibility lookup")
                return None
                
            # Try to find by name/label
            location = adapter.find_element_by_name(target_description)
            if location:
                return {
                    'x': location.x,
                    'y': location.y,
                    'width': location.width,
                    'height': location.height,
                    'confidence': location.confidence,
                    'strategy_used': 'accessibility',
                    'element_name': location.element_name,
                    'element_id': location.element_id,
                    'metadata': location.metadata
                }
                
            return None
        except Exception as e:
            self.logger.error(f"Accessibility lookup failed for '{target_description}': {e}")
            return None

    def _locate_multiple_via_accessibility(self, target_description: str) -> List[Dict[str, Any]]:
        """Locate multiple elements using accessibility APIs"""
        # Not fully implemented yet, but could use adapter.find_elements_by_type etc.
        location = self._locate_via_accessibility(target_description)
        return [location] if location else []

    def _locate_via_ocr(self, target_description: str) -> Optional[Dict[str, Any]]:
        """Locate element using OCR text matching"""
        self.logger.debug(f"Attempting OCR-based lookup for: {target_description}")

        try:
            from .dependency_types import OCR_PROCESSOR
            ocr_processor = self.dep_manager.get_dependency(OCR_PROCESSOR)
            
            if not ocr_processor:
                self.logger.warning("OCR processor not available")
                return None
                
            # 1. Capture screenshot
            screenshot = ocr_processor.capture_screenshot()
            if not screenshot:
                return None
                
            # 2. Find text in image
            results = ocr_processor.find_text_in_image(screenshot, target_description)
            
            if results:
                # Use the best match
                best_match = results[0]
                pos = best_match['position']
                return {
                    'x': pos['x'] + pos['width'] // 2, # Center point
                    'y': pos['y'] + pos['height'] // 2,
                    'width': pos['width'],
                    'height': pos['height'],
                    'confidence': best_match['confidence'] / 100.0,
                    'strategy_used': 'ocr',
                    'element_name': best_match['text']
                }
                
            return None
        except Exception as e:
            self.logger.error(f"OCR lookup failed for '{target_description}': {e}")
            return None

    def _locate_multiple_via_ocr(self, target_description: str) -> List[Dict[str, Any]]:
        """Locate multiple elements using OCR text matching"""
        try:
            from .dependency_types import OCR_PROCESSOR
            ocr_processor = self.dep_manager.get_dependency(OCR_PROCESSOR)
            if not ocr_processor: return []
            
            screenshot = ocr_processor.capture_screenshot()
            if not screenshot: return []
            
            results = ocr_processor.find_text_in_image(screenshot, target_description)
            return [{
                'x': r['position']['x'] + r['position']['width'] // 2,
                'y': r['position']['y'] + r['position']['height'] // 2,
                'width': r['position']['width'],
                'height': r['position']['height'],
                'confidence': r['confidence'] / 100.0,
                'strategy_used': 'ocr',
                'element_name': r['text']
            } for r in results]
        except:
            return []

    def _locate_via_llm_vision(self, target_description: str) -> Optional[Dict[str, Any]]:
        """Locate element using LLM visual understanding"""
        self.logger.debug(f"Attempting LLM vision-based lookup for: {target_description}")

        try:
            from .dependency_types import CROSS_PLATFORM_AUTOMATION_ENGINE
            engine = self.dep_manager.get_dependency(CROSS_PLATFORM_AUTOMATION_ENGINE)
            
            if not engine or not hasattr(engine, 'llm_client'):
                return None
                
            # Capture screenshot
            screenshot = engine.capture_screenshot()
            if not screenshot: return None
            
            # This would call the LLM to find coordinates
            # For now, return None as LLM vision is secondary
            return None
        except:
            return None

    def _locate_multiple_via_llm_vision(self, target_description: str) -> List[Dict[str, Any]]:
        """Locate multiple elements using LLM visual understanding"""
        return []

    def _locate_via_openai_vision(self, target_description: str) -> Optional[Dict[str, Any]]:
        """Locate element using OpenAI vision with YOLO pre-screening"""
        self.logger.debug(f"Attempting OpenAI vision-based lookup for: {target_description}")

        try:
            from .dependency_types import OPENAI_VISION_LOCATOR
            openai_locator = self.dep_manager.get_dependency(OPENAI_VISION_LOCATOR)

            if not openai_locator:
                self.logger.warning("OpenAI vision locator not available")
                return None

            # Set screenshot helper if not already set
            if not hasattr(openai_locator, '_screenshot_helper') or not openai_locator._screenshot_helper:
                # Try to get screenshot helper from OCR processor or create a simple one
                try:
                    from .dependency_types import OCR_PROCESSOR
                    ocr_processor = self.dep_manager.get_dependency(OCR_PROCESSOR)
                    if ocr_processor:
                        # Create a simple screenshot helper that uses the OCR processor
                        class SimpleScreenshotHelper:
                            def __init__(self, ocr_proc):
                                self.ocr_processor = ocr_proc

                            def screenshot_to_base64(self, screenshot):
                                import base64
                                from PIL import Image
                                import io
                                if hasattr(screenshot, 'save'):  # PIL Image
                                    buffer = io.BytesIO()
                                    screenshot.save(buffer, format='PNG')
                                    return base64.b64encode(buffer.getvalue()).decode('utf-8')
                                else:  # numpy array
                                    img = Image.fromarray(screenshot)
                                    buffer = io.BytesIO()
                                    img.save(buffer, format='PNG')
                                    return base64.b64encode(buffer.getvalue()).decode('utf-8')
                                return ""

                        openai_locator._screenshot_helper = SimpleScreenshotHelper(ocr_processor)
                except Exception as e:
                    self.logger.warning(f"Could not set up screenshot helper for OpenAI vision: {e}")

            # Capture screenshot using the locator's helper or fallback to direct capture
            screenshot = None
            if hasattr(openai_locator, '_screenshot_helper') and openai_locator._screenshot_helper:
                # This approach is more complex, let's use the OCR processor directly for simplicity
                pass

            # Fallback: use OCR processor to capture screenshot
            from .dependency_types import OCR_PROCESSOR
            ocr_processor = self.dep_manager.get_dependency(OCR_PROCESSOR)
            if not ocr_processor:
                self.logger.warning("OCR processor not available for screenshot capture")
                return None

            screenshot = ocr_processor.capture_screenshot()
            if not screenshot:
                self.logger.warning("Could not capture screenshot for OpenAI vision")
                return None

            # Save screenshot to temporary file
            import tempfile
            import os
            import cv2

            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                temp_path = tmp_file.name

            # Convert screenshot to format suitable for OpenCV if needed
            if hasattr(screenshot, 'save'):  # PIL Image
                screenshot.save(temp_path)
            else:  # Assume numpy array
                cv2.imwrite(temp_path, screenshot)

            # Find target using OpenAI vision
            bbox, result_msg = openai_locator.find_target_in_screenshot(temp_path, target_description)

            # Clean up temp file
            try:
                os.unlink(temp_path)
            except:
                pass

            if bbox is None:
                self.logger.warning(f"OpenAI vision could not locate element: {result_msg}")
                return None

            # Return center point and dimensions
            x, y, w, h = bbox
            return {
                'x': x,
                'y': y,
                'width': w,
                'height': h,
                'confidence': 0.85,  # Good confidence for OpenAI vision
                'strategy_used': 'openai_vision',
                'element_name': target_description,
                'metadata': {'result_msg': result_msg}
            }

        except Exception as e:
            self.logger.error(f"OpenAI vision lookup failed for '{target_description}': {e}")
            return None

    def _locate_multiple_via_openai_vision(self, target_description: str) -> List[Dict[str, Any]]:
        """Locate multiple elements using OpenAI vision with YOLO pre-screening"""
        # For now, single element localization is sufficient
        # Multiple element detection would require modifications to the vision prompt
        location = self._locate_via_openai_vision(target_description)
        return [location] if location else []
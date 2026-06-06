"""
Unified Element Locator Service

A unified service that combines multiple element location strategies:
    1. Playwright + CDP (PRIMARY) - Web-based DOM element extraction
    2. YOLO + AI (fallback) - Vision-based element detection
    3. OCR (fallback) - Text-based element location
    4. Heuristic (fallback) - Rule-based element location

Architecture:
    CDP Strategy → YOLO Pre-screening → Multimodal AI Judgment → OCR → Heuristic

Error Handling:
    - Circuit breaker pattern for AI service failures
    - Fallback chain: CDP → YOLO+AI → OCR → Heuristic → Cached
    - Graceful degradation for all external dependencies
"""
import asyncio
import base64
import inspect
import io
import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Any

try:
    import numpy as np
    import ultralytics
    YOLO_AVAILABLE = True
except ImportError as _yolo_import_error:  # pragma: no cover - env-gated
    np = None
    ultralytics = None
    YOLO_AVAILABLE = False

try:
    from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from PIL import Image

try:
    from shared.computer_use import ComputerUseFallbackPromptBuilder
except ImportError:
    try:
        from dataproai.src.servers.shared.computer_use import (
            ComputerUseFallbackPromptBuilder,
        )
    except ImportError:
        ComputerUseFallbackPromptBuilder = None


class LocatorStrategy(Enum):
    """Locator strategy types - ordered by priority (highest to lowest)"""
    PLAYWRIGHT_CDP = "playwright_cdp"  # Web-based via CDP (PRIMARY)
    YOLO_AI = "yolo_ai"               # Vision-based AI (secondary)
    OCR = "ocr"                        # OCR-based fallback
    HEURISTIC = "heuristic"            # Heuristic-based fallback
    CACHED = "cached"                  # Cached result fallback


class LocatorConfidence(Enum):
    """Result confidence levels"""
    HIGH = "high"      # Playwright + CDP or YOLO+AI with high confidence
    MEDIUM = "medium"  # OCR fallback
    LOW = "low"        # Heuristic fallback
    NONE = "none"      # No result found


@dataclass(frozen=True)
class BoundingBox:
    """Immutable bounding box representation"""
    x: int
    y: int
    width: int
    height: int

    @property
    def center(self) -> tuple[int, int]:
        """Get center coordinates"""
        return (self.x + self.width // 2, self.y + self.height // 2)

    def contains(self, x: int, y: int) -> bool:
        """Check if point is inside box"""
        return self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height


@dataclass(frozen=True)
class ElementLocation:
    """Immutable element location result"""
    bbox: BoundingBox
    confidence: LocatorConfidence
    strategy_used: LocatorStrategy
    description: str
    metadata: dict


@dataclass
class LocatorConfig:
    cdp_port: int = 9222
    yolo_confidence_threshold: float = 0.5
    yolo_model_path: str = "yolov8n.pt"
    yolo_max_candidates: int = 10
    ai_timeout_seconds: int = 30
    ai_retry_count: int = 3
    ai_confidence_threshold: float = 0.7
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout_seconds: int = 60
    enable_ocr_fallback: bool = True
    enable_heuristic_fallback: bool = True
    enable_cache: bool = True
    cache_ttl_seconds: int = 300


class CircuitBreaker:
    """Circuit breaker for external service calls"""

    def __init__(self, threshold: int, timeout: int, logger: logging.Logger):
        self._threshold = threshold
        self._timeout = timeout
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._logger = logger
        self._lock = asyncio.Lock()

    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        async with self._lock:
            if self._is_open():
                raise CircuitBreakerOpenError("Circuit breaker is open")

        try:
            result = await func(*args, **kwargs)
            await self._record_success()
            return result
        except Exception as e:
            await self._record_failure()
            raise

    def _is_open(self) -> bool:
        """Check if circuit breaker is open"""
        if self._failure_count >= self._threshold:
            if self._last_failure_time:
                import time
                if time.time() - self._last_failure_time > self._timeout:
                    self._logger.info("Circuit breaker timeout reset")
                    self._failure_count = 0
                    return False
            return True
        return False

    async def _record_success(self):
        """Record successful call"""
        async with self._lock:
            self._failure_count = 0

    async def _record_failure(self):
        """Record failed call"""
        import time
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            self._logger.warning(f"Circuit breaker failures: {self._failure_count}/{self._threshold}")


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


class PlaywrightLocator:
    """Playwright + CDP based element locator - PRIMARY strategy"""

    def __init__(self, config: LocatorConfig, logger: logging.Logger):
        self._config = config
        self._logger = logger
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self._initialized = False
        self._cdp_port = config.cdp_port if hasattr(config, 'cdp_port') else 9222

    async def initialize(self) -> bool:
        if not PLAYWRIGHT_AVAILABLE:
            self._logger.warning("Playwright not available")
            return False

        if self._initialized:
            return True

        try:
            self._playwright = await async_playwright().start()
            cdp_url = f"ws://127.0.0.1:{self._cdp_port}/devtools/browser"
            self._logger.info(f"Connecting to browser via CDP: {cdp_url}")
            self._browser = await self._playwright.chromium.connect_over_cdp(cdp_url)
            contexts = self._browser.contexts
            if contexts:
                self._page = await contexts[0].new_page()
                self._initialized = True
                self._logger.info("Playwright CDP connected successfully")
                return True
            await self._browser.close()
        except Exception as e:
            self._logger.warning(f"CDP connection failed: {e}")

        return False

    async def locate_element(
        self,
        selector: str,
        element_hint: str,
    ) -> Optional[ElementLocation]:
        if not self._initialized or not self._page:
            return None

        try:
            self._logger.info(f"CDP locate: {selector} ({element_hint})")
            element = await self._page.wait_for_selector(selector, timeout=5000)
            if element:
                box = await element.bounding_box()
                if box:
                    bbox = BoundingBox(
                        x=int(box.get("x", 0)),
                        y=int(box.get("y", 0)),
                        width=int(box.get("width", 100)),
                        height=int(box.get("height", 30)),
                    )
                    return ElementLocation(
                        bbox=bbox,
                        confidence=LocatorConfidence.HIGH,
                        strategy_used=LocatorStrategy.PLAYWRIGHT_CDP,
                        description=f"Element '{element_hint}' found via CDP",
                        metadata={"selector": selector},
                    )
        except PlaywrightTimeout:
            self._logger.debug(f"Timeout waiting for: {selector}")
        except Exception as e:
            self._logger.error(f"CDP locate failed: {e}")

        return None

    async def extract_content(self, selector: str) -> Optional[dict]:
        if not self._initialized or not self._page:
            return None

        try:
            element = await self._page.query_selector(selector)
            if not element:
                return None

            inner_html = await element.evaluate("el => el.innerHTML")
            inner_text = await element.evaluate("el => el.innerText")
            outer_html = await element.evaluate("el => el.outerHTML")

            return {
                "html": inner_html,
                "text": inner_text,
                "outer_html": outer_html,
            }
        except Exception as e:
            self._logger.error(f"CDP extract failed: {e}")

        return None

    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._initialized = False


class YOLOPrescreen:
    """YOLO pre-screening for candidate element detection"""

    def __init__(self, config: LocatorConfig, logger: logging.Logger):
        self._config = config
        self._logger = logger
        self._model = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize YOLO model.

        YOLO is optional for native-app automation. If it is not installed,
        the locator still has OCR and heuristic fallbacks.
        """
        if self._initialized:
            return True

        if not YOLO_AVAILABLE:
            self._logger.warning(
                "YOLO dependencies unavailable; UnifiedElementLocator will use OCR/heuristic fallbacks"
            )
            return False

        self._logger.info(f"Loading YOLO model: {self._config.yolo_model_path}")
        try:
            self._model = ultralytics.YOLO(self._config.yolo_model_path)
        except Exception as exc:
            self._logger.error(f"Failed to load YOLO model: {exc}")
            raise
        self._initialized = True
        self._logger.info("YOLO model loaded successfully")
        return True

    async def detect_candidates(
        self,
        screenshot: Image.Image,
        element_hint: str,
    ) -> list[BoundingBox]:
        """Detect candidate regions in screenshot

        Args:
            screenshot: PIL Image of the screen
            element_hint: Hint about what to find (e.g., "button", "search bar")

        Returns:
            List of candidate bounding boxes
        """
        if not self._initialized or not self._model:
            return []

        try:
            results = self._model(
                screenshot,
                conf=self._config.yolo_confidence_threshold,
                verbose=False,
            )

            candidates = []
            for result in results:
                boxes = result.boxes
                if boxes is None:
                    continue

                for box in boxes:
                    # Get box coordinates
                    xyxy = box.xyxy[0].cpu().numpy()
                    x1, y1, x2, y2 = map(int, xyxy)

                    candidates.append(BoundingBox(
                        x=x1,
                        y=y1,
                        width=x2 - x1,
                        height=y2 - y1,
                    ))

                    if len(candidates) >= self._config.yolo_max_candidates:
                        break

            self._logger.info(f"YOLO detected {len(candidates)} candidates")
            return candidates[:self._config.yolo_max_candidates]

        except Exception as e:
            self._logger.error(f"YOLO detection failed: {e}")
            return []


class MultimodalJudge:
    """Multimodal AI judgment for precise element location."""

    def __init__(
        self,
        config: LocatorConfig,
        logger: logging.Logger,
        ai_client=None,
    ):
        self._config = config
        self._logger = logger
        self._ai_client = ai_client
        self._circuit_breaker = CircuitBreaker(
            threshold=config.circuit_breaker_threshold,
            timeout=config.circuit_breaker_timeout_seconds,
            logger=logger,
        )

    async def judge_element(
        self,
        screenshot: Image.Image,
        candidates: list[BoundingBox],
        element_hint: str,
    ) -> Optional[ElementLocation]:
        """Judge which candidate is the correct element."""
        if not candidates:
            return None

        if self._ai_client is None:
            self._logger.warning("AI client not configured, skipping YOLO+AI judgment")
            return None

        try:
            ai_callable = self._get_ai_callable()
            if ai_callable is None:
                self._logger.warning("AI client does not support multimodal element judgment API")
                return None

            result = await self._circuit_breaker.call(
                ai_callable,
                screenshot,
                candidates,
                element_hint,
            )
            if result:
                return ElementLocation(
                    bbox=result["bbox"],
                    confidence=LocatorConfidence.HIGH,
                    strategy_used=LocatorStrategy.YOLO_AI,
                    description=result.get("description", f"Element '{element_hint}' found"),
                    metadata={"candidates_evaluated": len(candidates)},
                )
        except CircuitBreakerOpenError:
            self._logger.warning("Circuit breaker open for AI judgment")
        except Exception as e:
            self._logger.error(f"AI judgment failed: {e}")

        return None

    def _get_ai_callable(self):
        """Resolve the AI judgment entrypoint from the injected client."""
        if hasattr(self._ai_client, "judge_element"):
            return self._ai_client.judge_element
        # Prefer the explicit compatibility path over the old alias when only
        # the legacy screenshot-analysis contract is available.
        if hasattr(self._ai_client, "legacy_visual_fallback"):
            return self._judge_with_multimodal_api
        if hasattr(self._ai_client, "analyze_screenshot"):
            return self._judge_with_multimodal_api
        return None

    async def _judge_with_multimodal_api(
        self,
        screenshot: Image.Image,
        candidates: list[BoundingBox],
        element_hint: str,
    ) -> Optional[dict]:
        """Use the legacy visual fallback contract to pick the best YOLO candidate."""
        screenshot_b64 = self._encode_screenshot(screenshot)
        if not screenshot_b64:
            self._logger.error("Failed to encode screenshot for multimodal AI judgment")
            return None

        prompt = self._build_candidate_prompt(candidates, element_hint, screenshot.size)
        if hasattr(self._ai_client, "legacy_visual_fallback"):
            response = await self._ai_client.legacy_visual_fallback(prompt, screenshot_b64)
        else:
            response = await self._ai_client.analyze_screenshot(prompt, screenshot_b64)
        parsed = self._parse_ai_response(response)
        if not parsed:
            self._logger.warning("Multimodal AI returned no usable candidate selection")
            return None

        candidate_index = parsed.get("candidate_index")
        if not isinstance(candidate_index, int) or not (0 <= candidate_index < len(candidates)):
            self._logger.warning(
                "Multimodal AI returned invalid candidate index %r for %d candidates",
                candidate_index,
                len(candidates),
            )
            return None

        bbox = candidates[candidate_index]
        description = parsed.get("description", f"Element '{element_hint}' selected by multimodal AI")
        return {
            "bbox": bbox,
            "description": description,
        }

    def _encode_screenshot(self, screenshot: Image.Image) -> Optional[str]:
        try:
            image = screenshot if isinstance(screenshot, Image.Image) else Image.fromarray(screenshot)
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
        except Exception as exc:
            self._logger.error("Failed to encode screenshot for AI judge: %s", exc)
            return None

    def _build_candidate_prompt(
        self,
        candidates: list[BoundingBox],
        element_hint: str,
        image_size: tuple[int, int],
    ) -> str:
        candidate_lines = []
        for index, candidate in enumerate(candidates):
            candidate_lines.append(
                f"{index}: x={candidate.x}, y={candidate.y}, width={candidate.width}, height={candidate.height}, center={candidate.center}"
            )
        candidate_text = "\n".join(candidate_lines)
        if ComputerUseFallbackPromptBuilder:
            return ComputerUseFallbackPromptBuilder.build_yolo_candidate_judgment_prompt(
                candidate_text=candidate_text,
                element_hint=element_hint,
                image_size=image_size,
            )
        return f"目标元素: {element_hint}\n{candidate_text}"

    def _parse_ai_response(self, response: Any) -> Optional[dict]:
        if response is None:
            return None
        if isinstance(response, dict):
            return response
        if isinstance(response, str):
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                self._logger.warning("Failed to parse multimodal AI string response as JSON: %r", response[:200])
                return None
        return None


class OCRFallback:
    """OCR-based fallback for element location."""

    def __init__(
        self,
        logger: logging.Logger,
        ocr_processor=None,
    ):
        self._logger = logger
        self._ocr_processor = ocr_processor

    async def locate_element(
        self,
        screenshot: Image.Image,
        element_hint: str,
    ) -> Optional[ElementLocation]:
        """Locate element using OCR."""
        if self._ocr_processor is None:
            self._logger.warning("OCR processor not available")
            return None

        try:
            self._logger.info(f"OCR fallback for: {element_hint}")
            try:
                result = self._ocr_processor.find_text(
                    screenshot,
                    element_hint,
                    fuzzy_match=True,
                )
            except TypeError:
                result = self._ocr_processor.find_text(screenshot, element_hint)
            if inspect.isawaitable(result):
                result = await result
            if result:
                if isinstance(result, list):
                    result = result[0] if result else None
                if result is None:
                    return None
                bbox = BoundingBox(
                    x=result.get("x", 0),
                    y=result.get("y", 0),
                    width=result.get("width", 100),
                    height=result.get("height", 30),
                )
                return ElementLocation(
                    bbox=bbox,
                    confidence=LocatorConfidence.MEDIUM,
                    strategy_used=LocatorStrategy.OCR,
                    description=f"Element '{element_hint}' found via OCR",
                    metadata={"text": result.get("text", "")},
                )
        except Exception as e:
            self._logger.error(f"OCR fallback failed: {e}")

        return None


class HeuristicFallback:
    """Heuristic-based fallback for element location."""

    _COMMON_PATTERNS = {
        "搜索框": {"x_ratio": 0.50, "y_ratio": 0.09, "width_ratio": 0.42, "height_ratio": 0.06},
        "搜索按钮": {"x_ratio": 0.90, "y_ratio": 0.09, "width_ratio": 0.08, "height_ratio": 0.06},
        "发送按钮": {"x_ratio": 0.92, "y_ratio": 0.94, "width_ratio": 0.10, "height_ratio": 0.05},
        "公众号结果": {"x_ratio": 0.50, "y_ratio": 0.24, "width_ratio": 0.72, "height_ratio": 0.08},
        "文章列表": {"x_ratio": 0.50, "y_ratio": 0.45, "width_ratio": 0.88, "height_ratio": 0.72},
    }

    def __init__(self, logger: logging.Logger):
        self._logger = logger

    async def locate_element(
        self,
        screenshot: Image.Image,
        element_hint: str,
    ) -> Optional[ElementLocation]:
        """Locate element using heuristics"""
        self._logger.info(f"Heuristic fallback for: {element_hint}")
        width, height = screenshot.size
        pattern = self._COMMON_PATTERNS.get(element_hint)
        if not pattern:
            self._logger.warning(f"No heuristic pattern defined for: {element_hint}")
            return None

        box_width = max(60, int(width * pattern["width_ratio"]))
        box_height = max(24, int(height * pattern["height_ratio"]))
        center_x = int(width * pattern["x_ratio"])
        center_y = int(height * pattern["y_ratio"])
        bbox = BoundingBox(
            x=max(0, center_x - box_width // 2),
            y=max(0, center_y - box_height // 2),
            width=box_width,
            height=box_height,
        )
        return ElementLocation(
            bbox=bbox,
            confidence=LocatorConfidence.LOW,
            strategy_used=LocatorStrategy.HEURISTIC,
            description=f"Element '{element_hint}' estimated via heuristic",
            metadata={"pattern": pattern},
        )


class ResultCache:
    """Cache for element location results"""

    def __init__(self, ttl_seconds: int, logger: logging.Logger):
        self._ttl = ttl_seconds
        self._logger = logger
        self._cache: dict = {}

    def _make_key(self, screenshot_hash: int, element_hint: str) -> str:
        """Generate cache key"""
        return f"{screenshot_hash}:{element_hint}"

    def get(
        self,
        screenshot_hash: int,
        element_hint: str,
    ) -> Optional[ElementLocation]:
        """Get cached result"""
        import time

        key = self._make_key(screenshot_hash, element_hint)
        entry = self._cache.get(key)

        if entry:
            result, timestamp = entry
            if time.time() - timestamp < self._ttl:
                self._logger.debug("Cache hit")
                return result
            else:
                del self._cache[key]

        return None

    def set(
        self,
        screenshot_hash: int,
        element_hint: str,
        result: ElementLocation,
    ) -> None:
        """Cache result"""
        import time

        key = self._make_key(screenshot_hash, element_hint)
        self._cache[key] = (result, time.time())
        self._logger.debug("Result cached")


class UnifiedElementLocator:
    """
    Unified Element Locator Service

    Provides a single interface for all element location needs with
    automatic fallback chain: CDP → YOLO+AI → OCR → Heuristic → Cached
    """

    def __init__(
        self,
        config: Optional[LocatorConfig] = None,
        logger: Optional[logging.Logger] = None,
        ocr_processor=None,
        ai_client=None,
    ):
        self._config = config or LocatorConfig()
        self._logger = logger or logging.getLogger(__name__)

        self._playwright_locator = PlaywrightLocator(self._config, self._logger)
        self._yolo = YOLOPrescreen(self._config, self._logger)
        self._judge = MultimodalJudge(self._config, self._logger, ai_client=ai_client)
        self._ocr_fallback = OCRFallback(self._logger, ocr_processor=ocr_processor)
        self._heuristic_fallback = HeuristicFallback(self._logger)

        if self._config.enable_cache:
            self._cache = ResultCache(self._config.cache_ttl_seconds, self._logger)
        else:
            self._cache = None

    async def initialize(self) -> bool:
        """Initialize the locator service.

        CDP and YOLO are optional for native-app automation. Failures there
        should not prevent OCR/search-bar specific fallbacks from running.
        """
        self._logger.info("Initializing UnifiedElementLocator")

        cdp_ok = await self._playwright_locator.initialize()
        if not cdp_ok:
            self._logger.warning("CDP initialization failed, locator will start from YOLO+AI")

        yolo_ok = await self._yolo.initialize()
        if not yolo_ok:
            self._logger.warning("YOLO initialization skipped; locator will use OCR/heuristic fallbacks")

        self._logger.info("UnifiedElementLocator initialized")
        return True

    def set_ai_client(self, ai_client) -> None:
        """Inject or replace the multimodal AI client used by YOLO judgment."""
        self._judge = MultimodalJudge(self._config, self._logger, ai_client=ai_client)

    def set_ocr_processor(self, ocr_processor) -> None:
        """Inject or replace the OCR processor used by OCR fallback."""
        self._ocr_fallback = OCRFallback(self._logger, ocr_processor=ocr_processor)

    async def locate_element(
        self,
        screenshot: Image.Image,
        element_hint: str,
        selector: Optional[str] = None,
    ) -> Optional[ElementLocation]:
        """
        Locate element in screenshot using the full pipeline

        Args:
            screenshot: PIL Image of the screen
            element_hint: Hint about what to find (e.g., "搜索框", "搜索按钮")
            selector: CSS/XPath selector for CDP (PRIMARY strategy)

        Returns:
            ElementLocation if found, None otherwise
        """
        import hashlib

        screenshot_bytes = screenshot.tobytes()
        screenshot_hash = int(hashlib.md5(screenshot_bytes).hexdigest(), 16)

        if self._cache:
            cached = self._cache.get(screenshot_hash, element_hint)
            if cached:
                self._logger.info("Using cached result")
                return cached

        if selector:
            result = await self._playwright_locator.locate_element(selector, element_hint)
            if result:
                self._cache_and_return(result, screenshot_hash, element_hint)
                return result

        result = await self._locate_with_yolo_ai(screenshot, element_hint)
        if result:
            self._cache_and_return(result, screenshot_hash, element_hint)
            return result

        if self._config.enable_ocr_fallback:
            result = await self._ocr_fallback.locate_element(screenshot, element_hint)
            if result:
                self._cache_and_return(result, screenshot_hash, element_hint)
                return result

        if self._config.enable_heuristic_fallback:
            result = await self._heuristic_fallback.locate_element(screenshot, element_hint)
            if result:
                self._cache_and_return(result, screenshot_hash, element_hint)
                return result

        self._logger.warning(f"Could not locate element: {element_hint}")
        return None

    async def _locate_with_yolo_ai(
        self,
        screenshot: Image.Image,
        element_hint: str,
    ) -> Optional[ElementLocation]:
        """Locate using YOLO + AI judgment"""
        self._logger.info(f"YOLO+AI pipeline for: {element_hint}")

        candidates = await self._yolo.detect_candidates(screenshot, element_hint)

        if not candidates:
            self._logger.info("No YOLO candidates, trying fallback")
            return None

        try:
            result = await self._judge.judge_element(
                screenshot, candidates, element_hint
            )
            if result:
                self._logger.info(f"AI judgment successful: {result.description}")
                return result
        except CircuitBreakerOpenError:
            self._logger.warning("Circuit breaker open, falling back")

        return None

    def _cache_and_return(
        self,
        result: ElementLocation,
        screenshot_hash: int,
        element_hint: str,
    ) -> ElementLocation:
        """Cache result and return"""
        if self._cache:
            self._cache.set(screenshot_hash, element_hint, result)
        return result

    async def locate_elements(
        self,
        screenshot: Image.Image,
        element_hint: str,
    ) -> list[ElementLocation]:
        """Locate multiple elements in screenshot"""
        # For now, return single result wrapped in list
        result = await self.locate_element(screenshot, element_hint)
        return [result] if result else []

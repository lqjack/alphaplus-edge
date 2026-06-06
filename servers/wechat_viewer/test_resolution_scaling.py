import asyncio
import logging
import importlib
from pathlib import Path
import sys
import types

from PIL import Image

WECHAT_VIEWER_ROOT = Path(__file__).resolve().parent
wechat_viewer_root_str = str(WECHAT_VIEWER_ROOT)
if wechat_viewer_root_str not in sys.path:
    sys.path.insert(0, wechat_viewer_root_str)

automation_package = types.ModuleType("automation")
automation_package.__path__ = [str(WECHAT_VIEWER_ROOT / "automation")]
sys.modules["automation"] = automation_package

sys.modules["mcp_core"] = importlib.import_module(
    "dataproai.src.servers.wechat_viewer.mcp_core"
)

from .automation.wechat_automation import WeChatAutomation
from .mcp_core.ocr_processor import OCRProcessor as CoreOCRProcessor


class _FakePyAutoGUI:
    def __init__(self, logical_size, screenshot_size):
        self._logical_size = logical_size
        self._screenshot_size = screenshot_size
        self.last_region = None

    def size(self):
        return self._logical_size

    def screenshot(self, region=None):
        self.last_region = region
        return Image.new("RGB", self._screenshot_size, color="white")


class _FakeDepManager:
    def __init__(self, mapping):
        self._mapping = mapping

    def get_dependency(self, name):
        return self._mapping.get(name)


def _automation_with_pyautogui(pyautogui):
    automation = WeChatAutomation.__new__(WeChatAutomation)
    automation.dep_manager = _FakeDepManager({"pyautogui": pyautogui})
    automation.logger = logging.getLogger("wechat-viewer-test")
    return automation


class _FakeOCRCapture:
    def capture_screenshot(self, region=None):
        return Image.new("RGB", (400, 400), color="white")


def test_capture_screenshot_attaches_logical_region_metadata():
    pyautogui = _FakePyAutoGUI((1512, 982), (600, 300))
    processor = CoreOCRProcessor(_FakeDepManager({"pyautogui": pyautogui}))

    screenshot = processor.capture_screenshot((10, 20, 300, 150))

    assert screenshot is not None
    assert screenshot.info["_logical_capture_region"] == {
        "X": 10,
        "Y": 20,
        "Width": 300,
        "Height": 150,
    }
    assert screenshot.info["_screen_logical_size"] == {"Width": 1512, "Height": 982}


def test_get_screenshot_scale_prefers_region_metadata_for_retina_regions():
    pyautogui = _FakePyAutoGUI((1512, 982), (600, 300))
    automation = _automation_with_pyautogui(pyautogui)
    screenshot = Image.new("RGB", (600, 300), color="white")
    screenshot.info["_logical_capture_region"] = {
        "X": 10,
        "Y": 20,
        "Width": 300,
        "Height": 150,
    }

    scale_x, scale_y = automation._get_screenshot_scale(screenshot)

    assert scale_x == 2.0
    assert scale_y == 2.0


def test_image_point_to_screen_restores_region_origin():
    pyautogui = _FakePyAutoGUI((1512, 982), (600, 300))
    automation = _automation_with_pyautogui(pyautogui)
    screenshot = Image.new("RGB", (600, 300), color="white")
    screenshot.info["_logical_capture_region"] = {
        "X": 100,
        "Y": 200,
        "Width": 300,
        "Height": 150,
    }

    screen_x, screen_y = automation._image_point_to_screen(60, 80, screenshot)

    assert screen_x == 130
    assert screen_y == 240


def test_logical_region_to_pixels_uses_region_local_offset():
    pyautogui = _FakePyAutoGUI((1512, 982), (600, 300))
    automation = _automation_with_pyautogui(pyautogui)
    screenshot = Image.new("RGB", (600, 300), color="white")
    screenshot.info["_logical_capture_region"] = {
        "X": 100,
        "Y": 200,
        "Width": 300,
        "Height": 150,
    }

    x, y, width, height = automation._logical_region_to_pixels(
        {"X": 130, "Y": 240, "Width": 60, "Height": 40},
        screenshot,
    )

    assert x == 60
    assert y == 80
    assert width == 120
    assert height == 80


def test_official_account_region_scales_with_window_size():
    automation = _automation_with_pyautogui(_FakePyAutoGUI((1512, 982), (1512, 982)))

    reference = automation._official_account_result_region(
        {"X": 100, "Y": 100, "Width": 900, "Height": 760}
    )
    larger = automation._official_account_result_region(
        {"X": 100, "Y": 100, "Width": 1350, "Height": 1140}
    )

    assert larger["Y"] > reference["Y"]
    assert larger["Width"] > reference["Width"]
    assert larger["Height"] > reference["Height"]


def test_extract_article_content_uses_main_window_bounds_for_short_body_lines():
    automation = _automation_with_pyautogui(_FakePyAutoGUI((400, 400), (400, 400)))
    automation.ocr_processor = _FakeOCRCapture()
    automation._image_point_to_screen = lambda x, y, screenshot: (int(x), int(y))
    automation._get_frontmost_wechat_window_bounds = lambda: {
        "X": 0,
        "Y": 0,
        "Width": 180,
        "Height": 160,
    }
    automation._get_interaction_bounds = lambda: {
        "X": 0,
        "Y": 0,
        "Width": 400,
        "Height": 400,
    }
    automation._recognize_text_regions = lambda screenshot: [
        {"text": "“探店”网红白冰，偷税超900万元被查", "confidence": 93, "x": 60, "y": 40, "width": 180, "height": 20},
        {"text": "消息", "confidence": 92, "x": 20, "y": 18, "width": 40, "height": 18},
        {"text": "税务部门通报该网红偷税超900万元", "confidence": 78, "x": 210, "y": 145, "width": 150, "height": 18},
        {"text": "其关联直播探店行业税务合规再受关注", "confidence": 75, "x": 210, "y": 172, "width": 150, "height": 18},
        {"text": "视频", "confidence": 88, "x": 320, "y": 345, "width": 40, "height": 16},
    ]

    result = asyncio.run(
        automation._extract_article_content("“探店”网红白冰，偷税超900万元被查")
    )

    assert result is not None
    assert result["read_success"] is True
    assert "税务部门通报该网红偷税超900万元" in result["content"]
    assert "税务合规再受关注" in result["content"]
    assert result["content"] != "文章标题: “探店”网红白冰，偷税超900万元被查"


def test_search_input_region_scales_with_window_size():
    automation = _automation_with_pyautogui(_FakePyAutoGUI((1512, 982), (1512, 982)))

    reference = automation._search_input_text_region(
        {"X": 100, "Y": 100, "Width": 900, "Height": 760}
    )
    larger = automation._search_input_text_region(
        {"X": 100, "Y": 100, "Width": 1350, "Height": 1140}
    )

    assert larger["X"] > reference["X"]
    assert larger["Width"] > reference["Width"]
    assert larger["Height"] >= reference["Height"]

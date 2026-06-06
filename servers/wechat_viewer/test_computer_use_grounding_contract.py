import asyncio
import importlib
import json
import logging
import sys
import types
from pathlib import Path

from PIL import Image


WECHAT_VIEWER_ROOT = Path(__file__).resolve().parent
SERVERS_ROOT = WECHAT_VIEWER_ROOT.parent
if str(SERVERS_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVERS_ROOT))

automation_package = types.ModuleType("automation")
automation_package.__path__ = [str(WECHAT_VIEWER_ROOT / "automation")]
sys.modules["automation"] = automation_package
sys.modules["mcp_core"] = importlib.import_module(
    "dataproai.src.servers.wechat_viewer.mcp_core"
)

from dataproai.src.servers.ai.handlers.tool_handler import ToolHandler
from dataproai.src.servers.shared.computer_use import (
    ComputerUseAgentAdapter,
    ComputerUseContextBuilder,
    ComputerUseFallbackPromptBuilder,
    ComputerUseGroundingResult,
    ComputerUseGroundingInterpreter,
    ComputerUseSuggestedAction,
)
from dataproai.src.servers.wechat_viewer.automation.improved_search_bar_locator import (
    ImprovedSearchBarLocator,
)
from dataproai.src.servers.wechat_viewer.automation.llm_element_locator import (
    LLMElementLocator,
)
from dataproai.src.servers.wechat_viewer.mcp_core.llm_protocol import (
    WeChatViewerLLMClient,
)
from dataproai.src.servers.wechat_viewer.automation.unified_element_locator import (
    BoundingBox,
    LocatorConfig,
    MultimodalJudge,
)
from dataproai.src.servers.wechat_viewer.automation.screenshot_optimizer import (
    ScreenshotInfo,
)


class _FakeAnalysisEngine:
    def __init__(self, response):
        self.response = response
        self.messages = None
        self.kwargs = None

    async def chat(self, messages, **kwargs):
        self.messages = messages
        self.kwargs = kwargs
        return self.response


class _FakeScreenshotHelper:
    def screenshot_to_base64(self, _screenshot):
        return "ZmFrZQ=="


class _FakeGroundingClient:
    def __init__(self, result, screenshot_info):
        self.result = result
        self.screenshot_info = screenshot_info
        self.calls = []

    async def computer_use_grounding(self, **kwargs):
        self.calls.append(kwargs)
        return self.result

    def get_last_screenshot_info(self):
        return self.screenshot_info


class _FakeLegacyFallbackClient:
    def __init__(self, result, screenshot_info):
        self.result = result
        self.screenshot_info = screenshot_info
        self.calls = []

    async def legacy_visual_fallback(self, prompt, screenshot_b64):
        self.calls.append({"prompt": prompt, "screenshot_b64": screenshot_b64})
        return self.result

    def get_last_screenshot_info(self):
        return self.screenshot_info


class _FakeProtocolMCPClient:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def legacy_visual_fallback(self, prompt, screenshot_b64):
        self.calls.append({"prompt": prompt, "screenshot_b64": screenshot_b64})
        return self.result


class _FakeAdaptiveOCR:
    def __init__(self, screenshot):
        self.ocr = self
        self._screenshot = screenshot

    def capture_screenshot(self, _region):
        return self._screenshot

    def recognize(self, _screenshot):
        return []

    def find_text(self, _screenshot, _indicator, fuzzy_match=True):
        return [{"text": "搜索"}]


def _install_fake_pyautogui(logical_size):
    fake_module = types.ModuleType("pyautogui")
    fake_module.size = lambda: logical_size
    sys.modules["pyautogui"] = fake_module
    return fake_module


def test_ai_tool_handler_computer_use_grounding_returns_openmanus_style_payload():
    response = {
        "status": "success",
        "response": json.dumps(
            {
                "found": True,
                "confidence": 0.91,
                "description": "Matched the WeChat search box.",
                "bbox": {"x": 90, "y": 24, "width": 60, "height": 24},
                "point": {"x": 120, "y": 36},
                "recommended_action": {
                    "action": "click",
                    "rationale": "The search box is ready for input.",
                    "confidence": 0.9,
                },
            }
        ),
    }
    engine = _FakeAnalysisEngine(response)
    handler = ToolHandler(dep_manager=None, db_ops=None, analysis_engine=engine)

    result = asyncio.run(
        handler.execute_tool(
            "computer_use_grounding",
            {
                "target": "搜索框",
                "screenshot_b64": "ZmFrZQ==",
                "region": {"X": 10, "Y": 20, "Width": 200, "Height": 80},
                "ui_context": {"app": "WeChat", "mode": "search_account"},
            },
        )
    )

    assert result["status"] == "success"
    assert result["found"] is True
    assert result["point"] == {"x": 120, "y": 36}
    assert result["bbox"] == {"x": 90, "y": 24, "width": 60, "height": 24}
    assert result["recommended_action"]["action"] == "click"
    assert "OpenManus-style computer_use contract" in engine.messages[1]["content"][0]["text"]


def test_computer_use_context_builder_generates_stable_wechat_payload():
    payload = ComputerUseContextBuilder.build_wechat_region_context(
        "财联社早知道",
        region={"X": 0, "Y": 0, "Width": 200, "Height": 80},
        original_region={"X": 100, "Y": 200, "Width": 200, "Height": 80},
    )

    assert payload["app"] == "WeChat"
    assert payload["mode"] == "find_element_by_name"
    assert payload["coordinate_space"] == "cropped_region"
    assert payload["expected_text"] == "财联社早知道"
    assert payload["original_region"]["X"] == 100


def test_computer_use_agent_adapter_builds_wechat_search_profile():
    profile = ComputerUseAgentAdapter.for_wechat_search_bar(
        window_bounds={"X": 10, "Y": 20, "Width": 300, "Height": 180},
        screenshot_size={"width": 300, "height": 180},
    )

    payload = profile.to_kwargs(screenshot_b64="ZmFrZQ==")

    assert payload["target"] == "微信搜索框"
    assert payload["allowed_actions"] == ["move_to", "click", "typing"]
    assert payload["ui_context"]["mode"] == "search_bar_locator"
    assert payload["ui_context"]["window_bounds"]["X"] == 10


def test_computer_use_grounding_result_to_dict_preserves_contract_shape():
    result = ComputerUseGroundingResult(
        status="success",
        target="搜索框",
        found=True,
        confidence=0.92,
        description="Matched the full search box.",
        point={"x": 120, "y": 36},
        bbox={"x": 90, "y": 24, "width": 60, "height": 24},
        recommended_action=ComputerUseSuggestedAction(
            action="click",
            rationale="The field is ready for input.",
            confidence=0.9,
            x=120,
            y=36,
        ),
        region={"X": 10, "Y": 20, "Width": 200, "Height": 80},
        coordinate_space="image",
        provider_metadata={"model": "test-model"},
        raw_response='{"found": true}',
    )

    payload = result.to_dict()

    assert payload["status"] == "success"
    assert payload["point"] == {"x": 120, "y": 36}
    assert payload["recommended_action"]["action"] == "click"
    assert payload["recommended_action"]["x"] == 120
    assert payload["provider_metadata"]["model"] == "test-model"


def test_computer_use_grounding_interpreter_extracts_point_and_legacy_payload():
    payload = {
        "found": True,
        "confidence": 87,
        "bbox": {"x": 90, "y": 24, "width": 60, "height": 24},
        "description": "Matched search box",
    }

    x, y = ComputerUseGroundingInterpreter.extract_point(payload)
    legacy = ComputerUseGroundingInterpreter.to_legacy_locator_payload(
        payload,
        description="Search box",
        match_text="搜索框",
    )

    assert (x, y) == (120, 36)
    assert ComputerUseGroundingInterpreter.coerce_confidence_percent(0.87) == 87.0
    assert legacy["center_x"] == 120
    assert legacy["center_y"] == 36
    assert legacy["match_text"] == "搜索框"
    assert legacy["confidence"] == 0.87


def test_computer_use_fallback_prompt_builder_covers_wechat_modes():
    locate_prompt = ComputerUseFallbackPromptBuilder.build_wechat_locate_prompt("搜索框")
    region_prompt = ComputerUseFallbackPromptBuilder.build_wechat_region_prompt(
        "财联社早知道",
        {"X": 0, "Y": 0, "Width": 200, "Height": 80},
    )
    search_prompt = ComputerUseFallbackPromptBuilder.build_wechat_search_bar_prompt()

    assert "搜索框" in locate_prompt
    assert "center_x" in locate_prompt
    assert "财联社早知道" in region_prompt
    assert "200x80" in region_prompt
    assert "微信的搜索框位置" in search_prompt
    candidate_prompt = (
        ComputerUseFallbackPromptBuilder.build_yolo_candidate_judgment_prompt(
            candidate_text="0: x=10, y=20, width=30, height=40, center=(25, 40)",
            element_hint="搜索框",
            image_size=(300, 180),
        )
    )
    articles_prompt = (
        ComputerUseFallbackPromptBuilder.build_wechat_visible_articles_prompt(
            candidate_limit=5,
            width=300,
            height=400,
        )
    )
    assert "candidate_index" in candidate_prompt
    assert "搜索框" in candidate_prompt
    assert "最多返回 5 个当前可见文章" in articles_prompt
    assert "300x400" in articles_prompt


def test_llm_locator_uses_computer_use_grounding_and_restores_logical_coords():
    previous = sys.modules.get("pyautogui")
    _install_fake_pyautogui((300, 150))
    try:
        client = _FakeGroundingClient(
            result={
                "found": True,
                "confidence": 0.88,
                "point": {"x": 30, "y": 20},
                "description": "Search box located.",
            },
            screenshot_info=ScreenshotInfo(
                original_width=300,
                original_height=150,
                compressed_width=150,
                compressed_height=75,
                scale_x=0.5,
                scale_y=0.5,
                was_compressed=True,
            ),
        )
        locator = LLMElementLocator(client, True, logging.getLogger("locator-test"))
        locator.set_screenshot_helper(_FakeScreenshotHelper())

        coords = asyncio.run(
            locator.locate_element(Image.new("RGB", (600, 300), color="white"), "搜索框")
        )

        assert coords == (30, 20)
        assert client.calls[0]["target"] == "搜索框"
        assert client.calls[0]["ui_context"]["mode"] == "locate_element"
        assert client.calls[0]["allowed_actions"] == ["move_to", "click"]
    finally:
        if previous is None:
            sys.modules.pop("pyautogui", None)
        else:
            sys.modules["pyautogui"] = previous


def test_llm_locator_restores_region_offset_after_computer_use_grounding():
    previous = sys.modules.get("pyautogui")
    _install_fake_pyautogui((300, 150))
    try:
        client = _FakeGroundingClient(
            result={
                "found": True,
                "confidence": 0.94,
                "point": {"x": 20, "y": 30},
                "description": "Account row located.",
            },
            screenshot_info=ScreenshotInfo(
                original_width=150,
                original_height=100,
                compressed_width=75,
                compressed_height=50,
                scale_x=0.5,
                scale_y=0.5,
                was_compressed=True,
            ),
        )
        locator = LLMElementLocator(client, True, logging.getLogger("locator-test"))
        locator.set_screenshot_helper(_FakeScreenshotHelper())

        coords = asyncio.run(
            locator.find_element_by_name(
                Image.new("RGB", (600, 600), color="white"),
                "财联社早知道",
                {"X": 100, "Y": 200, "Width": 150, "Height": 100},
            )
        )

        assert coords == (140, 260)
        assert client.calls[0]["ui_context"]["mode"] == "find_element_by_name"
        assert client.calls[0]["region"] == {"X": 0, "Y": 0, "Width": 150, "Height": 100}
        assert client.calls[0]["allowed_actions"] == ["move_to", "click"]
    finally:
        if previous is None:
            sys.modules.pop("pyautogui", None)
        else:
            sys.modules["pyautogui"] = previous


def test_improved_search_bar_locator_prefers_computer_use_grounding():
    screenshot = Image.new("RGB", (300, 180), color="white")
    locator = ImprovedSearchBarLocator(
        adaptive_ocr=_FakeAdaptiveOCR(screenshot),
        window_manager=None,
        ocr_enabled=False,
    )
    locator._verify_search_bar_activation = lambda *_args, **_kwargs: asyncio.sleep(0, result=True)

    client = _FakeGroundingClient(
        result={
            "found": True,
            "confidence": 0.93,
            "point": {"x": 40, "y": 30},
            "description": "搜索框位于侧边栏顶部。",
        },
        screenshot_info=None,
    )

    result = asyncio.run(
        locator._llm_based_search(
            {"X": 100, "Y": 200, "Width": 300, "Height": 180},
            client,
        )
    )

    assert result is not None
    assert result.x == 140
    assert result.y == 230
    assert result.strategy.value == "llm_vision"
    assert client.calls[0]["ui_context"]["mode"] == "search_bar_locator"
    assert client.calls[0]["allowed_actions"] == ["move_to", "click", "typing"]


def test_llm_locator_prefers_legacy_visual_fallback_when_grounding_unavailable():
    previous = sys.modules.get("pyautogui")
    _install_fake_pyautogui((300, 150))
    try:
        client = _FakeLegacyFallbackClient(
            result={
                "found": True,
                "center_x": 30,
                "center_y": 20,
                "confidence": 0.8,
                "description": "Legacy fallback located the search box.",
            },
            screenshot_info=ScreenshotInfo(
                original_width=300,
                original_height=150,
                compressed_width=300,
                compressed_height=150,
                scale_x=1.0,
                scale_y=1.0,
                was_compressed=False,
            ),
        )
        locator = LLMElementLocator(client, True, logging.getLogger("locator-test"))
        locator.set_screenshot_helper(_FakeScreenshotHelper())

        coords = asyncio.run(
            locator.locate_element(Image.new("RGB", (300, 150), color="white"), "搜索框")
        )

        assert coords == (30, 20)
        assert client.calls
        assert "搜索框" in client.calls[0]["prompt"]
    finally:
        if previous is None:
            sys.modules.pop("pyautogui", None)
        else:
            sys.modules["pyautogui"] = previous


def test_multimodal_judge_prefers_legacy_visual_fallback_for_candidate_selection():
    client = _FakeLegacyFallbackClient(
        result={"candidate_index": 1, "description": "Second candidate matches best."},
        screenshot_info=None,
    )
    judge = MultimodalJudge(
        config=LocatorConfig(),
        logger=logging.getLogger("multimodal-judge-test"),
        ai_client=client,
    )

    result = asyncio.run(
        judge.judge_element(
            Image.new("RGB", (200, 120), color="white"),
            [
                BoundingBox(0, 0, 20, 20),
                BoundingBox(20, 20, 40, 30),
            ],
            "搜索框",
        )
    )

    assert result is not None
    assert result.bbox == BoundingBox(20, 20, 40, 30)
    assert client.calls
    assert "candidate_index" in client.calls[0]["prompt"]


def test_improved_search_bar_locator_restores_compressed_grounding_coordinates():
    screenshot = Image.new("RGB", (300, 180), color="white")
    locator = ImprovedSearchBarLocator(
        adaptive_ocr=_FakeAdaptiveOCR(screenshot),
        window_manager=None,
        ocr_enabled=False,
    )
    locator._verify_search_bar_activation = lambda *_args, **_kwargs: asyncio.sleep(0, result=True)

    client = _FakeGroundingClient(
        result={
            "found": True,
            "confidence": 0.93,
            "point": {"x": 40, "y": 30},
            "description": "搜索框位于侧边栏顶部。",
        },
        screenshot_info=ScreenshotInfo(
            original_width=300,
            original_height=180,
            compressed_width=150,
            compressed_height=90,
            scale_x=0.5,
            scale_y=0.5,
            was_compressed=True,
        ),
    )

    result = asyncio.run(
        locator._llm_based_search(
            {"X": 100, "Y": 200, "Width": 300, "Height": 180},
            client,
        )
    )

    assert result is not None
    assert result.x == 180
    assert result.y == 260


def test_wechat_viewer_llm_client_analyze_screenshot_aliases_legacy_visual_fallback():
    client = object.__new__(WeChatViewerLLMClient)
    client._mcp_client = _FakeProtocolMCPClient({"ok": True, "source": "legacy"})

    result = asyncio.run(client.analyze_screenshot("定位搜索框", "ZmFrZQ=="))

    assert result == {"ok": True, "source": "legacy"}
    assert client._mcp_client.calls == [
        {"prompt": "定位搜索框", "screenshot_b64": "ZmFrZQ=="}
    ]

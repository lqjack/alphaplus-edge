import importlib
import logging
import sys
import types
from pathlib import Path

import pytest

WECHAT_VIEWER_ROOT = Path(__file__).resolve().parent
wechat_viewer_root_str = str(WECHAT_VIEWER_ROOT)
if wechat_viewer_root_str not in sys.path:
    sys.path.insert(0, wechat_viewer_root_str)

automation_package = types.ModuleType("automation")
automation_package.__path__ = [str(WECHAT_VIEWER_ROOT / "automation")]
sys.modules["automation"] = automation_package

handlers_package = types.ModuleType("handlers")
handlers_package.__path__ = [str(WECHAT_VIEWER_ROOT / "handlers")]
sys.modules["handlers"] = handlers_package

sys.modules["mcp_core"] = importlib.import_module(
    "dataproai.src.servers.wechat_viewer.mcp_core"
)
from .automation import wechat_automation as wechat_automation_module  # noqa: E402

from .automation.wechat_automation import (  # noqa: E402
    AutomationResult,
    AutomationStatus,
    WECHAT_ACCOUNT_ARTICLE_STAGE_TIMEOUT_SECONDS,
    WECHAT_ACCOUNT_SEARCH_STAGE_TIMEOUT_SECONDS_READ,
    WECHAT_ACCOUNT_SELECTION_STAGE_TIMEOUT_SECONDS_READ,
    WeChatAutomation,
)
from .handlers.tool_handler import WeChatViewerToolHandler  # noqa: E402
from .mcp_core.window_manager import MacOSWindowManager  # noqa: E402


class _PerfMonitor:
    def __init__(self):
        self.calls = []

    def record_operation(self, name, execution_time, success):
        self.calls.append((name, execution_time, success))


def _build_automation() -> WeChatAutomation:
    automation = WeChatAutomation.__new__(WeChatAutomation)
    automation.logger = logging.getLogger("wechat-viewer-contract-test")
    automation.performance_monitor = _PerfMonitor()
    automation._wechat_focus_grace_deadline = 0.0
    automation.adaptive_ocr = None
    automation.ocr_processor = None
    return automation


class _FakeDepManager:
    def __init__(self, mapping):
        self._mapping = mapping

    def get_dependency(self, name):
        return self._mapping.get(name)


class _FakeAccessibilityService:
    def __init__(self, match=None):
        self._match = match

    def find_named_element(self, *args, **kwargs):
        return self._match


class _FakeOCR:
    def __init__(self, results):
        self._results = results

    def recognize(self, screenshot, target_hint=None):
        return list(self._results)


class _FakeScreenshotCapture:
    def capture_screenshot(self):
        return object()


def test_normalize_article_url_repairs_dangling_percent_padding():
    automation = _build_automation()

    assert automation._normalize_article_url(
        "https://mp.weixin.qq.com/s?uin=MjQ2MDQ5ODMwNA%3D%"
    ) == "https://mp.weixin.qq.com/s?uin=MjQ2MDQ5ODMwNA%3D"


def test_article_trading_signal_score_prefers_optical_module_theme():
    automation = _build_automation()

    optical_score = automation._article_trading_signal_score(
        "光模块产能释放，下一个瓶颈轮到材料了？",
        "CPO、磷化铟和AI服务器链条同步扩产。",
    )
    bank_score = automation._article_trading_signal_score(
        "国有四大行，一季报出炉",
        "建设银行净利润862.91亿元，同比增长3.53%。",
    )

    assert optical_score > bank_score


def test_article_trading_signal_score_prefers_robot_material_theme_over_bank_quarterly_brief():
    automation = _build_automation()

    robot_score = automation._article_trading_signal_score(
        "【明日主题前瞻】人形机器人产业迎来密集催化，这类材料需求增速有望更趋陡峭",
        "人形机器人产业催化密集落地，关键材料需求斜率有望继续走高。",
    )
    bank_score = automation._article_trading_signal_score(
        "国有四大行，一季报出炉",
        "建设银行净利润862.91亿元，同比增长3.53%。",
    )

    assert robot_score > bank_score


def test_article_readout_timeout_scales_with_requested_article_count():
    automation = _build_automation()

    assert automation._article_readout_timeout_seconds(1) == WECHAT_ACCOUNT_ARTICLE_STAGE_TIMEOUT_SECONDS
    assert automation._article_readout_timeout_seconds(3) > WECHAT_ACCOUNT_ARTICLE_STAGE_TIMEOUT_SECONDS


def test_backfill_article_links_from_account_url_only_applies_to_matching_proxy_title():
    automation = _build_automation()

    visible_articles, articles, backfill_used = automation._backfill_article_links_from_account_url(
        visible_articles=[{"title": "在深海领域，“深海一号”超深水大气田成功投产，推动我国深水"}],
        articles=[{"title": "在深海领域，“深海一号”超深水大气田成功投产，推动我国深水", "content": "ok"}],
        titles=["在深海领域，“深海一号”超深水大气田成功投产，推动我国深水"],
        proxy_titles=["国有四大行，一季报出炉"],
        account_url="https://mp.weixin.qq.com/s?__biz=test&mid=1&idx=1&sn=bank",
        max_articles=3,
    )

    assert backfill_used is False
    assert not articles[0].get("url")
    assert not visible_articles[0].get("url")


def test_backfill_article_links_from_account_url_skips_fragmentary_title():
    automation = _build_automation()

    visible_articles, articles, backfill_used = automation._backfill_article_links_from_account_url(
        visible_articles=[{"title": "，不抢都感觉亏了"}],
        articles=[{"title": "，不抢都感觉亏了", "content": "ok"}],
        titles=["，不抢都感觉亏了"],
        proxy_titles=["，不抢都感觉亏了"],
        account_url="https://mp.weixin.qq.com/s?__biz=test&mid=1&idx=1&sn=fragment",
        max_articles=3,
    )

    assert backfill_used is False
    assert not articles[0].get("url")
    assert not visible_articles[0].get("url")


def test_exact_account_name_match_accepts_official_account_surface_variants():
    automation = _build_automation()

    assert automation._is_exact_account_name_match("财联社公众号 - Account", "财联社")
    assert automation._is_exact_account_name_match("财联社 媒体", "财联社")
    assert automation._looks_like_target_account_window_title("财联社公众号 - Account", "财联社")


def test_opened_account_window_title_accepts_exact_account_name():
    automation = _build_automation()

    assert automation._looks_like_opened_account_window_title("上海证券报", account_name="上海证券报")
    assert automation._looks_like_opened_account_window_title("财联社公众号 - Account", account_name="财联社")
    assert automation._looks_like_opened_account_window_title("Official Accounts", account_name="财联社") is False
    assert automation._looks_like_opened_account_window_title("搜一搜", account_name="财联社") is False


def test_resolve_search_surface_bounds_ignores_front_account_child_window(monkeypatch):
    automation = _build_automation()
    base_bounds = {"X": 100, "Y": 100, "Width": 900, "Height": 760}
    front_bounds = {"X": 560, "Y": 214, "Width": 598, "Height": 640}
    candidate_bounds = {"X": 120, "Y": 130, "Width": 620, "Height": 700}

    monkeypatch.setattr(automation, "_get_frontmost_wechat_window_bounds", lambda: front_bounds)
    monkeypatch.setattr(automation, "_find_wechat_search_panel_window_bounds", lambda bounds: candidate_bounds)
    monkeypatch.setattr(
        automation,
        "_find_wechat_window_info_by_bounds",
        lambda bounds, preferred_name=None: {"name": "上海证券报", "bounds": front_bounds},
    )

    resolved = automation._resolve_search_surface_bounds(
        base_bounds,
        allow_small_child=True,
        account_name="上海证券报",
    )

    assert resolved == candidate_bounds


def test_resolve_search_surface_bounds_prefers_larger_dedicated_search_panel(monkeypatch):
    automation = _build_automation()
    base_bounds = {"X": 547, "Y": 94, "Width": 909, "Height": 895}
    front_bounds = {"X": 595, "Y": 129, "Width": 368, "Height": 526}
    candidate_bounds = {"X": 843, "Y": 146, "Width": 609, "Height": 887}

    monkeypatch.setattr(automation, "_get_frontmost_wechat_window_bounds", lambda: front_bounds)
    monkeypatch.setattr(automation, "_find_wechat_search_panel_window_bounds", lambda bounds: candidate_bounds)
    monkeypatch.setattr(
        automation,
        "_find_wechat_window_info_by_bounds",
        lambda bounds, preferred_name=None: {"name": "", "bounds": front_bounds},
    )

    resolved = automation._resolve_search_surface_bounds(
        base_bounds,
        allow_small_child=True,
        account_name="上海证券报",
    )

    assert resolved == candidate_bounds


def test_resolve_account_discovery_panel_bounds_ignores_small_front_popup(monkeypatch):
    automation = _build_automation()
    base_bounds = {"X": 547, "Y": 94, "Width": 909, "Height": 895}
    front_bounds = {"X": 595, "Y": 129, "Width": 368, "Height": 526}
    fallback_bounds = {"X": 874, "Y": 165, "Width": 582, "Height": 800}

    monkeypatch.setattr(automation, "_get_frontmost_wechat_window_bounds", lambda: front_bounds)
    monkeypatch.setattr(automation, "_resolve_article_panel_bounds", lambda bounds: fallback_bounds)

    resolved = automation._resolve_account_discovery_panel_bounds(base_bounds)

    assert resolved == fallback_bounds


def test_official_account_panel_rejects_search_results_surface():
    automation = _build_automation()

    texts = [
        "AI Chatting",
        "Underline",
        "Video",
        "Account",
        "Articles",
        "财联社公众号 - Account",
        "Related Results",
        "More〉",
        "财联社24小时快讯",
        "财联社 媒体",
    ]

    assert automation._looks_like_official_account_panel(texts, "财联社") is False


def test_official_account_panel_rejects_search_results_surface_with_tabs():
    automation = _build_automation()

    texts = [
        "AI Chatting",
        "Video",
        "Articles",
        "Account",
        "财联社公众号 - Account",
        "Related Results",
        "More〉",
        "财联社24小时快讯",
        "财联社 媒体",
        "小程序",
        "公众号",
        "视频号",
        "服务号",
        "不限",
    ]

    assert automation._looks_like_official_account_panel(texts, "财联社") is False


def test_titled_account_article_window_rejects_search_results_surface():
    automation = _build_automation()

    texts = [
        "AI Chatting",
        "All",
        "Account",
        "Articles",
        "Underline",
        "Video",
        "财联社公众号 - Account",
        "Related Results",
        "财联社24小时快讯",
        "财联社 媒体",
    ]

    assert automation._looks_like_titled_account_article_window(texts, "财联社") is False


def test_titled_account_article_window_accepts_account_header_plus_single_title():
    automation = _build_automation()

    texts = [
        "Account",
        "Articles",
        "财联社公众号 - Account",
        "财联社24小时快讯",
        "财联社 媒体",
    ]

    assert automation._looks_like_titled_account_article_window(texts, "财联社") is True


def test_generic_official_accounts_panel_detects_category_surface():
    automation = _build_automation()

    texts = [
        "Video",
        "Articles",
        "Account",
        "All",
        "不限",
        "小程序",
        "公众号",
        "视频号",
        "服务号",
    ]

    assert automation._looks_like_generic_official_accounts_panel(texts) is True


def test_resolve_official_accounts_preview_region_uses_detected_section_headers(monkeypatch):
    automation = _build_automation()
    automation.ocr_processor = object()
    search_region = {"X": 100, "Y": 120, "Width": 620, "Height": 760}
    fake_ocr = _FakeOCR(
        [
            {"text": "Official Accounts", "confidence": 95, "position": {"x": 40, "y": 280, "width": 180, "height": 28}},
            {"text": "财联社", "confidence": 92, "position": {"x": 90, "y": 355, "width": 90, "height": 32}},
            {"text": "Recently Used Mini Programs", "confidence": 93, "position": {"x": 40, "y": 520, "width": 280, "height": 26}},
            {"text": "财联社", "confidence": 90, "position": {"x": 90, "y": 610, "width": 90, "height": 32}},
        ]
    )

    monkeypatch.setattr(automation, "_get_account_result_ocr_engine", lambda: fake_ocr)
    monkeypatch.setattr(
        automation,
        "_capture_region_screenshot",
        lambda region, expected_bounds=None: types.SimpleNamespace(
            size=(region["Width"], region["Height"]),
            info={"_logical_capture_region": region},
        ),
    )

    region = automation._resolve_official_accounts_preview_region(search_region, search_region, fake_ocr)

    assert region["Y"] > 120 + 280 + 28
    assert region["Y"] + region["Height"] < 120 + 520


def test_find_target_account_click_targets_in_search_preview_prefers_official_accounts_section(monkeypatch):
    automation = _build_automation()
    automation.ocr_processor = object()
    fake_ocr = _FakeOCR(
        [
            {"text": "Internet search results", "confidence": 95, "position": {"x": 30, "y": 20, "width": 220, "height": 28}},
            {"text": "财联社", "confidence": 95, "position": {"x": 80, "y": 100, "width": 92, "height": 30}},
            {"text": "Official Accounts", "confidence": 95, "position": {"x": 30, "y": 250, "width": 180, "height": 28}},
            {"text": "财联社", "confidence": 93, "position": {"x": 80, "y": 330, "width": 92, "height": 30}},
            {"text": "Recently Used Mini Programs", "confidence": 92, "position": {"x": 30, "y": 500, "width": 280, "height": 28}},
            {"text": "财联社", "confidence": 94, "position": {"x": 80, "y": 590, "width": 92, "height": 30}},
        ]
    )
    search_bounds = {"X": 100, "Y": 120, "Width": 620, "Height": 760}

    monkeypatch.setattr(
        automation,
        "_resolve_search_surface_bounds",
        lambda base_bounds, allow_small_child=True, account_name=None: search_bounds,
    )
    monkeypatch.setattr(automation, "_search_results_panel_bounds", lambda bounds: search_bounds)
    monkeypatch.setattr(
        automation,
        "_collect_region_ocr_surface_texts",
        lambda bounds, min_confidence=18.0: [
            "Internet search results",
            "财联社",
            "Official Accounts",
            "财联社",
            "Recently Used Mini Programs",
            "财联社",
        ],
    )
    monkeypatch.setattr(automation, "_get_account_result_ocr_engine", lambda: fake_ocr)
    monkeypatch.setattr(
        automation,
        "_capture_region_screenshot",
        lambda region, expected_bounds=None: types.SimpleNamespace(
            size=(region["Width"], region["Height"]),
            info={"_logical_capture_region": region},
        ),
    )

    targets = automation._find_target_account_click_targets_in_search_preview(search_bounds, "财联社")

    assert targets
    assert all(y < 120 + 500 for _, y, _ in targets)
    assert any(label == "preview_target_label" for _, _, label in targets)


def test_find_target_account_click_target_in_panel_allows_variant_on_generic_surface():
    automation = _build_automation()
    automation.accessibility_service = _FakeAccessibilityService(
        {
            "text": "财联社公众号",
            "x": 320,
            "y": 360,
            "confidence": 0.92,
        }
    )
    automation.ocr_processor = None

    match = automation._find_target_account_click_target_in_panel(
        {"X": 100, "Y": 120, "Width": 700, "Height": 780},
        "财联社",
        strict_exact=False,
    )

    assert match is not None
    assert match["text"] == "财联社公众号"


def test_probable_article_title_rejects_short_vip_section_label():
    automation = _build_automation()

    assert automation._is_probable_article_title("口 财联社VIP") is False
    assert automation._is_probable_article_title("，不抢都感觉亏了") is False
    assert automation._is_probable_article_title("东的净利润862.91亿元，同比增长3.53%。") is False
    assert automation._is_probable_article_title("达里奥：黄金或成终极避险选项") is True


def test_account_overview_content_is_not_treated_as_substantive_article():
    automation = _build_automation()
    overview_text = (
        "财联社24小时快讯 - Account\n"
        "24小时全球财经快讯\n"
        "财联社早知道\n"
        "今日财经头条\n"
        "3945篇原创内容 1小时前更新\n"
        "7x24财经快讯\n"
        "24小时实时财经新闻"
    )

    assert automation._looks_like_account_overview_content(overview_text, "财联社24小时快讯") is True
    assert automation._is_substantive_article_text(overview_text, "财联社24小时快讯") is False


@pytest.mark.asyncio
async def test_promote_article_content_from_url_replaces_account_overview_ocr(monkeypatch):
    automation = _build_automation()
    html = """
    <html>
      <head><meta property="og:title" content="财联社24小时快讯"></head>
      <body>
        <div id="js_content">
          <p>国家能源局发布最新数据，新能源装机持续增长。</p>
          <p>市场预期相关设备与材料需求继续改善。</p>
        </div>
      </body>
    </html>
    """

    monkeypatch.setattr(automation, "_fetch_article_html_from_url", lambda url, timeout_seconds=15.0: html)

    promoted = await automation._promote_article_content_from_url(
        {
            "title": "财联社24小时快讯",
            "content": (
                "财联社24小时快讯 - Account\n24小时全球财经快讯\n财联社早知道\n"
                "3945篇原创内容 1小时前更新"
            ),
            "detection_method": "ocr_content_extraction",
        },
        "https://mp.weixin.qq.com/s?id=proxy-account",
        "财联社24小时快讯",
    )

    assert promoted is not None
    assert "新能源装机持续增长" in promoted["content"]
    assert promoted["detection_method"] == "ocr_content_extraction+url_html_fallback"
    assert promoted["article_html"]


@pytest.mark.asyncio
async def test_promote_article_content_from_url_rejects_mismatched_html_title(monkeypatch):
    automation = _build_automation()
    html = """
    <html>
      <head><meta property="og:title" content="特斯拉内部担心马斯克涉政伤害公司 据悉有高管暗示他该辞职"></head>
      <body>
        <div id="js_content">
          <p>一份内部录音显示，特斯拉某部门最近举行的员工会议上，员工和管理层公开表达了对马斯克的担忧。</p>
        </div>
      </body>
    </html>
    """

    monkeypatch.setattr(automation, "_fetch_article_html_from_url", lambda url, timeout_seconds=15.0: html)

    promoted = await automation._promote_article_content_from_url(
        {
            "title": "光模块产能释放，下一个瓶颈轮到材料了？",
            "content": (
                "财联社24小时快讯 - Account\n24小时全球财经快讯\n财联社早知道\n"
                "3945篇原创内容 1小时前更新"
            ),
            "detection_method": "ocr_content_extraction",
        },
        "https://mp.weixin.qq.com/s?id=stale-proxy-url",
        "光模块产能释放，下一个瓶颈轮到材料了？",
    )

    assert promoted is not None
    assert promoted["title"] == "光模块产能释放，下一个瓶颈轮到材料了？"
    assert promoted["content"] == "文章标题: 光模块产能释放，下一个瓶颈轮到材料了？"
    assert "特斯拉某部门最近举行的员工会议" not in promoted["content"]
    assert promoted["detection_method"] == "ocr_content_extraction+url_title_mismatch_title_only"
    assert "article_html" not in promoted


@pytest.mark.asyncio
async def test_extract_article_content_demotes_account_overview_mix(monkeypatch):
    automation = _build_automation()
    automation.ocr_processor = _FakeScreenshotCapture()

    ocr_rows = [
        {"text": "财联社公众号 - Account", "confidence": 96, "y": 220},
        {"text": "10499篇原创内容 44分钟前更新", "confidence": 93, "y": 260},
        {"text": "VIP资讯。", "confidence": 92, "y": 300},
        {"text": "工、农、中、建四大国有行一季报陆续出炉，", "confidence": 90, "y": 340},
        {"text": "其中，农业银行净利润增速领跑。", "confidence": 88, "y": 380},
    ]

    monkeypatch.setattr(automation, "_recognize_text_regions", lambda screenshot: list(ocr_rows))
    monkeypatch.setattr(automation, "_ocr_position", lambda result: {"x": 120, "y": result["y"]})
    monkeypatch.setattr(automation, "_ocr_center", lambda result, screenshot: (320, result["y"]))
    monkeypatch.setattr(
        automation,
        "_get_frontmost_wechat_window_bounds",
        lambda: {"X": 100, "Y": 100, "Width": 700, "Height": 900},
    )
    monkeypatch.setattr(
        automation,
        "_get_interaction_bounds",
        lambda: {"X": 100, "Y": 100, "Width": 700, "Height": 900},
    )

    extracted = await automation._extract_article_content("国有四大行，一季报出炉")

    assert extracted is not None
    assert extracted["content"] == "文章标题: 国有四大行，一季报出炉"
    assert extracted["detection_method"] == "ocr_account_overview_title_only"


@pytest.mark.asyncio
async def test_extract_article_content_aggregates_loose_body_fragments(monkeypatch):
    automation = _build_automation()
    automation.ocr_processor = _FakeScreenshotCapture()

    ocr_rows = [
        {"text": "新能源汽车最新成绩单发布", "confidence": 96, "y": 180},
        {"text": "比亚迪4月销量继续攀升", "confidence": 8, "y": 320},
        {"text": "整车出口和高端化趋势延续", "confidence": 8, "y": 360},
        {"text": "供应链景气度同步抬升", "confidence": 8, "y": 400},
        {"text": "锂电与智能驾驶板块受关注", "confidence": 8, "y": 440},
    ]

    monkeypatch.setattr(automation, "_recognize_text_regions", lambda screenshot: list(ocr_rows))
    monkeypatch.setattr(automation, "_ocr_position", lambda result: {"x": 160, "y": result["y"]})
    monkeypatch.setattr(automation, "_ocr_center", lambda result, screenshot: (360, result["y"]))
    monkeypatch.setattr(
        automation,
        "_get_frontmost_wechat_window_bounds",
        lambda: {"X": 100, "Y": 100, "Width": 700, "Height": 900},
    )
    monkeypatch.setattr(
        automation,
        "_get_interaction_bounds",
        lambda: {"X": 100, "Y": 100, "Width": 700, "Height": 900},
    )

    extracted = await automation._extract_article_content("新能源汽车最新成绩单发布")

    assert extracted is not None
    assert extracted["detection_method"] == "ocr_tertiary_content"
    assert "比亚迪4月销量继续攀升" in extracted["content"]
    assert "锂电与智能驾驶板块受关注" in extracted["content"]


@pytest.mark.asyncio
async def test_extract_article_content_stitches_short_body_fragments(monkeypatch):
    automation = _build_automation()
    automation.ocr_processor = _FakeScreenshotCapture()

    ocr_rows = [
        {"text": "新能源汽车最新成绩单发布", "confidence": 96, "y": 180},
        {"text": "比亚迪", "confidence": 6, "y": 320},
        {"text": "4月", "confidence": 6, "y": 320},
        {"text": "销量", "confidence": 6, "y": 320},
        {"text": "继续", "confidence": 6, "y": 320},
        {"text": "攀升", "confidence": 6, "y": 320},
        {"text": "整车", "confidence": 6, "y": 360},
        {"text": "出口", "confidence": 6, "y": 360},
        {"text": "高端", "confidence": 6, "y": 360},
        {"text": "化趋势", "confidence": 6, "y": 360},
        {"text": "延续", "confidence": 6, "y": 360},
        {"text": "供应链", "confidence": 6, "y": 400},
        {"text": "景气度", "confidence": 6, "y": 400},
        {"text": "同步", "confidence": 6, "y": 400},
        {"text": "抬升", "confidence": 6, "y": 400},
        {"text": "锂电", "confidence": 6, "y": 440},
        {"text": "板块", "confidence": 6, "y": 440},
        {"text": "持续", "confidence": 6, "y": 440},
        {"text": "受关注", "confidence": 6, "y": 440},
    ]

    monkeypatch.setattr(automation, "_recognize_text_regions", lambda screenshot: list(ocr_rows))
    monkeypatch.setattr(automation, "_ocr_position", lambda result: {"x": 160, "y": result["y"]})
    monkeypatch.setattr(automation, "_ocr_center", lambda result, screenshot: (360, result["y"]))
    monkeypatch.setattr(
        automation,
        "_get_frontmost_wechat_window_bounds",
        lambda: {"X": 100, "Y": 100, "Width": 700, "Height": 900},
    )
    monkeypatch.setattr(
        automation,
        "_get_interaction_bounds",
        lambda: {"X": 100, "Y": 100, "Width": 700, "Height": 900},
    )

    extracted = await automation._extract_article_content("新能源汽车最新成绩单发布")

    assert extracted is not None
    assert extracted["detection_method"] == "ocr_fragment_stitch_content"
    assert "比亚迪4月销量继续攀升" in extracted["content"]
    assert "整车出口高端化趋势延续" in extracted["content"]


def test_get_proxy_history_for_account_recovers_title_from_article_url(monkeypatch):
    automation = _build_automation()

    accounts_payload = {
        "accounts": [
            {
                "id": 15,
                "account_name": "财联社",
                "account_url": "https://mp.weixin.qq.com/s?__biz=abc&uin=MjQ2MDQ5ODMwNA%3D%",
                "update": "2026-04-29T01:00:00Z",
            }
        ]
    }
    articles_payload = {
        "data": [
            {
                "article_title": "",
                "article_content_url": "https://mp.weixin.qq.com/s?__biz=abc&mid=1&uin=MjQ2MDQ5ODMwNA%3D%",
            }
        ]
    }

    def fake_fetch(path, params):
        if path == "/api/platforms/weixin/accounts":
            return accounts_payload
        if path == "/api/articles/":
            return articles_payload
        raise AssertionError(path)

    monkeypatch.setattr(automation, "_fetch_proxy_history_json", fake_fetch)
    monkeypatch.setattr(
        automation,
        "_fetch_article_title_from_url",
        lambda url, timeout=8.0: "特斯拉内部担心马斯克涉政伤害公司",
    )

    payload = automation._get_proxy_history_for_account("财联社", max_articles=1)

    assert payload is not None
    assert payload["titles"] == ["特斯拉内部担心马斯克涉政伤害公司"]
    assert payload["articles"][0]["title"] == "特斯拉内部担心马斯克涉政伤害公司"
    assert payload["articles"][0]["url"].endswith("uin=MjQ2MDQ5ODMwNA%3D")
    assert payload["account_url"].endswith("uin=MjQ2MDQ5ODMwNA%3D")


def test_get_proxy_history_for_account_uses_core_content_as_title(monkeypatch):
    automation = _build_automation()

    accounts_payload = {
        "accounts": [
            {
                "id": 15,
                "account_name": "财联社",
                "account_url": "https://mp.weixin.qq.com/s?__biz=abc&uin=MjQ2MDQ5ODMwNA%3D%",
                "update": "2026-04-29T01:00:00Z",
            }
        ]
    }
    articles_payload = {
        "data": [
            {
                "title": "",
                "coreContent": "达里奥：黄金或成终极避险选项",
                "url": "wechat://article/2a3faa5cefd3be6c2089aaef0d9ff43c091e9e29",
            }
        ]
    }

    def fake_fetch(path, params):
        if path == "/api/platforms/weixin/accounts":
            return accounts_payload
        if path == "/api/articles/":
            return articles_payload
        raise AssertionError(path)

    monkeypatch.setattr(automation, "_fetch_proxy_history_json", fake_fetch)
    monkeypatch.setattr(
        automation,
        "_fetch_article_title_from_url",
        lambda url, timeout=8.0: (_ for _ in ()).throw(AssertionError("URL fetch should not be needed when coreContent exists")),
    )

    payload = automation._get_proxy_history_for_account("财联社", max_articles=1)

    assert payload is not None
    assert payload["titles"] == ["达里奥：黄金或成终极避险选项"]
    assert payload["articles"][0]["title"] == "达里奥：黄金或成终极避险选项"


@pytest.mark.anyio
async def test_read_articles_with_ocr_prefers_highest_scored_candidate(monkeypatch):
    automation = _build_automation()

    candidates = [
        {"title": "口 财联社VIP", "x": 100, "y": 120, "confidence": 92.0, "total_score": 92.0},
        {"title": "达里奥：黄金或成终极避险选项", "x": 140, "y": 220, "confidence": 88.0, "total_score": 138.0},
    ]
    clicked_titles = []

    monkeypatch.setattr(automation, "_detect_articles_with_ocr", lambda bounds, limit: candidates)

    async def fake_open_extract_close(article, detection_method):
        clicked_titles.append(article["title"])
        return {"title": article["title"], "content": "ok", "read_success": True}

    async def fake_scroll(article_window_title=None, bounds=None):
        return None

    monkeypatch.setattr(automation, "_open_extract_close_article", fake_open_extract_close)
    monkeypatch.setattr(automation, "_scroll_article_list", fake_scroll)

    articles = await automation._read_articles_with_ocr(
        {"X": 0, "Y": 0, "Width": 600, "Height": 800},
        max_articles=1,
    )

    assert clicked_titles == ["达里奥：黄金或成终极避险选项"]
    assert articles[0]["title"] == "达里奥：黄金或成终极避险选项"


@pytest.mark.anyio
async def test_read_articles_with_ocr_scrolls_past_low_signal_candidates(monkeypatch):
    automation = _build_automation()

    candidate_pages = iter(
        [
            [
                {
                    "title": "国有四大行，一季报出炉",
                    "x": 100,
                    "y": 120,
                    "confidence": 92.0,
                    "signal_score": -10.0,
                    "total_score": 92.0,
                }
            ],
            [
                {
                    "title": "光模块产能释放，下一个瓶颈轮到材料了？",
                    "x": 140,
                    "y": 220,
                    "confidence": 88.0,
                    "signal_score": 30.0,
                    "total_score": 238.0,
                }
            ],
        ]
    )
    clicked_titles = []
    scroll_calls = []

    monkeypatch.setattr(automation, "_detect_articles_with_ocr", lambda bounds, limit: next(candidate_pages))

    async def fake_open_extract_close(article, detection_method):
        clicked_titles.append(article["title"])
        return {"title": article["title"], "content": "ok", "read_success": True}

    async def fake_scroll(article_window_title=None, bounds=None):
        scroll_calls.append((article_window_title, bounds))
        return None

    monkeypatch.setattr(automation, "_open_extract_close_article", fake_open_extract_close)
    monkeypatch.setattr(automation, "_scroll_article_list", fake_scroll)

    articles = await automation._read_articles_with_ocr(
        {"X": 0, "Y": 0, "Width": 600, "Height": 800},
        max_articles=1,
    )

    assert scroll_calls
    assert clicked_titles == ["光模块产能释放，下一个瓶颈轮到材料了？"]
    assert articles[0]["title"] == "光模块产能释放，下一个瓶颈轮到材料了？"


@pytest.mark.anyio
async def test_read_articles_with_ocr_applies_proxy_url_hint_before_open(monkeypatch):
    automation = _build_automation()
    automation._article_read_url_hints = {
        automation._article_title_key("财联社24小时快讯"): "https://mp.weixin.qq.com/s?id=hinted-article"
    }
    seen = {}

    monkeypatch.setattr(
        automation,
        "_detect_articles_with_ocr",
        lambda bounds, limit: [
            {"title": "财联社24小时快讯", "x": 140, "y": 220, "confidence": 88.0, "total_score": 138.0},
        ],
    )

    async def fake_open_extract_close(article, detection_method):
        seen["url"] = article.get("url")
        seen["link"] = article.get("link")
        return {"title": article["title"], "content": "ok", "read_success": True}

    async def fake_scroll(article_window_title=None, bounds=None):
        return None

    monkeypatch.setattr(automation, "_open_extract_close_article", fake_open_extract_close)
    monkeypatch.setattr(automation, "_scroll_article_list", fake_scroll)

    articles = await automation._read_articles_with_ocr(
        {"X": 0, "Y": 0, "Width": 600, "Height": 800},
        max_articles=1,
    )

    assert articles[0]["title"] == "财联社24小时快讯"
    assert seen["url"] == "https://mp.weixin.qq.com/s?id=hinted-article"
    assert seen["link"] == "https://mp.weixin.qq.com/s?id=hinted-article"


@pytest.mark.anyio
async def test_prepare_account_fetch_window_uses_fast_focus_path_before_slow_recovery(monkeypatch):
    automation = _build_automation()
    calls = []

    monkeypatch.setattr(
        automation,
        "_get_interaction_bounds",
        lambda: {"X": 10, "Y": 20, "Width": 900, "Height": 760},
    )

    def fake_frontmost(**kwargs):
        calls.append(("frontmost", kwargs))
        return False

    def fake_prime(**kwargs):
        calls.append(("prime", kwargs))
        return True

    def fail_close_windows():
        raise AssertionError("slow auxiliary-window recovery should be skipped when fast prime succeeds")

    monkeypatch.setattr(automation, "_ensure_wechat_frontmost", fake_frontmost)
    monkeypatch.setattr(automation, "_prime_wechat_for_immediate_action", fake_prime)
    monkeypatch.setattr(automation, "_close_front_auxiliary_wechat_windows", fail_close_windows)

    bounds = await automation._prepare_account_fetch_window()

    assert bounds == {"X": 10, "Y": 20, "Width": 900, "Height": 760}
    assert [call[0] for call in calls] == ["frontmost", "prime"]


@pytest.mark.asyncio
async def test_open_target_account_from_directory_panel_accepts_generic_category_surface(monkeypatch):
    automation = _build_automation()

    generic_panel_texts = [
        "Articles",
        "Account",
        "All",
        "不限",
        "小程序",
        "公众号",
        "视频号",
        "服务号",
    ]
    panel_checks = iter([True])
    clicked = []

    monkeypatch.setattr(
        automation,
        "_resolve_account_discovery_panel_bounds",
        lambda base_bounds: {"X": 100, "Y": 120, "Width": 700, "Height": 780},
    )
    monkeypatch.setattr(automation, "_collect_region_surface_texts", lambda *args, **kwargs: generic_panel_texts)
    monkeypatch.setattr(automation, "_looks_like_account_directory_panel", lambda texts, account_name: False)
    monkeypatch.setattr(
        automation,
        "_find_target_account_click_target_in_panel",
        lambda bounds, account_name, strict_exact=True: {
            "x": 320,
            "y": 360,
            "text": "财联社公众号",
            "method": "ocr_panel_match",
            "alternate_clicks": [],
        },
    )
    monkeypatch.setattr(
        automation,
        "click_at",
        lambda x, y: clicked.append((x, y)) or AutomationResult(
            status=AutomationStatus.SUCCESS,
            message="ok",
            execution_time=0.01,
        ),
    )
    monkeypatch.setattr(
        automation,
        "_panel_looks_like_official_account_page",
        lambda base_bounds, account_name: next(panel_checks),
    )

    assert await automation._open_target_account_from_directory_panel(
        {"X": 0, "Y": 0, "Width": 900, "Height": 760},
        "财联社",
    ) is True
    assert clicked[0] == (320, 360)


@pytest.mark.asyncio
async def test_open_target_account_from_directory_panel_accepts_target_evidence_without_directory_markers(monkeypatch):
    automation = _build_automation()
    panel_texts = ["上海证券报", "上证早知道", "投资内参", "宏观观察"]
    clicked = []

    monkeypatch.setattr(
        automation,
        "_resolve_account_discovery_panel_bounds",
        lambda base_bounds: {"X": 100, "Y": 120, "Width": 700, "Height": 780},
    )
    monkeypatch.setattr(automation, "_collect_region_surface_texts", lambda *args, **kwargs: panel_texts)
    monkeypatch.setattr(automation, "_looks_like_account_directory_panel", lambda texts, account_name: False)
    monkeypatch.setattr(automation, "_looks_like_generic_official_accounts_panel", lambda texts: False)
    monkeypatch.setattr(automation, "_has_account_name_evidence", lambda texts, account_name, min_similarity=0.68: True)
    monkeypatch.setattr(
        automation,
        "_find_target_account_click_target_in_panel",
        lambda bounds, account_name, strict_exact=True: {
            "x": 320,
            "y": 360,
            "text": "上海证券报",
            "method": "ocr_panel_match",
            "alternate_clicks": [],
        },
    )
    monkeypatch.setattr(
        automation,
        "click_at",
        lambda x, y: clicked.append((x, y)) or AutomationResult(
            status=AutomationStatus.SUCCESS,
            message="ok",
            execution_time=0.01,
        ),
    )
    monkeypatch.setattr(automation, "_panel_looks_like_official_account_page", lambda base_bounds, account_name: True)

    assert await automation._open_target_account_from_directory_panel(
        {"X": 0, "Y": 0, "Width": 900, "Height": 760},
        "上海证券报",
    ) is True
    assert clicked == [(320, 360)]


@pytest.mark.asyncio
async def test_open_target_account_from_official_accounts_preview_falls_back_to_directory_panel(monkeypatch):
    automation = _build_automation()

    monkeypatch.setattr(
        automation,
        "_resolve_search_surface_bounds",
        lambda base_bounds, allow_small_child=True, account_name=None: {"X": 10, "Y": 20, "Width": 900, "Height": 760},
    )
    monkeypatch.setattr(
        automation,
        "_search_results_panel_bounds",
        lambda bounds: bounds,
    )
    monkeypatch.setattr(
        automation,
        "_collect_region_ocr_surface_texts",
        lambda bounds, min_confidence=18.0: ["Articles", "Account", "公众号", "服务号", "视频号", "小程序", "不限"],
    )
    monkeypatch.setattr(
        automation,
        "_find_target_account_click_targets_in_search_preview",
        lambda base_bounds, account_name: [],
    )
    monkeypatch.setattr(automation, "_looks_like_generic_official_accounts_panel", lambda texts: True)

    async def fake_open_directory(base_bounds, account_name):
        return True

    monkeypatch.setattr(automation, "_open_target_account_from_directory_panel", fake_open_directory)

    assert await automation._open_target_account_from_official_accounts_preview(
        {"X": 0, "Y": 0, "Width": 900, "Height": 760},
        "财联社",
    ) is True


@pytest.mark.asyncio
async def test_reset_search_and_open_official_accounts_surface_opens_target_before_refocus(monkeypatch):
    automation = _build_automation()
    calls = []

    monkeypatch.setattr(automation, "_ensure_wechat_frontmost", lambda activate=True: True)
    monkeypatch.setattr(automation, "press_key", lambda key: calls.append(("press_key", key)) or True)

    async def fake_open_contacts(base_bounds, ocr_engine):
        calls.append(("open_contacts", base_bounds))
        return True

    monkeypatch.setattr(automation, "_open_contacts_official_accounts_surface", fake_open_contacts)

    async def fake_open_directory(base_bounds, account_name):
        calls.append(("open_directory", account_name))
        return True

    async def fail_open_preview(base_bounds, account_name):
        raise AssertionError("preview fallback should not be needed when directory open succeeds")

    monkeypatch.setattr(automation, "_open_target_account_from_directory_panel", fake_open_directory)
    monkeypatch.setattr(automation, "_open_target_account_from_official_accounts_preview", fail_open_preview)
    monkeypatch.setattr(automation, "_refocus_search_input", lambda bounds: (_ for _ in ()).throw(AssertionError("refocus should be skipped")))

    opened = await automation._reset_search_and_open_official_accounts_surface(
        {"X": 0, "Y": 0, "Width": 900, "Height": 760},
        "财联社",
        None,
    )

    assert opened is True
    assert ("open_directory", "财联社") in calls


@pytest.mark.asyncio
async def test_reset_search_and_open_official_accounts_surface_fails_when_refocus_fails(monkeypatch):
    automation = _build_automation()

    monkeypatch.setattr(automation, "_ensure_wechat_frontmost", lambda activate=True: True)
    monkeypatch.setattr(automation, "press_key", lambda key: True)

    async def fake_open_contacts(base_bounds, ocr_engine):
        return True

    monkeypatch.setattr(automation, "_open_contacts_official_accounts_surface", fake_open_contacts)

    async def fake_open_directory(base_bounds, account_name):
        return False

    async def fake_open_preview(base_bounds, account_name):
        return False

    monkeypatch.setattr(automation, "_open_target_account_from_directory_panel", fake_open_directory)
    monkeypatch.setattr(automation, "_open_target_account_from_official_accounts_preview", fake_open_preview)
    monkeypatch.setattr(automation, "_refocus_search_input", lambda bounds: False)

    opened = await automation._reset_search_and_open_official_accounts_surface(
        {"X": 0, "Y": 0, "Width": 900, "Height": 760},
        "财联社",
        None,
    )

    assert opened is False


@pytest.mark.asyncio
async def test_find_and_click_account_in_results_resets_when_surface_looks_like_chat_list(monkeypatch):
    automation = _build_automation()
    reset_calls = []
    search_bounds = {"X": 10, "Y": 20, "Width": 900, "Height": 760}
    effective_region = {"X": 20, "Y": 80, "Width": 300, "Height": 600}
    official_region = {"X": 20, "Y": 80, "Width": 300, "Height": 600}

    monkeypatch.setattr(
        automation,
        "_resolve_search_surface_bounds",
        lambda bounds, allow_small_child=True, account_name=None: search_bounds,
    )
    monkeypatch.setattr(automation, "_search_results_panel_bounds", lambda bounds, region_hint=None: effective_region)
    monkeypatch.setattr(automation, "_resolve_official_accounts_preview_region", lambda bounds, region, ocr_engine=None: official_region)
    monkeypatch.setattr(automation, "_get_account_result_ocr_engine", lambda: object())
    monkeypatch.setattr(automation, "_capture_region_screenshot", lambda region, expected_bounds=None: object())
    monkeypatch.setattr(
        automation,
        "_extract_region_ocr_texts",
        lambda region, min_confidence=18.0: ["Jack", "Yesterday 18:08", "［Photo］", "Minimized Groups", "锂电@珍珠项链：顶多"],
    )
    monkeypatch.setattr(automation, "_find_best_ocr_text_match", lambda *args, **kwargs: None)
    monkeypatch.setattr(automation, "_open_official_accounts_search_entry", lambda *args, **kwargs: False)
    monkeypatch.setattr(automation, "_has_account_name_evidence", lambda texts, account_name: False)

    async def fake_reset(base_bounds, account_name, ocr_engine):
        reset_calls.append((base_bounds, account_name))
        return False

    monkeypatch.setattr(automation, "_reset_search_and_open_official_accounts_surface", fake_reset)

    opened = await automation._find_and_click_account_in_results(
        search_bounds,
        "财联社",
        search_bounds,
    )

    assert opened is False
    assert reset_calls == [(search_bounds, "财联社")]


@pytest.mark.asyncio
async def test_select_account_from_search_results_short_circuits_when_target_page_already_open(monkeypatch):
    automation = _build_automation()

    monkeypatch.setattr(
        automation,
        "_panel_looks_like_official_account_page",
        lambda bounds, account_name: True,
    )

    async def fail_find(*args, **kwargs):
        raise AssertionError("search-result lookup should be skipped when target page is already open")

    monkeypatch.setattr(automation, "_find_and_click_account_in_results", fail_find)

    opened = await automation.select_account_from_search_results(
        {"X": 0, "Y": 0, "Width": 900, "Height": 760},
        "上海证券报",
    )

    assert opened is True


def test_looks_like_chat_conversation_panel_matches_real_wechat_chat_list_sample():
    automation = _build_automation()

    texts = [
        "微信ClawBot AI",
        "星期五",
        "定时任务 sch202605011c22...",
        "吴先生 pujon 标易....",
        "星期五",
        "好",
        "可以的。",
        "会飞的猪猪侠（爱..",
        "星期五",
        "Jack",
        "04/30",
        "［文件］ labor_arbitration_bo..",
        "折叠的聊天",
    ]

    assert automation._looks_like_chat_conversation_panel(texts) is True
    assert automation._looks_like_misfocused_search_results_surface(texts) is True


def test_looks_like_official_account_panel_accepts_real_article_body_sample():
    automation = _build_automation()

    texts = [
        "海证券报 2026年5月2日 23:08638人",
        "026年5月2日，投资界的年度盛会——伯克希",
        "（下简称伯克希尔）股东大会在美国内布拉斯加",
        "马哈°举行。这是自沃伦•巴菲特掌舵六十年来，",
        "首次在他退居幕后情况下举行的股东年会，也是",
        "接班人阿贝尔首次独立主持年度大会。",
    ]

    assert automation._looks_like_official_account_panel(texts, "上海证券报") is True


def test_looks_like_official_account_panel_accepts_profile_surface_without_exact_header():
    automation = _build_automation()

    texts = [
        "上海证券报，新华社主办，中国证监会法定披露证券市场信",
        "息媒体。1991年创办，是新中国第一份提供权威金融证券..",
        "展开",
        "3479篇原创内容 8个朋友关注",
        "视频号：上证盈视频",
        "已关注",
        "发消息",
        "文章",
        "视频号",
        "贴图",
        "全部",
        "每日研选 • 上证早知道 市场探“涨\"",
    ]

    assert automation._looks_like_official_account_panel(texts, "上海证券报") is True


@pytest.mark.asyncio
async def test_find_and_click_account_in_results_resets_misfocused_surface_even_with_target_evidence(monkeypatch):
    automation = _build_automation()
    automation.ocr_enabled = True
    automation.accessibility_service = None
    reset_calls = []
    search_bounds = {"X": 10, "Y": 20, "Width": 900, "Height": 760}
    effective_region = {"X": 20, "Y": 80, "Width": 300, "Height": 600}
    official_region = {"X": 20, "Y": 80, "Width": 300, "Height": 600}

    monkeypatch.setattr(
        automation,
        "_resolve_search_surface_bounds",
        lambda bounds, allow_small_child=True, account_name=None: search_bounds,
    )
    monkeypatch.setattr(automation, "_search_results_panel_bounds", lambda bounds, region_hint=None: effective_region)
    monkeypatch.setattr(automation, "_resolve_official_accounts_preview_region", lambda bounds, region, ocr_engine=None: official_region)
    monkeypatch.setattr(automation, "_get_account_result_ocr_engine", lambda: object())
    monkeypatch.setattr(automation, "_capture_region_screenshot", lambda region, expected_bounds=None: object())
    monkeypatch.setattr(
        automation,
        "_extract_region_ocr_texts",
        lambda region, min_confidence=18.0: [
            "聊天记录",
            "上海证券报",
            "发送人",
            "日期",
            "进入聊天〉",
            "上海证券报0430.pdf",
        ],
    )
    monkeypatch.setattr(automation, "_find_best_ocr_text_match", lambda *args, **kwargs: None)
    monkeypatch.setattr(automation, "_open_official_accounts_search_entry", lambda *args, **kwargs: False)
    monkeypatch.setattr(automation, "_has_account_name_evidence", lambda texts, account_name: True)
    monkeypatch.setattr(automation, "_looks_like_misfocused_search_results_surface", lambda texts: True)

    async def fake_reset(base_bounds, account_name, ocr_engine):
        reset_calls.append((base_bounds, account_name))
        return False

    monkeypatch.setattr(automation, "_reset_search_and_open_official_accounts_surface", fake_reset)

    opened = await automation._find_and_click_account_in_results(
        search_bounds,
        "上海证券报",
        search_bounds,
    )

    assert opened is False
    assert reset_calls == [(search_bounds, "上海证券报")]


@pytest.mark.asyncio
async def test_find_and_click_account_in_results_short_circuits_when_article_page_already_open(monkeypatch):
    automation = _build_automation()
    automation.ocr_enabled = True
    automation.accessibility_service = None
    search_bounds = {"X": 10, "Y": 20, "Width": 900, "Height": 760}
    effective_region = {"X": 20, "Y": 80, "Width": 300, "Height": 600}
    official_region = {"X": 20, "Y": 80, "Width": 300, "Height": 600}
    article_texts = [
        "海证券报 2026年5月2日 23:08638人",
        "026年5月2日，投资界的年度盛会——伯克希",
        "（下简称伯克希尔）股东大会在美国内布拉斯加",
        "马哈°举行。这是自沃伦•巴菲特掌舵六十年来，",
        "首次在他退居幕后情况下举行的股东年会，也是",
        "接班人阿贝尔首次独立主持年度大会。",
    ]
    reset_calls = []

    monkeypatch.setattr(
        automation,
        "_resolve_search_surface_bounds",
        lambda bounds, allow_small_child=True, account_name=None: search_bounds,
    )
    monkeypatch.setattr(automation, "_search_results_panel_bounds", lambda bounds, region_hint=None: effective_region)
    monkeypatch.setattr(automation, "_resolve_official_accounts_preview_region", lambda bounds, region, ocr_engine=None: official_region)
    monkeypatch.setattr(automation, "_get_account_result_ocr_engine", lambda: object())
    monkeypatch.setattr(automation, "_capture_region_screenshot", lambda region, expected_bounds=None: object())
    monkeypatch.setattr(automation, "_extract_region_ocr_texts", lambda region, min_confidence=18.0: article_texts)
    monkeypatch.setattr(automation, "_find_best_ocr_text_match", lambda *args, **kwargs: None)
    monkeypatch.setattr(automation, "_has_account_name_evidence", lambda texts, account_name: True)

    async def fake_reset(*args, **kwargs):
        reset_calls.append((args, kwargs))
        return False

    monkeypatch.setattr(automation, "_reset_search_and_open_official_accounts_surface", fake_reset)

    opened = await automation._find_and_click_account_in_results(
        search_bounds,
        "上海证券报",
        search_bounds,
        allow_search_commit_retry=False,
    )

    assert opened is True
    assert reset_calls == []


def test_account_result_row_context_flags_block_chat_history_pdf_rows():
    automation = _build_automation()

    official, blocked = automation._account_result_row_context_flags(
        "上海证券报 发送人 日期 共1条与“上海证券报”的聊天记录 进入聊天 上海证券报0430.pdf PDF"
    )

    assert official is False
    assert blocked is True


def test_click_wechat_named_entry_allows_exact_label_even_with_timestamp_row(monkeypatch):
    automation = _build_automation()
    automation.accessibility_service = None
    clicked = []

    monkeypatch.setattr(automation, "_capture_region_screenshot", lambda region, expected_bounds=None: object())
    monkeypatch.setattr(automation, "_get_account_result_ocr_engine", lambda: object())
    monkeypatch.setattr(
        automation,
        "_find_best_ocr_text_match",
        lambda screenshot, label, **kwargs: {
            "text": "公众号",
            "row_text": "公众号22:46 公众号 22:46",
            "x": 684,
            "y": 169,
        }
        if label == "公众号"
        else None,
    )
    monkeypatch.setattr(
        automation,
        "_click_at_with_focus_retry",
        lambda x, y: clicked.append((x, y)) or AutomationResult(
            status=AutomationStatus.SUCCESS,
            message="ok",
            execution_time=0.01,
        ),
    )

    opened = automation._click_wechat_named_entry(
        {"X": 547, "Y": 94, "Width": 909, "Height": 895},
        ["订阅号", "公众号", "Official Accounts"],
        region={"X": 547, "Y": 156, "Width": 381, "Height": 833},
    )

    assert opened is True
    assert clicked == [(684, 169)]


def test_click_wechat_named_entry_allows_exact_label_with_official_directory_context(monkeypatch):
    automation = _build_automation()
    automation.accessibility_service = None
    clicked = []

    monkeypatch.setattr(automation, "_capture_region_screenshot", lambda region, expected_bounds=None: object())
    monkeypatch.setattr(automation, "_get_account_result_ocr_engine", lambda: object())
    monkeypatch.setattr(
        automation,
        "_find_best_ocr_text_match",
        lambda screenshot, label, **kwargs: {
            "text": "公众号",
            "row_text": "公众号07:45常看的号 公众号 07:45 常看的号",
            "x": 685,
            "y": 169,
        }
        if label == "公众号"
        else None,
    )
    monkeypatch.setattr(
        automation,
        "_click_at_with_focus_retry",
        lambda x, y: clicked.append((x, y)) or AutomationResult(
            status=AutomationStatus.SUCCESS,
            message="ok",
            execution_time=0.01,
        ),
    )

    opened = automation._click_wechat_named_entry(
        {"X": 547, "Y": 94, "Width": 909, "Height": 895},
        ["订阅号", "公众号", "Official Accounts"],
        region={"X": 547, "Y": 156, "Width": 381, "Height": 833},
        blocked_terms=["常看的号", "今天"],
    )

    assert opened is True
    assert clicked == [(685, 169)]


@pytest.mark.asyncio
async def test_fetch_account_article_titles_prefers_gui_titles_over_proxy_titles(monkeypatch):
    automation = _build_automation()

    async def passthrough_timeout(label, awaitable, timeout_seconds, default=None):
        return await awaitable

    async def fake_prepare():
        return {"X": 10, "Y": 20, "Width": 900, "Height": 760}

    async def fake_search(bounds, account_name):
        return AutomationResult(
            status=AutomationStatus.SUCCESS,
            message="ok",
            data={"found": True},
            execution_time=0.1,
        )

    async def fake_scroll(account_name, bounds):
        return None

    async def fake_visible(bounds, max_articles=1):
        return [{"title": "风口研报pro是由界面财联社出品的研报解读服务，专业分析..."}]

    async def fake_read(bounds, max_articles=1, article_window_title=None):
        return [{
            "title": "财联社存款利率下调",
            "content": "ok",
            "read_success": True,
        }]

    async def fake_select(bounds, account_name):
        return True

    automation.get_accessibility_status = lambda: {"permission_required": False}
    automation._get_proxy_history_for_account = lambda account_name, max_articles=1: {
        "account_name": account_name,
        "account_url": "https://mp.weixin.qq.com/s?id=proxy-account",
        "titles": ["达里奥：黄金或成终极避险选项"],
        "visible_titles": ["达里奥：黄金或成终极避险选项"],
        "read_titles": ["达里奥：黄金或成终极避险选项"],
        "articles": [{"title": "达里奥：黄金或成终极避险选项"}],
    }
    automation._await_with_timeout = passthrough_timeout
    automation._prepare_account_fetch_window = fake_prepare
    automation.search_wechat_account = fake_search
    automation.select_account_from_search_results = fake_select
    automation._resolve_article_panel_bounds = lambda bounds, account_name=None: bounds
    automation._scroll_article_list_to_top = fake_scroll
    automation.list_latest_articles = fake_visible
    automation.read_latest_articles = fake_read

    result = await automation.fetch_account_article_titles(
        "财联社",
        max_articles=1,
        read_articles=True,
    )

    assert result.status == AutomationStatus.SUCCESS
    assert result.data["titles"] == ["财联社存款利率下调"]
    assert result.data["visible_titles"] == ["风口研报pro是由界面财联社出品的研报解读服务，专业分析..."]
    assert result.data["read_titles"] == ["财联社存款利率下调"]
    assert result.data["articles"][0]["title"] == "财联社存款利率下调"
    assert result.data["proxy_fallback_used"] is False
    assert result.data["proxy_account_url_backfilled"] is False
    assert result.data["articles"][0].get("url", "") == ""


@pytest.mark.asyncio
async def test_fetch_account_article_titles_prefers_official_entry_before_generic_selection(monkeypatch):
    automation = _build_automation()

    async def passthrough_timeout(label, awaitable, timeout_seconds, default=None):
        return await awaitable

    async def fake_prepare():
        return {"X": 10, "Y": 20, "Width": 900, "Height": 760}

    async def fake_search(bounds, account_name):
        return AutomationResult(
            status=AutomationStatus.SUCCESS,
            message="ok",
            data={"found": True},
            execution_time=0.1,
        )

    async def fake_select(bounds, account_name):
        called["generic_select"] = (bounds, account_name)
        return True

    async def fake_open_official_entry(
        bounds,
        search_results_region,
        ocr_engine,
        account_name="",
        official_account_region=None,
        detected_texts=None,
    ):
        called["official_entry"] = {
            "bounds": bounds,
            "search_results_region": search_results_region,
            "account_name": account_name,
            "detected_texts": detected_texts,
        }
        return True

    async def fake_scroll(account_name, bounds):
        return None

    async def fake_visible(bounds, max_articles=1):
        return [{"title": "财联社财报解读"}]

    async def fake_read(bounds, max_articles=1, article_window_title=None):
        return [{
            "title": "财联社财报解读",
            "content": "ok",
            "read_success": True,
        }]

    called = {}

    automation.get_accessibility_status = lambda: {"permission_required": False}
    automation._get_proxy_history_for_account = lambda account_name, max_articles=1: {}
    automation._await_with_timeout = passthrough_timeout
    automation._prepare_account_fetch_window = fake_prepare
    automation.search_wechat_account = fake_search
    automation._open_official_accounts_search_entry = fake_open_official_entry
    automation._collect_official_accounts_surface_texts = lambda *args, **kwargs: ["公众号", "财联社"]
    automation._resolve_search_surface_bounds = lambda bounds, allow_small_child=False, account_name=None: bounds
    automation._search_results_panel_bounds = lambda bounds: bounds
    automation._official_account_result_region = lambda bounds: bounds
    automation._get_account_result_ocr_engine = lambda: None
    automation.select_account_from_search_results = fake_select
    automation._resolve_article_panel_bounds = lambda bounds, account_name=None: bounds
    automation._scroll_article_list_to_top = fake_scroll
    automation.list_latest_articles = fake_visible
    automation.read_latest_articles = fake_read

    result = await automation.fetch_account_article_titles(
        "财联社",
        max_articles=1,
        read_articles=True,
    )

    assert result.status == AutomationStatus.SUCCESS
    assert called["official_entry"]["account_name"] == "财联社"
    assert "generic_select" not in called


@pytest.mark.asyncio
async def test_fetch_account_article_titles_falls_back_to_generic_selection_when_official_hint_missing(monkeypatch):
    automation = _build_automation()

    async def passthrough_timeout(label, awaitable, timeout_seconds, default=None):
        return await awaitable

    async def fake_prepare():
        return {"X": 10, "Y": 20, "Width": 900, "Height": 760}

    async def fake_search(bounds, account_name):
        return AutomationResult(
            status=AutomationStatus.SUCCESS,
            message="ok",
            data={"found": True},
            execution_time=0.1,
        )

    async def fake_select(bounds, account_name):
        called["generic_select"] = (bounds, account_name)
        return True

    async def fake_open_official_entry(
        bounds,
        search_results_region,
        ocr_engine,
        account_name="",
        official_account_region=None,
        detected_texts=None,
    ):
        called["official_entry"] = {
            "bounds": bounds,
            "search_results_region": search_results_region,
            "account_name": account_name,
        }
        return True

    async def fake_scroll(account_name, bounds):
        return None

    async def fake_visible(bounds, max_articles=1):
        return [{"title": "财联社24小时快讯"}]

    async def fake_read(bounds, max_articles=1, article_window_title=None):
        return [{
            "title": "财联社24小时快讯",
            "content": "ok",
            "read_success": True,
        }]

    called = {}

    automation.get_accessibility_status = lambda: {"permission_required": False}
    automation._get_proxy_history_for_account = lambda account_name, max_articles=1: {}
    automation._await_with_timeout = passthrough_timeout
    automation._prepare_account_fetch_window = fake_prepare
    automation.search_wechat_account = fake_search
    automation._open_official_accounts_search_entry = fake_open_official_entry
    automation._collect_official_accounts_surface_texts = lambda *args, **kwargs: ["财联社快讯", "市场动态"]
    automation._has_account_name_evidence = lambda texts, account_name: False
    automation._resolve_search_surface_bounds = lambda bounds, allow_small_child=False, account_name=None: bounds
    automation._search_results_panel_bounds = lambda bounds: bounds
    automation._official_account_result_region = lambda bounds: bounds
    automation._get_account_result_ocr_engine = lambda: None
    automation.select_account_from_search_results = fake_select
    automation._resolve_article_panel_bounds = lambda bounds, account_name=None: bounds
    automation._scroll_article_list_to_top = fake_scroll
    automation.list_latest_articles = fake_visible
    automation.read_latest_articles = fake_read

    result = await automation.fetch_account_article_titles(
        "财联社",
        max_articles=1,
        read_articles=True,
    )

    assert result.status == AutomationStatus.SUCCESS
    assert "official_entry" not in called
    assert "generic_select" in called


@pytest.mark.asyncio
async def test_fetch_account_article_titles_marks_proxy_fallback_when_proxy_article_supplies_link(monkeypatch):
    automation = _build_automation()

    async def passthrough_timeout(label, awaitable, timeout_seconds, default=None):
        return await awaitable

    async def fake_prepare():
        return {"X": 10, "Y": 20, "Width": 900, "Height": 760}

    async def fake_search(bounds, account_name):
        return AutomationResult(
            status=AutomationStatus.SUCCESS,
            message="ok",
            data={"found": True},
            execution_time=0.1,
        )

    async def fake_scroll(account_name, bounds):
        return None

    async def fake_visible(bounds, max_articles=1):
        return [{"title": "财联社24小时快讯"}]

    async def fake_read(bounds, max_articles=1, article_window_title=None):
        return [{
            "title": "财联社24小时快讯",
            "content": "ok",
            "read_success": True,
        }]

    async def fake_select(bounds, account_name):
        return True

    automation.get_accessibility_status = lambda: {"permission_required": False}
    automation._get_proxy_history_for_account = lambda account_name, max_articles=1: {
        "account_name": account_name,
        "account_url": "https://mp.weixin.qq.com/s?id=proxy-account",
        "titles": ["财联社24小时快讯"],
        "visible_titles": ["财联社24小时快讯"],
        "read_titles": ["财联社24小时快讯"],
        "articles": [{"title": "财联社24小时快讯", "url": "https://mp.weixin.qq.com/s?id=proxy-article"}],
    }
    automation._await_with_timeout = passthrough_timeout
    automation._prepare_account_fetch_window = fake_prepare
    automation.search_wechat_account = fake_search
    automation.select_account_from_search_results = fake_select
    automation._resolve_article_panel_bounds = lambda bounds, account_name=None: bounds
    automation._scroll_article_list_to_top = fake_scroll
    automation.list_latest_articles = fake_visible
    automation.read_latest_articles = fake_read

    result = await automation.fetch_account_article_titles(
        "财联社",
        max_articles=1,
        read_articles=True,
    )

    assert result.status == AutomationStatus.SUCCESS
    assert result.data["articles"][0]["url"] == "https://mp.weixin.qq.com/s?id=proxy-article"
    assert result.data["proxy_fallback_used"] is True
    assert result.data["proxy_account_url_backfilled"] is False


@pytest.mark.asyncio
async def test_fetch_account_article_titles_preserves_partial_read_results_on_timeout(monkeypatch):
    automation = _build_automation()

    async def fake_timeout(label, awaitable, timeout_seconds, default=None):
        if label.startswith("Article readout for "):
            automation._set_partial_article_read_results(
                [
                    {
                        "title": "光模块产能释放，下一个瓶颈轮到材料了？",
                        "content": "正文" * 30,
                        "read_success": True,
                        "url": "https://mp.weixin.qq.com/s?id=optic",
                    }
                ]
            )
            awaitable.close()
            return default
        return await awaitable

    async def fake_prepare():
        return {"X": 10, "Y": 20, "Width": 900, "Height": 760}

    async def fake_search(bounds, account_name):
        return AutomationResult(
            status=AutomationStatus.SUCCESS,
            message="ok",
            data={"found": True},
            execution_time=0.1,
        )

    async def fake_select(bounds, account_name):
        return True

    async def fake_scroll(account_name, bounds):
        return None

    async def fake_visible(bounds, max_articles=1):
        return [{"title": "光模块产能释放，下一个瓶颈轮到材料了？"}]

    async def fake_read(bounds, max_articles=1, article_window_title=None):
        await asyncio.sleep(10)
        return []

    automation.get_accessibility_status = lambda: {"permission_required": False}
    automation._get_proxy_history_for_account = lambda account_name, max_articles=1: {
        "account_name": account_name,
        "account_url": "https://mp.weixin.qq.com/s?id=proxy-account",
        "titles": ["财联社24小时快讯"],
        "visible_titles": ["财联社24小时快讯"],
        "read_titles": ["财联社24小时快讯"],
        "articles": [{"title": "财联社24小时快讯"}],
    }
    automation._await_with_timeout = fake_timeout
    automation._prepare_account_fetch_window = fake_prepare
    automation.search_wechat_account = fake_search
    automation.select_account_from_search_results = fake_select
    automation._resolve_article_panel_bounds = lambda bounds, account_name=None: bounds
    automation._scroll_article_list_to_top = fake_scroll
    automation.list_latest_articles = fake_visible
    automation.read_latest_articles = fake_read

    result = await automation.fetch_account_article_titles(
        "财联社",
        max_articles=1,
        read_articles=True,
    )

    assert result.status == AutomationStatus.SUCCESS
    assert result.data["titles"] == ["光模块产能释放，下一个瓶颈轮到材料了？"]
    assert result.data["read_titles"] == ["光模块产能释放，下一个瓶颈轮到材料了？"]
    assert result.data["articles"][0]["title"] == "光模块产能释放，下一个瓶颈轮到材料了？"
    assert result.data["articles"][0]["url"] == "https://mp.weixin.qq.com/s?id=optic"
    assert result.data["proxy_fallback_used"] is False


@pytest.mark.asyncio
async def test_fetch_account_article_titles_recovers_last_completed_article_after_timeout(monkeypatch):
    automation = _build_automation()

    async def fake_timeout(label, awaitable, timeout_seconds, default=None):
        if label.startswith("Article readout for "):
            automation._set_partial_article_read_results(
                [
                    {
                        "title": "光模块产能释放，下一个瓶颈轮到材料了？",
                        "content": "文章标题: 光模块产能释放，下一个瓶颈轮到材料了？",
                        "read_success": True,
                    }
                ]
            )
            automation._set_last_completed_article_read(
                {
                    "title": "同时，多家厂商也透露了扩产计划，例如中际旭创日前在业绩会",
                    "content": "正文" * 60,
                    "read_success": True,
                }
            )
            awaitable.close()
            return default
        return await awaitable

    async def fake_prepare():
        return {"X": 10, "Y": 20, "Width": 900, "Height": 760}

    async def fake_search(bounds, account_name):
        return AutomationResult(
            status=AutomationStatus.SUCCESS,
            message="ok",
            data={"found": True},
            execution_time=0.1,
        )

    async def fake_select(bounds, account_name):
        return True

    async def fake_scroll(account_name, bounds):
        return None

    async def fake_visible(bounds, max_articles=3):
        return [{"title": "光模块产能释放，下一个瓶颈轮到材料了？"}]

    async def fake_read(bounds, max_articles=3, article_window_title=None):
        await asyncio.sleep(10)
        return []

    automation.get_accessibility_status = lambda: {"permission_required": False}
    automation._get_proxy_history_for_account = lambda account_name, max_articles=3: {
        "account_name": account_name,
        "account_url": "https://mp.weixin.qq.com/s?id=proxy-account",
        "titles": ["财联社24小时快讯"],
        "visible_titles": ["财联社24小时快讯"],
        "read_titles": ["财联社24小时快讯"],
        "articles": [{"title": "财联社24小时快讯"}],
    }
    automation._await_with_timeout = fake_timeout
    automation._prepare_account_fetch_window = fake_prepare
    automation.search_wechat_account = fake_search
    automation.select_account_from_search_results = fake_select
    automation._resolve_article_panel_bounds = lambda bounds, account_name=None: bounds
    automation._scroll_article_list_to_top = fake_scroll
    automation.list_latest_articles = fake_visible
    automation.read_latest_articles = fake_read

    result = await automation.fetch_account_article_titles(
        "财联社",
        max_articles=3,
        read_articles=True,
    )

    assert result.status == AutomationStatus.SUCCESS
    assert "同时，多家厂商也透露了扩产计划，例如中际旭创日前在业绩会" in result.data["read_titles"]
    assert any(
        article.get("title") == "同时，多家厂商也透露了扩产计划，例如中际旭创日前在业绩会"
        for article in result.data["articles"]
    )
    assert result.data["proxy_fallback_used"] is False


@pytest.mark.anyio
async def test_fetch_account_article_titles_can_skip_article_readout():
    automation = _build_automation()

    async def fake_prepare():
        return {"X": 10, "Y": 20, "Width": 900, "Height": 760}

    async def fake_search(bounds, account_name):
        return AutomationResult(
            status=AutomationStatus.SUCCESS,
            message=f"searched {account_name}",
            data={"found": True},
            execution_time=0.1,
        )

    async def fake_select(bounds, account_name):
        return True

    async def fake_scroll(account_name, bounds):
        return None

    async def fake_list(bounds, max_articles=10):
        return [
            {
                "title": "达里奥：黄金或成终极避险选项",
                "url": "https://mp.weixin.qq.com/s?id=gold-article",
            }
        ]

    async def fail_read(*args, **kwargs):
        raise AssertionError("read_latest_articles should be skipped in titles-only mode")

    automation.get_accessibility_status = lambda: {"permission_required": False}
    automation._get_proxy_history_for_account = lambda account_name, max_articles=3: {}
    automation._prepare_account_fetch_window = fake_prepare
    automation.search_wechat_account = fake_search
    automation.select_account_from_search_results = fake_select
    automation._resolve_article_panel_bounds = lambda bounds, account_name=None: bounds
    automation._scroll_article_list_to_top = fake_scroll
    automation.list_latest_articles = fake_list
    automation.read_latest_articles = fail_read

    result = await automation.fetch_account_article_titles(
        "财联社",
        max_articles=1,
        read_articles=False,
    )

    assert result.status == AutomationStatus.SUCCESS
    assert result.data["titles"] == ["达里奥：黄金或成终极避险选项"]
    assert result.data["read_titles"] == ["达里奥：黄金或成终极避险选项"]
    assert result.data["articles"][0]["url"] == "https://mp.weixin.qq.com/s?id=gold-article"
    assert result.data["articles"][0]["read_success"] is False
    assert result.data["read_articles"] is False
    assert result.message == "Fetched 1 title(s) for 财联社"


@pytest.mark.anyio
async def test_fetch_account_article_titles_recovers_proxy_when_window_prep_times_out():
    automation = _build_automation()
    proxy_payload = {
        "account_name": "财联社",
        "account_url": "https://mp.weixin.qq.com/s?id=proxy-account",
        "titles": ["达里奥：黄金或成终极避险选项"],
        "articles": [],
    }

    async def fake_timeout(label, awaitable, timeout_seconds, default=None):
        try:
            awaitable.close()
        except Exception:
            pass
        assert label == "WeChat window prep for 财联社"
        return default

    automation.get_accessibility_status = lambda: {"permission_required": False}
    automation._get_proxy_history_for_account = lambda account_name, max_articles=3: proxy_payload
    automation._await_with_timeout = fake_timeout

    result = await automation.fetch_account_article_titles(
        "财联社",
        max_articles=1,
        read_articles=True,
    )

    assert result.status == AutomationStatus.SUCCESS
    assert result.data["titles"] == ["达里奥：黄金或成终极避险选项"]
    assert "window prep failed" in result.message


@pytest.mark.anyio
async def test_fetch_account_article_titles_titles_only_short_circuits_to_proxy_payload():
    automation = _build_automation()
    proxy_payload = {
        "account_name": "财联社",
        "account_url": "https://mp.weixin.qq.com/s?id=proxy-account",
        "titles": ["达里奥：黄金或成终极避险选项"],
        "articles": [],
    }

    async def fail_timeout(*args, **kwargs):
        raise AssertionError("titles-only proxy recovery should not wait on GUI stages")

    automation.get_accessibility_status = lambda: {"permission_required": False}
    automation._get_proxy_history_for_account = lambda account_name, max_articles=3: proxy_payload
    automation._await_with_timeout = fail_timeout

    result = await automation.fetch_account_article_titles(
        "财联社",
        max_articles=1,
        read_articles=False,
    )

    assert result.status == AutomationStatus.SUCCESS
    assert result.data["titles"] == ["达里奥：黄金或成终极避险选项"]
    assert result.data["read_articles"] is False
    assert result.data["account_url"] == "https://mp.weixin.qq.com/s?id=proxy-account"
    assert "without GUI article readout" in result.message


@pytest.mark.anyio
async def test_fetch_account_article_titles_full_read_uses_extended_gui_timeouts(monkeypatch):
    automation = _build_automation()
    observed_timeouts = {}

    async def fake_sleep(_seconds):
        return None

    async def fake_timeout(label, awaitable, timeout_seconds, default=None):
        observed_timeouts[label] = timeout_seconds
        return await awaitable

    async def fake_prepare():
        return {"X": 10, "Y": 20, "Width": 900, "Height": 760}

    async def fake_search(bounds, account_name):
        return AutomationResult(
            status=AutomationStatus.SUCCESS,
            message=f"searched {account_name}",
            data={"found": True, "bounds": bounds},
            execution_time=0.1,
        )

    async def fake_select(bounds, account_name):
        return True

    async def fake_scroll(account_name, bounds):
        return None

    async def fake_list(bounds, max_articles=10):
        return [{"title": "黄金板块再度走强", "url": "https://mp.weixin.qq.com/s?id=gold-1"}]

    async def fake_read(bounds, max_articles=10, article_window_title=None):
        return [
            {
                "title": "黄金板块再度走强",
                "url": "https://mp.weixin.qq.com/s?id=gold-1",
                "content": "gold rally",
                "read_success": True,
            }
        ]

    monkeypatch.setattr(wechat_automation_module.asyncio, "sleep", fake_sleep)
    automation.get_accessibility_status = lambda: {"permission_required": False}
    automation._get_proxy_history_for_account = lambda account_name, max_articles=3: {}
    automation._await_with_timeout = fake_timeout
    automation._prepare_account_fetch_window = fake_prepare
    automation.search_wechat_account = fake_search
    automation.select_account_from_search_results = fake_select
    automation._resolve_article_panel_bounds = lambda bounds, account_name=None: bounds
    automation._scroll_article_list_to_top = fake_scroll
    automation.list_latest_articles = fake_list
    automation.read_latest_articles = fake_read

    result = await automation.fetch_account_article_titles(
        "财联社",
        max_articles=1,
        read_articles=True,
    )

    assert result.status == AutomationStatus.SUCCESS
    assert observed_timeouts["WeChat account search for 财联社"] != WECHAT_ACCOUNT_SEARCH_STAGE_TIMEOUT_SECONDS_READ
    assert observed_timeouts["WeChat account selection for 财联社"] != WECHAT_ACCOUNT_SELECTION_STAGE_TIMEOUT_SECONDS_READ
    assert observed_timeouts["WeChat account search for 财联社"] == wechat_automation_module.WECHAT_ACCOUNT_SEARCH_STAGE_TIMEOUT_SECONDS
    assert observed_timeouts["WeChat account selection for 财联社"] == wechat_automation_module.WECHAT_ACCOUNT_SELECTION_STAGE_TIMEOUT_SECONDS
    assert result.data["read_articles"] is True
    assert result.data["titles"] == ["黄金板块再度走强"]


@pytest.mark.anyio
async def test_fetch_account_article_titles_full_read_extends_retry_selection_timeout(monkeypatch):
    automation = _build_automation()
    observed_timeouts = {}
    selection_calls = {"count": 0}

    async def fake_sleep(_seconds):
        return None

    async def fake_timeout(label, awaitable, timeout_seconds, default=None):
        observed_timeouts[label] = timeout_seconds
        if label == "WeChat account selection for 财联社":
            awaitable.close()
            return default
        return await awaitable

    async def fake_prepare():
        return {"X": 10, "Y": 20, "Width": 900, "Height": 760}

    async def fake_search(bounds, account_name):
        return AutomationResult(
            status=AutomationStatus.SUCCESS,
            message=f"searched {account_name}",
            data={"found": True, "bounds": bounds},
            execution_time=0.1,
        )

    async def fake_select(bounds, account_name):
        selection_calls["count"] += 1
        return True

    async def fake_scroll(account_name, bounds):
        return None

    async def fake_list(bounds, max_articles=10):
        return [{"title": "黄金板块再度走强", "url": "https://mp.weixin.qq.com/s?id=gold-1"}]

    async def fake_read(bounds, max_articles=10, article_window_title=None):
        return [
            {
                "title": "黄金板块再度走强",
                "url": "https://mp.weixin.qq.com/s?id=gold-1",
                "content": "gold rally",
                "read_success": True,
            }
        ]

    monkeypatch.setattr(wechat_automation_module.asyncio, "sleep", fake_sleep)
    automation.get_accessibility_status = lambda: {"permission_required": False}
    automation._get_proxy_history_for_account = lambda account_name, max_articles=3: {}
    automation._await_with_timeout = fake_timeout
    automation._prepare_account_fetch_window = fake_prepare
    automation.search_wechat_account = fake_search
    automation.select_account_from_search_results = fake_select
    automation._resolve_article_panel_bounds = lambda bounds, account_name=None: bounds
    automation._scroll_article_list_to_top = fake_scroll
    automation.list_latest_articles = fake_list
    automation.read_latest_articles = fake_read

    result = await automation.fetch_account_article_titles(
        "财联社",
        max_articles=1,
        read_articles=True,
    )

    assert result.status == AutomationStatus.SUCCESS
    assert selection_calls["count"] == 1
    assert observed_timeouts["WeChat account selection for 财联社"] == wechat_automation_module.WECHAT_ACCOUNT_SELECTION_STAGE_TIMEOUT_SECONDS
    assert observed_timeouts["WeChat account selection retry for 财联社"] == WECHAT_ACCOUNT_SELECTION_STAGE_TIMEOUT_SECONDS_READ


@pytest.mark.anyio
async def test_fetch_account_article_titles_primes_and_clears_article_url_hints(monkeypatch):
    automation = _build_automation()

    async def fake_sleep(_seconds):
        return None

    async def fake_timeout(_label, awaitable, _timeout_seconds, default=None):
        return await awaitable

    async def fake_prepare():
        return {"X": 10, "Y": 20, "Width": 900, "Height": 760}

    async def fake_search(bounds, account_name):
        return AutomationResult(
            status=AutomationStatus.SUCCESS,
            message=f"searched {account_name}",
            data={"found": True, "bounds": bounds},
            execution_time=0.1,
        )

    async def fake_select(bounds, account_name):
        return True

    async def fake_scroll(account_name, bounds):
        return None

    async def fake_list(bounds, max_articles=10):
        return [{"title": "黄金板块再度走强"}]

    observed = {}

    async def fake_read(bounds, max_articles=10, article_window_title=None):
        observed["during_read"] = automation._article_url_hint_for_title("黄金板块再度走强")
        return [
            {
                "title": "黄金板块再度走强",
                "content": "gold rally",
                "read_success": True,
            }
        ]

    proxy_payload = {
        "account_url": "https://mp.weixin.qq.com/mp/profile_ext?action=home&__biz=hint-biz#wechat_redirect",
        "articles": [
            {
                "title": "黄金板块再度走强",
                "url": "https://mp.weixin.qq.com/s?id=gold-hint",
            }
        ],
    }

    monkeypatch.setattr(wechat_automation_module.asyncio, "sleep", fake_sleep)
    automation.get_accessibility_status = lambda: {"permission_required": False}
    automation._get_proxy_history_for_account = lambda account_name, max_articles=3: proxy_payload
    automation._await_with_timeout = fake_timeout
    automation._prepare_account_fetch_window = fake_prepare
    automation.search_wechat_account = fake_search
    automation.select_account_from_search_results = fake_select
    automation._resolve_article_panel_bounds = lambda bounds, account_name=None: bounds
    automation._scroll_article_list_to_top = fake_scroll
    automation.list_latest_articles = fake_list
    automation.read_latest_articles = fake_read

    result = await automation.fetch_account_article_titles(
        "财联社",
        max_articles=1,
        read_articles=True,
    )

    assert result.status == AutomationStatus.SUCCESS
    assert observed["during_read"] == "https://mp.weixin.qq.com/s?id=gold-hint"
    assert automation._article_url_hint_for_title("黄金板块再度走强") == ""


@pytest.mark.anyio
async def test_tool_handler_passes_read_articles_flag_to_automation():
    captured = {}

    class _Automation:
        async def fetch_account_article_titles(self, account_name, max_articles=3, read_articles=True):
            captured["call"] = {
                "account_name": account_name,
                "max_articles": max_articles,
                "read_articles": read_articles,
            }
            return AutomationResult(
                status=AutomationStatus.SUCCESS,
                message="ok",
                data={"titles": [], "read_articles": read_articles},
                execution_time=0.1,
            )

        async def fetch_accounts_latest_articles(self, account_names, max_articles=3, read_articles=True):
            raise AssertionError("single-account path expected")

    handler = WeChatViewerToolHandler(dep_manager=None, automation=_Automation())
    payload = await handler._handle_get_account_article_titles(
        {"account_name": "财联社", "max_articles": 2, "read_articles": False}
    )

    assert captured["call"] == {
        "account_name": "财联社",
        "max_articles": 2,
        "read_articles": False,
    }
    assert payload["success"] is True
    assert payload["data"]["read_articles"] is False


@pytest.mark.anyio
async def test_tool_handler_routes_latest_official_article_tool_to_automation():
    captured = {}

    class _Automation:
        async def open_latest_official_account_article(
            self,
            account_name=None,
            max_articles=1,
            read_articles=True,
            search_keyword="公众号",
        ):
            captured["call"] = {
                "account_name": account_name,
                "max_articles": max_articles,
                "read_articles": read_articles,
                "search_keyword": search_keyword,
            }
            return AutomationResult(
                status=AutomationStatus.SUCCESS,
                message="ok",
                data={
                    "mode": "keyword" if not account_name or account_name == "公众号" else "specific",
                },
                execution_time=0.1,
            )

    handler = WeChatViewerToolHandler(dep_manager=None, automation=_Automation())
    payload = await handler._handle_click_latest_official_article(
        {
            "account_name": "",
            "search_keyword": "公众号",
            "max_articles": 2,
            "read_articles": False,
        }
    )

    assert captured["call"] == {
        "account_name": "",
        "max_articles": 2,
        "read_articles": False,
        "search_keyword": "公众号",
    }
    assert payload["success"] is True
    assert payload["data"]["mode"] == "keyword"


def test_macos_window_manager_uses_bounded_subprocess_timeouts_for_activation():
    class _FakeSubprocess:
        def __init__(self):
            self.calls = []

        def run(self, args, **kwargs):
            self.calls.append((list(args), dict(kwargs)))

            class _Result:
                stdout = ""
                returncode = 0

            return _Result()

    fake_subprocess = _FakeSubprocess()
    manager = MacOSWindowManager(_FakeDepManager({"subprocess": fake_subprocess}))
    manager._get_profile = lambda app_id=None: types.SimpleNamespace(
        name="WeChat",
        bundle_id="com.tencent.xinWeChat",
        process_names=["WeChat"],
        window_titles=["Weixin"],
    )
    manager._raise_preferred_window = lambda profile, name: False

    frontmost_checks = {"count": 0}

    def _is_frontmost(app_id=None):
        frontmost_checks["count"] += 1
        return frontmost_checks["count"] >= 2

    manager.is_frontmost = _is_frontmost

    assert manager.bring_to_front("WeChat") is True

    osascript_calls = [
        kwargs
        for args, kwargs in fake_subprocess.calls
        if args and args[0] == "osascript"
    ]
    open_calls = [
        kwargs
        for args, kwargs in fake_subprocess.calls
        if args and args[0] == "open"
    ]

    assert osascript_calls
    assert all(kwargs.get("timeout") == 3.0 for kwargs in osascript_calls)
    assert open_calls
    assert all(kwargs.get("timeout") == 3.0 for kwargs in open_calls)


def test_macos_window_manager_prefers_visible_process_names_from_quartz():
    class _FakeQuartz:
        kCGWindowListOptionOnScreenOnly = 1
        kCGWindowListExcludeDesktopElements = 2
        kCGNullWindowID = 0

        @staticmethod
        def CGWindowListCopyWindowInfo(options, window_id):
            return [
                {"kCGWindowOwnerName": "WeChat"},
                {"kCGWindowOwnerName": "Google Chrome"},
            ]

    manager = MacOSWindowManager(
        _FakeDepManager({"quartz": _FakeQuartz()})
    )
    profile = types.SimpleNamespace(process_names=["WeChat", "微信"])

    assert manager._ordered_process_names(profile) == ["WeChat"]

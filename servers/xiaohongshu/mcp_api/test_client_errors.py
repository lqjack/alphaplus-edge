import sys
import types

import pytest

from servers.xiaohongshu.mcp_api import client as client_module
from servers.xiaohongshu.mcp_api.client import XiaohongshuAPIClient


class FakeDependencyManager:
    def get_dependency(self, name):
        if name == "xiaohongshu_api":
            return EmptyXhsAPI
        if name == "is_mongodb":
            return lambda: False
        return None


class EmptyXhsAPI:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def extract(self, user_id, download=False, data=True):
        return []


class OrderedNotesXhsAPI:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def extract(self, user_id, download=False, data=True):
        return [
            {
                "作品标题": "older note",
                "作品链接": "https://www.xiaohongshu.com/explore/older",
                "作品描述": "older content",
                "发布时间": "2026-04-27 09:00:00",
            },
            {
                "作品标题": "newest note",
                "作品链接": "https://www.xiaohongshu.com/explore/newest",
                "作品描述": "newest content",
                "发布时间": "2026-04-29 10:00:00",
            },
            {
                "作品标题": "middle note",
                "作品链接": "https://www.xiaohongshu.com/explore/middle",
                "作品描述": "middle content",
                "publish_time": "2026/04/28 08:00:00",
            },
            {
                "作品标题": "missing time note",
                "作品链接": "https://www.xiaohongshu.com/explore/missing",
                "作品描述": "missing time content",
            },
        ]


class ConfigAwareXhsAPI:
    captured_kwargs = None

    def __init__(self, **kwargs):
        type(self).captured_kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def extract(self, user_id, download=False, data=True):
        return []


class FlakyBlankThenValidXhsAPI:
    calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def extract(self, user_id, download=False, data=True):
        type(self).calls += 1
        if type(self).calls == 1:
            return [{}]
        return [
            {
                "作品标题": "stable note",
                "作品链接": "https://www.xiaohongshu.com/explore/stable",
                "作品描述": "stable content",
                "作者昵称": "stable author",
                "发布时间": "2026-04-29 10:00:00",
            }
        ]


@pytest.mark.anyio
async def test_sync_notes_empty_result_is_structured_error():
    client = XiaohongshuAPIClient(FakeDependencyManager())

    result = await client.sync_notes("https://xhslink.com/a/example", limit=3)

    assert result["success"] is False
    assert result["error_code"] == "EMPTY_RESULT"
    assert result["source_url"] == "https://xhslink.com/a/example"
    assert result["next_action"]


@pytest.mark.anyio
async def test_sync_notes_empty_result_includes_browser_login_probe(monkeypatch):
    client = XiaohongshuAPIClient(FakeDependencyManager())

    async def fake_probe(self, source_url):
        return {
            "attempted": True,
            "available": True,
            "method": "playwright_cookie_probe",
            "redirected_to_login": True,
            "final_url": "https://www.xiaohongshu.com/login?redirectPath=...",
            "logged_in": False,
            "note_map_keys": [],
        }

    monkeypatch.setattr(
        XiaohongshuAPIClient,
        "_probe_note_page_access",
        fake_probe,
    )
    monkeypatch.setattr(
        XiaohongshuAPIClient,
        "_refresh_browser_cookies_into_settings",
        staticmethod(lambda: {"attempted": True, "applied": False, "error": "still-invalid"}),
    )

    result = await client.sync_notes("https://xhslink.com/a/example", limit=3)

    assert result["success"] is False
    assert result["error_code"] == "EMPTY_RESULT"
    assert result["browser_probe"]["redirected_to_login"] is True
    assert result["cookie_refresh"]["attempted"] is True
    assert "redirected to login" in result["message"]
    assert "Chrome" in result["next_action"]


class OrderedNotesDependencyManager:
    def get_dependency(self, name):
        if name == "xiaohongshu_api":
            return OrderedNotesXhsAPI
        if name == "is_mongodb":
            return lambda: False
        return None


class ConfigAwareDependencyManager:
    def get_dependency(self, name):
        if name == "xiaohongshu_api":
            return ConfigAwareXhsAPI
        if name == "is_mongodb":
            return lambda: False
        return None


class FlakyBlankThenValidDependencyManager:
    def get_dependency(self, name):
        if name == "xiaohongshu_api":
            return FlakyBlankThenValidXhsAPI
        if name == "is_mongodb":
            return lambda: False
        return None


@pytest.mark.anyio
async def test_sync_notes_sorts_by_latest_publish_time_before_limit():
    client = XiaohongshuAPIClient(OrderedNotesDependencyManager())

    result = await client.sync_notes("https://xhslink.com/a/example", limit=2)

    assert result["success"] is True
    assert result["notes_synced"] == 2
    assert [note["title"] for note in result["notes"]] == ["newest note", "middle note"]


@pytest.mark.anyio
async def test_sync_notes_pushes_missing_publish_time_after_dated_items():
    client = XiaohongshuAPIClient(OrderedNotesDependencyManager())

    result = await client.sync_notes("https://xhslink.com/a/example", limit=4)

    assert result["success"] is True
    assert [note["title"] for note in result["notes"]] == [
        "newest note",
        "middle note",
        "older note",
        "missing time note",
    ]


@pytest.mark.anyio
async def test_sync_notes_loads_service_settings_for_real_xhs_client(monkeypatch):
    class FakeSettings:
        def __init__(self, root):
            self.root = root

        def run(self):
            return {"cookie": "cookie-from-settings", "timeout": 42}

    fake_module = types.ModuleType("source.module")
    fake_module.ROOT = "/tmp/xhs"
    fake_module.Settings = FakeSettings
    monkeypatch.setitem(sys.modules, "source.module", fake_module)
    ConfigAwareXhsAPI.captured_kwargs = None

    client = XiaohongshuAPIClient(ConfigAwareDependencyManager())
    result = await client.sync_notes("https://xhslink.com/a/example", limit=1)

    assert result["success"] is False
    assert result["error_code"] == "EMPTY_RESULT"
    assert ConfigAwareXhsAPI.captured_kwargs == {
        "cookie": "cookie-from-settings",
        "timeout": 42,
    }


@pytest.mark.anyio
async def test_sync_notes_retries_blank_note_payload_until_usable_result():
    FlakyBlankThenValidXhsAPI.calls = 0
    client = XiaohongshuAPIClient(FlakyBlankThenValidDependencyManager())

    refresh_calls = []
    monkeypatch = pytest.MonkeyPatch()
    async def fake_refresh(self, source_url):
        refresh_calls.append(source_url)
        return {"attempted": True, "applied": True, "validated": True}

    monkeypatch.setattr(
        XiaohongshuAPIClient,
        "_refresh_browser_cookies_with_probe",
        fake_refresh,
    )

    result = await client.sync_notes("https://xhslink.com/a/example", limit=1)
    monkeypatch.undo()

    assert result["success"] is True
    assert result["notes_synced"] == 1
    assert result["notes"][0]["title"] == "stable note"
    assert FlakyBlankThenValidXhsAPI.calls == 2
    assert len(refresh_calls) == 1
    assert refresh_calls[0] == "https://xhslink.com/a/example"


@pytest.mark.anyio
async def test_refresh_browser_cookies_with_probe_attaches_validation(monkeypatch):
    client = XiaohongshuAPIClient(FakeDependencyManager())

    monkeypatch.setattr(
        XiaohongshuAPIClient,
        "_refresh_browser_cookies_into_settings",
        staticmethod(lambda: {"attempted": True, "applied": True}),
    )

    async def fake_probe(self, source_url):
        return {
            "attempted": True,
            "available": True,
            "redirected_to_login": True,
            "note_map_keys": ["undefined"],
            "note_title": None,
            "source_url": source_url,
        }

    monkeypatch.setattr(
        XiaohongshuAPIClient,
        "_probe_note_page_access",
        fake_probe,
    )

    result = await client._refresh_browser_cookies_with_probe("https://xhslink.com/a/example")

    assert result["attempted"] is True
    assert result["applied"] is True
    assert result["validated"] is False
    assert result["browser_probe"]["redirected_to_login"] is True

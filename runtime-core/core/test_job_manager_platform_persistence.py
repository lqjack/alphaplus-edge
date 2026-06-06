import sys
import types

from core import job_manager_mcp
from core.job_manager_mcp import (
    _article_payload_from_platform_item,
    _extract_douyin_video_id,
    _extract_kuaishou_principal_id,
    _extract_platform_sync_items,
    _get_tool_name,
    _is_kuaishou_work_source,
    _persist_platform_sync_items,
    _resolve_kuaishou_account_sync_target,
)


def test_extract_platform_sync_items_prefers_real_xiaohongshu_notes():
    result = {
        "success": True,
        "notes": [
            {
                "title": "LA sky",
                "url": "https://www.xiaohongshu.com/explore/69db064a0000000023024503",
            }
        ],
    }

    items = _extract_platform_sync_items("xiaohongshu", result)

    assert len(items) == 1
    assert items[0]["url"].endswith("69db064a0000000023024503")


def test_article_payload_maps_xiaohongshu_note_to_article_fields():
    item = {
        "title": "LA sky",
        "url": "https://www.xiaohongshu.com/explore/69db064a0000000023024503",
        "content": "California sky note",
        "author": "加州momo",
        "publish_time": "1776691289",
        "likes": 12,
        "comments": 3,
    }

    payload = _article_payload_from_platform_item("xiaohongshu", item, 137)

    assert payload["account_id"] == 137
    assert payload["article_title"] == "LA sky"
    assert payload["article_author"] == "加州momo"
    assert payload["article_content_url"].endswith("69db064a0000000023024503")
    assert payload["content_type"] == "xiaohongshu_note"
    assert payload["article_done"] is True
    assert payload["like_count"] == 12
    assert payload["comment_count"] == 3


def test_article_payload_maps_kuaishou_video_to_article_fields():
    item = {
        "caption": "但我也会难过。",
        "url": "https://www.kuaishou.com/short-video/3xndngpns5fhv7u",
        "name": "sky_不火",
        "realLikeCount": "128",
        "viewCount": "1024",
    }

    payload = _article_payload_from_platform_item("kuaishou", item, 138)

    assert payload["account_id"] == 138
    assert payload["article_title"] == "但我也会难过。"
    assert payload["article_author"] == "sky_不火"
    assert payload["article_content_url"].endswith("3xndngpns5fhv7u")
    assert payload["content_type"] == "kuaishou_video"
    assert payload["like_count"] == 128
    assert payload["read_count"] == 1024


def test_extract_platform_sync_items_accepts_single_douyin_detail_payload():
    result = {
        "success": True,
        "data": {
            "desc": "Harness 工程",
            "share_url": "https://www.douyin.com/video/7630882768608925371",
            "nickname": "晓辉博士",
        },
    }

    items = _extract_platform_sync_items("douyin", result)

    assert len(items) == 1
    assert items[0]["share_url"].endswith("7630882768608925371")


def test_extract_platform_sync_items_accepts_telegram_messages_payload():
    result = {
        "success": True,
        "messages": [
            {
                "id": 8,
                "text": "Robotics sector opens strong",
                "channel_id": "@market_news",
            }
        ],
    }

    items = _extract_platform_sync_items("telegram", result)

    assert len(items) == 1
    assert items[0]["text"] == "Robotics sector opens strong"


def test_article_payload_maps_telegram_message_to_article_fields():
    item = {
        "id": 8,
        "text": "Robotics sector opens strong\nSecond line",
        "channel_id": "@market_news",
        "date": "1777692653",
        "views": "1200",
        "reactions": [{"count": 4}, {"count": 6}],
        "reply_count": 3,
    }

    payload = _article_payload_from_platform_item("telegram", item, 91)

    assert payload["account_id"] == 91
    assert payload["article_title"] == "Robotics sector opens strong"
    assert payload["article_author"] == "@market_news"
    assert payload["article_content_url"] == "https://t.me/market_news/8"
    assert payload["content_type"] == "telegram_message"
    assert payload["read_count"] == 1200
    assert payload["like_count"] == 10
    assert payload["comment_count"] == 3


def test_job_manager_main_does_not_shutdown_shared_executor_by_default(monkeypatch):
    calls = {"shutdown": 0}

    class _FakeExecutor:
        def shutdown(self):
            calls["shutdown"] += 1

    monkeypatch.setattr(job_manager_mcp, "get_service_executor", lambda: _FakeExecutor())
    monkeypatch.setattr(
        job_manager_mcp.time,
        "sleep",
        lambda _seconds: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    job_manager_mcp.main()

    assert calls["shutdown"] == 0


def test_job_manager_main_can_shutdown_executor_when_owned(monkeypatch):
    calls = {"shutdown": 0}

    class _FakeExecutor:
        def shutdown(self):
            calls["shutdown"] += 1

    monkeypatch.setattr(job_manager_mcp, "get_service_executor", lambda: _FakeExecutor())
    monkeypatch.setattr(
        job_manager_mcp.time,
        "sleep",
        lambda _seconds: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    job_manager_mcp.main(shutdown_executor=True)

    assert calls["shutdown"] == 1


def test_persist_platform_sync_items_stores_telegram_messages(monkeypatch):
    created_payloads = []
    count_updates = []

    monkeypatch.setattr(
        job_manager_mcp,
        "article_dao",
        types.SimpleNamespace(
            list_by_account=lambda account_id, limit=500: [],
            create=lambda payload: created_payloads.append(payload) or 101,
            count_by_account=lambda account_id: len(created_payloads),
        ),
    )
    monkeypatch.setattr(
        job_manager_mcp,
        "account_dao",
        types.SimpleNamespace(
            update=lambda account_id, payload: count_updates.append((account_id, payload)) or True
        ),
    )

    stored_count = _persist_platform_sync_items(
        "telegram",
        {
            "success": True,
            "messages": [
                {
                    "id": 88,
                    "text": "Battery names move at open",
                    "channel_id": "@market_news",
                }
            ],
        },
        "91",
    )

    assert stored_count == 1
    assert created_payloads[0]["article_title"] == "Battery names move at open"
    assert created_payloads[0]["content_type"] == "telegram_message"
    assert count_updates == [(91, {"counts": 1})]


def test_get_tool_name_routes_telegram_syncs_to_live_channel_tool():
    assert _get_tool_name("telegram", 1, -1, account_id="91") == "telegram_sync_channel"
    assert _get_tool_name("telegram", 1, 77, account_id="91") == "telegram_sync_channel"


def test_extract_douyin_video_id_prefers_video_urls_before_account_sync():
    detail_id = _extract_douyin_video_id(
        "https://www.douyin.com/video/7630882768608925371",
        "7630882768608925371",
    )

    assert detail_id == "7630882768608925371"


def test_extract_kuaishou_principal_id_supports_profile_url():
    principal_id = _extract_kuaishou_principal_id(
        "https://www.kuaishou.com/profile/3xgky8dd3yvdtba"
    )

    assert principal_id == "3xgky8dd3yvdtba"


def test_resolve_kuaishou_account_sync_target_prefers_work_link_for_content_sync():
    target = _resolve_kuaishou_account_sync_target(
        {
            "account_url": "https://www.kuaishou.com/short-video/3xndngpns5fhv7u?authorId=3xgky8dd3yvdtba",
            "account_id_unique": "3xgky8dd3yvdtba",
        }
    )

    assert _is_kuaishou_work_source(target["text"]) is True
    assert target == {
        "tool_name": "sync_content",
        "text": "https://www.kuaishou.com/short-video/3xndngpns5fhv7u?authorId=3xgky8dd3yvdtba",
        "download": False,
    }


def test_resolve_kuaishou_account_sync_target_uses_profile_source_for_account_sync():
    target = _resolve_kuaishou_account_sync_target(
        {
            "account_url": "https://www.kuaishou.com/profile/3xgky8dd3yvdtba",
            "account_id_unique": "3xgky8dd3yvdtba",
        }
    )

    assert target == {
        "tool_name": "sync_account",
        "account_id": "3xgky8dd3yvdtba",
        "force_update": False,
    }


def test_monitor_threads_routes_youtube_account_sync_to_live_content_skill(monkeypatch):
    updates = []
    captured_payload = {}
    app_context_events = []

    class _FakeAppContext:
        def __enter__(self):
            app_context_events.append("enter")
            return self

        def __exit__(self, exc_type, exc, tb):
            app_context_events.append("exit")
            return False

    fake_api_main = types.ModuleType("api.main")
    fake_api_main.app = types.SimpleNamespace(app_context=lambda: _FakeAppContext())
    sys.modules["api.main"] = fake_api_main

    monkeypatch.setattr(
        job_manager_mcp,
        "job_task_adapter",
        types.SimpleNamespace(
            get_by_id=lambda task_id: {
                "id": task_id,
                "task_type": "youtube",
                "operate": 1,
                "account_id": 45,
            },
            update_status=lambda task_id, status, result=None: updates.append(
                (task_id, status, result)
            ),
        ),
    )
    monkeypatch.setattr(
        job_manager_mcp,
        "account_dao",
        types.SimpleNamespace(
            get_by_id=lambda account_id: {
                "id": account_id,
                "platform": "youtube",
                "account_name": "IN核局",
                "account_id": "UCh6gAbFmwsoif41t_jow_QQ",
                "account_url": "",
            }
        ),
    )

    fake_live_module = types.ModuleType("api.rest.services.live_content_sync")

    def _fake_sync_live_content_from_payload(payload):
        captured_payload.update(payload)
        assert app_context_events and app_context_events[-1] == "enter"
        return {"articles_count": 1}

    fake_live_module.sync_live_content_from_payload = _fake_sync_live_content_from_payload
    sys.modules["api.rest.services.live_content_sync"] = fake_live_module

    job_manager_mcp.monitor_threads(
        task_id=9001,
        task_type="youtube",
        article_id=-1,
        operate=1,
        account_id="45",
        user_id="my",
    )

    assert captured_payload["platform"] == "youtube"
    assert captured_payload["account_id"] == 45
    assert captured_payload["account_name"] == "IN核局"
    assert captured_payload["platform_account_id"] == "UCh6gAbFmwsoif41t_jow_QQ"
    assert captured_payload["max_videos"] == 10
    assert app_context_events[:2] == ["enter", "exit"]
    assert updates[-1] == (9001, "completed", "articles_count=1")


def test_monitor_threads_routes_telegram_account_sync_to_live_channel_tool(monkeypatch):
    updates = []
    executor_calls = []

    class _FakeAppContext:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    fake_api_main = types.ModuleType("api.main")
    fake_api_main.app = types.SimpleNamespace(app_context=lambda: _FakeAppContext())
    sys.modules["api.main"] = fake_api_main

    monkeypatch.setattr(
        job_manager_mcp,
        "job_task_adapter",
        types.SimpleNamespace(
            get_by_id=lambda task_id: {
                "id": task_id,
                "task_type": "telegram",
                "operate": 1,
                "account_id": 91,
            },
            update_status=lambda task_id, status, result=None: updates.append(
                (task_id, status, result)
            ),
        ),
    )
    monkeypatch.setattr(
        job_manager_mcp,
        "account_dao",
        types.SimpleNamespace(
            get_by_id=lambda account_id: {
                "id": account_id,
                "platform": "telegram",
                "account_name": "Market News",
                "account_id_unique": "market_news",
            },
            update=lambda account_id, payload: True,
        ),
    )
    monkeypatch.setattr(
        job_manager_mcp,
        "article_dao",
        types.SimpleNamespace(
            list_by_account=lambda account_id, limit=500: [],
            create=lambda payload: True,
            count_by_account=lambda account_id: 1,
        ),
    )

    class _FakeExecutor:
        def submit_call(self, service_alias, function_name, arguments, timeout=None):
            executor_calls.append((service_alias, function_name, arguments, timeout))
            return {
                "success": True,
                "messages": [
                    {
                        "id": 3,
                        "text": "Chip names rise after earnings",
                        "channel_id": "@market_news",
                    }
                ],
            }

    monkeypatch.setattr(job_manager_mcp, "get_service_executor", lambda: _FakeExecutor())

    job_manager_mcp.monitor_threads(
        task_id=9002,
        task_type="telegram",
        article_id=-1,
        operate=1,
        account_id="91",
        user_id="my",
    )

    assert executor_calls[0][0].startswith("telegram_")
    assert executor_calls[0][1] == "telegram_sync_channel"
    assert executor_calls[0][2]["channel_id"] == "@market_news"
    assert executor_calls[0][2]["limit"] == 50
    assert updates[-1] == (9002, "completed", "stored_articles=1")

"""
Xiaohongshu API Client

Handles Xiaohongshu API operations for user and note management.
"""
import asyncio
import json
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List


_SYNC_NOTES_LOCK = asyncio.Lock()
_SYNC_NOTES_RETRY_ATTEMPTS = 3
_SYNC_NOTES_RETRY_DELAY_SECONDS = 1.0
_BROWSER_PROBE_TIMEOUT_MS = 15_000
_BROWSER_PROBE_SETTLE_MS = 3_000
_COOKIE_FILE = Path(__file__).resolve().parents[1] / "xiaohongshu_cookies.json"


class XiaohongshuAPIClient:
    """Client for interacting with Xiaohongshu APIs"""

    def __init__(self, dep_manager):
        self.dep_manager = dep_manager

    @staticmethod
    def _refresh_browser_cookies_into_settings() -> Dict[str, Any]:
        try:
            from cookie_bridge import apply_harvest_to_settings
            from cookie_harvest import harvest_and_persist
        except Exception as exc:  # noqa: BLE001
            return {
                "attempted": False,
                "applied": False,
                "error": str(exc) or exc.__class__.__name__,
            }

        try:
            harvested = harvest_and_persist()
            applied_count = apply_harvest_to_settings()
            return {
                "attempted": True,
                "applied": True,
                "harvested_count": len(harvested),
                "applied_count": applied_count,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "attempted": True,
                "applied": False,
                "error": str(exc) or exc.__class__.__name__,
            }

    async def _refresh_browser_cookies_with_probe(self, source_url: str) -> Dict[str, Any]:
        refresh = self._refresh_browser_cookies_into_settings()
        if not source_url:
            return refresh
        probe = await self._probe_note_page_access(source_url)
        note_map_keys = probe.get("note_map_keys") if isinstance(probe, dict) else []
        if not isinstance(note_map_keys, list):
            note_map_keys = []
        has_note_payload = bool(probe.get("note_title")) or any(
            str(key).strip().lower() != "undefined" for key in note_map_keys
        )
        refresh["browser_probe"] = probe
        refresh["validated"] = bool(
            probe.get("attempted")
            and probe.get("available")
            and not probe.get("redirected_to_login")
            and has_note_payload
        )
        return refresh

    @staticmethod
    def _probe_browser_cookies() -> List[Dict[str, Any]]:
        if not _COOKIE_FILE.is_file():
            return []
        payload = json.loads(_COOKIE_FILE.read_text(encoding="utf-8"))
        raw = payload.get("cookies") if isinstance(payload, dict) else None
        if not isinstance(raw, dict):
            return []
        cookies = []
        for name, value in raw.items():
            if not value:
                continue
            cookies.append(
                {
                    "name": str(name),
                    "value": str(value),
                    "domain": ".xiaohongshu.com",
                    "path": "/",
                    "secure": False,
                    "httpOnly": False,
                }
            )
        return cookies

    async def _probe_note_page_access(self, source_url: str) -> Dict[str, Any]:
        """Validate harvested cookies via cookie_bridge — no Playwright dependency."""
        try:
            from cookie_harvest import is_logged_in
        except ImportError:
            return {
                "attempted": False,
                "available": False,
                "reason": "cookie_harvest_unavailable",
            }

        cookies = self._probe_browser_cookies()
        cookie_dict = {item["name"]: item["value"] for item in cookies if item.get("value")}
        logged_in = is_logged_in(cookie_dict)
        return {
            "attempted": True,
            "available": bool(cookies),
            "method": "cookie_bridge_probe",
            "cookies_loaded": len(cookies),
            "validated": logged_in,
            "redirected_to_login": not logged_in,
            "source_url": source_url or None,
        }

    @staticmethod
    def _build_xhs_instance(xiaohongshu_api):
        """Instantiate the downloader with service settings when available."""
        with suppress(Exception):
            from source.module import ROOT, Settings

            params = Settings(ROOT).run()
            if isinstance(params, dict):
                try:
                    return xiaohongshu_api(**params)
                except TypeError:
                    # Test doubles and older wrappers may not accept kwargs.
                    pass
        return xiaohongshu_api()

    def sync_user(self, user_id: str) -> Dict[str, Any]:
        """Sync Xiaohongshu user information"""
        xiaohongshu_api = self.dep_manager.get_dependency("xiaohongshu_api")
        logger = self.dep_manager.get_dependency("logger")

        if not xiaohongshu_api:
            return {"success": False, "message": "Xiaohongshu API not available"}

        try:
            return {
                "success": False,
                "user_id": user_id,
                "message": "The bundled XHS downloader supports note extraction, not user-profile sync"
            }

        except Exception as e:
            if logger:
                logger.error(f"Failed to sync Xiaohongshu user {user_id}: {e}")
            return {"success": False, "message": str(e)}

    @staticmethod
    def _normalize_publish_timestamp(note: Dict[str, Any]) -> float:
        """Return a comparable timestamp for newest-first note ordering."""
        for key in ("time", "lastUpdateTime", "publish_time", "发布时间"):
            value = note.get(key)
            if value in (None, ""):
                continue
            if isinstance(value, (int, float)):
                numeric = float(value)
                # Xiaohongshu payloads often use millisecond timestamps.
                return numeric / 1000.0 if numeric > 1_000_000_000_000 else numeric
            if isinstance(value, str):
                trimmed = value.strip()
                if not trimmed:
                    continue
                if trimmed.isdigit():
                    numeric = float(trimmed)
                    return numeric / 1000.0 if numeric > 1_000_000_000_000 else numeric
                for fmt in (
                    "%Y-%m-%d %H:%M:%S",
                    "%Y/%m/%d %H:%M:%S",
                    "%Y-%m-%d %H:%M",
                    "%Y/%m/%d %H:%M",
                    "%Y-%m-%d",
                    "%Y/%m/%d",
                ):
                    try:
                        return datetime.strptime(trimmed, fmt).timestamp()
                    except ValueError:
                        continue
        return float("-inf")

    async def sync_notes(self, user_id: str, limit: int = 20) -> Dict[str, Any]:
        """Sync Xiaohongshu user notes"""
        xiaohongshu_api = self.dep_manager.get_dependency("xiaohongshu_api")
        article_adapter = self.dep_manager.get_dependency("article_adapter")
        account_adapter = self.dep_manager.get_dependency("account_adapter")
        is_mongodb = self.dep_manager.get_dependency("is_mongodb")
        logger = self.dep_manager.get_dependency("logger")

        if not xiaohongshu_api:
            return {"success": False, "message": "Xiaohongshu API not available"}

        try:
            # The local XHS library accepts note URLs/share text. It does not
            # expose a public user timeline API, so do not fabricate notes for
            # plain user ids.
            if "xiaohongshu.com" not in user_id and "xhslink.com" not in user_id:
                return {
                    "success": False,
                    "user_id": user_id,
                    "source_url": user_id,
                    "error_code": "UNSUPPORTED_SOURCE_URL",
                    "message": "sync_notes requires Xiaohongshu note URL/share text for real extraction",
                    "next_action": "提供当前可访问的小红书笔记链接或 xhslink.com 分享文本后重试。",
                }

            processed_notes = 0
            normalized_notes: List[Dict[str, Any]] = []
            last_notes_data: List[Dict[str, Any]] = []
            cookie_refresh: Dict[str, Any] | None = None
            for attempt in range(1, _SYNC_NOTES_RETRY_ATTEMPTS + 1):
                async with _SYNC_NOTES_LOCK:
                    async with self._build_xhs_instance(xiaohongshu_api) as xhs:
                        notes_data = await xhs.extract(user_id, download=False, data=True)

                normalized_notes = []
                processed_notes = 0
                last_notes_data = self._coerce_note_list(notes_data)
                for note in last_notes_data[:limit]:
                    normalized = self._normalize_note_record(note)
                    if not normalized:
                        continue
                    normalized_notes.append(normalized)
                    if article_adapter and is_mongodb and is_mongodb():
                        # Check if note already exists
                        existing_note = article_adapter.get_by_url(normalized["url"])
                        if not existing_note:
                            article_adapter.create({
                                "account_id": None,
                                "article_title": normalized["title"],
                                "article_content_url": normalized["url"] or user_id,
                                "article_html": normalized["content"],
                                "content_type": "xiaohongshu_note",
                                "article_publish_time": normalized["publish_time"],
                                "read_count": normalized["raw"].get("收藏数量", 0),
                                "like_count": normalized["likes"],
                            })
                    processed_notes += 1

                if normalized_notes:
                    break
                if logger:
                    logger.warning(
                        "Xiaohongshu sync_notes extracted only blank notes on attempt %s/%s for %s",
                        attempt,
                        _SYNC_NOTES_RETRY_ATTEMPTS,
                        user_id,
                    )
                if attempt == 1:
                    cookie_refresh = await self._refresh_browser_cookies_with_probe(user_id)
                    if logger:
                        logger.info(
                            "Xiaohongshu cookie refresh after blank sync_notes result for %s: %s",
                            user_id,
                            cookie_refresh,
                        )
                if attempt < _SYNC_NOTES_RETRY_ATTEMPTS:
                    await asyncio.sleep(_SYNC_NOTES_RETRY_DELAY_SECONDS)

            if not normalized_notes:
                browser_probe = await self._probe_note_page_access(user_id)
                message = (
                    "Xiaohongshu live extraction returned no usable notes; "
                    "check that the saved account has a valid note URL/share text and usable login/cookies"
                )
                next_action = "确认链接未过期、当前环境有可用小红书登录/cookie 后重试。"
                if browser_probe.get("redirected_to_login"):
                    message = (
                        "Xiaohongshu live extraction returned no usable notes; "
                        "browser login probe was redirected to login, so current saved cookies/profile "
                        "do not grant note-detail access"
                    )
                    next_action = (
                        "先在本机 Chrome 中确认这条小红书笔记可直接打开且处于登录状态，"
                        "重新 harvest cookies 后再重试。"
                    )
                result = {
                    "success": False,
                    "user_id": user_id,
                    "source_url": user_id,
                    "error_code": "EMPTY_RESULT",
                    "notes_synced": 0,
                    "count": 0,
                    "notes": [],
                    "data": [],
                    "raw_notes_count": len(last_notes_data),
                    "message": message,
                    "next_action": next_action,
                    "browser_probe": browser_probe,
                }
                if cookie_refresh:
                    result["cookie_refresh"] = cookie_refresh
                return result

            return {
                "success": True,
                "user_id": user_id,
                "notes_synced": processed_notes,
                "count": len(normalized_notes),
                "notes": normalized_notes,
                "data": normalized_notes,
                "message": f"Successfully synced {processed_notes} notes for user {user_id}"
            }

        except Exception as e:
            if logger:
                logger.error(f"Failed to sync notes for Xiaohongshu user {user_id}: {e}")
            return {"success": False, "message": str(e)}

    @classmethod
    def _coerce_note_list(cls, notes_data: Any) -> List[Dict[str, Any]]:
        if isinstance(notes_data, dict):
            for key in ("notes", "data", "items", "results"):
                if isinstance(notes_data.get(key), list):
                    notes_data = notes_data[key]
                    break
            else:
                notes_data = []
        if not isinstance(notes_data, list):
            return []
        return sorted(
            [note for note in notes_data if isinstance(note, dict)],
            key=cls._normalize_publish_timestamp,
            reverse=True,
        )

    @staticmethod
    def _normalize_note_record(note: Dict[str, Any]) -> Dict[str, Any]:
        title = note.get("作品标题") or note.get("title") or note.get("display_title") or ""
        url = note.get("作品链接") or note.get("url") or note.get("share_url") or ""
        content = (
            note.get("作品描述")
            or note.get("content")
            or note.get("desc")
            or note.get("description")
            or ""
        )
        author = note.get("作者昵称") or note.get("author") or note.get("nickname") or ""
        title = str(title or "").strip()
        url = str(url or "").strip()
        content = str(content or "").strip()
        author = str(author or "").strip()
        if not title or not url or not content:
            return {}
        return {
            "title": title,
            "url": url,
            "content": content,
            "author": author,
            "publish_time": note.get("发布时间") or note.get("publish_time"),
            "likes": note.get("点赞数量") or note.get("likes") or note.get("like_count") or 0,
            "comments": note.get("评论数量") or note.get("comments") or note.get("comment_count") or 0,
            "raw": note,
        }

    def search_notes(self, keyword: str) -> Dict[str, Any]:
        """Search Xiaohongshu notes"""
        xiaohongshu_api = self.dep_manager.get_dependency("xiaohongshu_api")
        article_adapter = self.dep_manager.get_dependency("article_adapter")
        is_mongodb = self.dep_manager.get_dependency("is_mongodb")
        logger = self.dep_manager.get_dependency("logger")

        if not xiaohongshu_api:
            return {"success": False, "message": "Xiaohongshu API not available"}

        try:
            local_results = []
            if article_adapter and is_mongodb and is_mongodb():
                # Search for notes containing the keyword in title or content
                all_notes = article_adapter.list_by_platform("xiaohongshu", limit=100)
                for note in all_notes:
                    if (keyword.lower() in note.get("article_title", "").lower() or
                        keyword.lower() in note.get("article_html", "").lower()):
                        local_results.append({
                            "id": note.get("id"),
                            "title": note.get("article_title"),
                            "url": note.get("article_content_url"),
                            "content": note.get("article_html", "")[:200] + "..." if len(note.get("article_html", "")) > 200 else note.get("article_html", ""),
                            "publish_time": note.get("article_publish_time"),
                            "likes": note.get("like_count", 0)
                        })

            return {
                "success": True,
                "keyword": keyword,
                "results": local_results[:20],
                "total": len(local_results),
                "message": "Searched locally synced Xiaohongshu notes; public keyword search is not exposed by the bundled library"
            }

        except Exception as e:
            if logger:
                logger.error(f"Failed to search Xiaohongshu notes for keyword '{keyword}': {e}")
            return {"success": False, "message": str(e)}

    def delete_note(self, article_id: str) -> Dict[str, Any]:
        """Delete a Xiaohongshu note"""
        article_adapter = self.dep_manager.get_dependency("article_adapter")
        is_mongodb = self.dep_manager.get_dependency("is_mongodb")
        logger = self.dep_manager.get_dependency("logger")

        try:
            if article_adapter and is_mongodb and is_mongodb():
                # Check if article exists
                article = article_adapter.get_by_id(article_id)
                if not article:
                    return {"success": False, "message": f"Article {article_id} not found"}

                # Delete the article
                success = article_adapter.delete(article_id)
                if success:
                    return {
                        "success": True,
                        "article_id": article_id,
                        "message": f"Successfully deleted article {article_id}"
                    }
                else:
                    return {"success": False, "message": f"Failed to delete article {article_id}"}
            else:
                return {"success": False, "message": "Database adapter not available"}

        except Exception as e:
            if logger:
                logger.error(f"Failed to delete Xiaohongshu note {article_id}: {e}")
            return {"success": False, "message": str(e)}

    async def run_scheduled_task(self) -> Dict[str, Any]:
        """Run scheduled synchronization task"""
        account_adapter = self.dep_manager.get_dependency("account_adapter")
        is_mongodb = self.dep_manager.get_dependency("is_mongodb")
        logger = self.dep_manager.get_dependency("logger")

        try:
            if not (account_adapter and is_mongodb and is_mongodb()):
                return {"success": False, "message": "Database adapter not available"}

            # Get all Xiaohongshu accounts
            accounts = account_adapter.list_by_platform("xiaohongshu")
            processed_accounts = 0
            total_notes_synced = 0

            for account in accounts:
                try:
                    account_id = account.get("account_id")
                    if account_id:
                        # Sync notes for this account
                        result = await self.sync_notes(account_id, limit=10)
                        if result.get("success"):
                            processed_accounts += 1
                            total_notes_synced += result.get("notes_synced", 0)

                        if logger:
                            logger.info(f"Scheduled sync completed for account {account_id}")

                except Exception as e:
                    if logger:
                        logger.error(f"Failed to sync account {account.get('account_id')}: {e}")

            return {
                "success": True,
                "accounts_processed": processed_accounts,
                "total_notes_synced": total_notes_synced,
                "message": f"Scheduled task completed: {processed_accounts} accounts processed, {total_notes_synced} notes synced"
            }

        except Exception as e:
            if logger:
                logger.error(f"Failed to run scheduled task: {e}")
            return {"success": False, "message": str(e)}

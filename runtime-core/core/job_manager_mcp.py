# -*- encoding: utf-8 -*-
"""
Unified Job Manager
Supports both MCP and API protocols for service calls.
Automatically discovers services and handles protocol-specific logic.
"""

import traceback
import os
import re
import time
import asyncio
import logging
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from api.rest import mongodb_adapter as _mongodb_adapter

# Service and Protocol management
from core.service_manager import get_service_manager
from core.mcp_executor import get_service_executor

logger = logging.getLogger(__name__)


class _NullJobTaskAdapter:
    @staticmethod
    def get_by_id(_task_id: int) -> Optional[Dict[str, Any]]:
        return None

    @staticmethod
    def create(_data: Dict[str, Any]) -> Optional[int]:
        return None

    @staticmethod
    def get_latest_by_account_and_article(_account_id: int, _article_id: int) -> Optional[Dict[str, Any]]:
        return None

    @staticmethod
    def update_status(_task_id: int, _status: str, _result: Optional[str] = None) -> bool:
        return False


article_dao = getattr(_mongodb_adapter, "article_adapter", None)
account_dao = getattr(_mongodb_adapter, "account_adapter", None)
job_task_adapter = getattr(_mongodb_adapter, "job_task_adapter", None)
if job_task_adapter is None:
    job_task_adapter_cls = getattr(_mongodb_adapter, "JobTaskAdapter", None)
    job_task_adapter = job_task_adapter_cls() if job_task_adapter_cls is not None else _NullJobTaskAdapter()

def _clean_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    return str(value).strip()

def _first_account_value(account: Optional[dict], *keys: str) -> str:
    if not isinstance(account, dict):
        return ""
    for key in keys:
        value = _clean_text(account.get(key))
        if value:
            return value
    return ""

def _extract_douyin_sec_user_id(*values: Any) -> str:
    for value in values:
        text = _clean_text(value)
        if not text:
            continue
        for pattern in (
            r"(?:sec_user_id|sec_uid)=([^&\s#]+)",
            r"/user/([^/?#\s]+)",
        ):
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        if not text.startswith(("http://", "https://")) and len(text) >= 8:
                return text
    return ""

def _extract_douyin_video_id(*values: Any) -> str:
    for value in values:
        text = _clean_text(value)
        if not text:
            continue
        for pattern in (
            r"/video/(\d+)",
            r"(?:aweme_id|detail_id)=([^&\s#]+)",
        ):
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        if text.isdigit() and len(text) >= 10:
            return text
    return ""

def _derive_account_source(account: Optional[dict]) -> str:
    return _first_account_value(
        account,
        "account_url",
        "accountUrl",
        "account_id_unique",
        "accountUniqueId",
        "account_biz",
        "accountBiz",
        "account_id",
        "accountExternalId",
        "url",
        "account_desc",
        "description",
    )

def _is_kuaishou_work_source(source: Any) -> bool:
    text = _clean_text(source).lower()
    if not text:
        return False
    return any(
        token in text
        for token in (
            "v.kuaishou.com/",
            "/short-video/",
            "/fw/photo/",
        )
    )

def _extract_kuaishou_principal_id(*values: Any) -> str:
    for value in values:
        text = _clean_text(value)
        if not text:
            continue
        for pattern in (
            r"(?:principalid|userid)=([^&\s#]+)",
            r"/profile/([^/?#\s]+)",
        ):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        if "://" not in text and len(text) >= 6:
            return text
    return ""

def _resolve_kuaishou_account_sync_target(account: Optional[dict]) -> Dict[str, Any]:
    source = _derive_account_source(account)
    principal_id = _extract_kuaishou_principal_id(
        source,
        _first_account_value(account, "account_id_unique", "accountUniqueId"),
        _first_account_value(account, "account_id", "accountExternalId"),
    )
    if _is_kuaishou_work_source(source):
        return {
            "tool_name": "sync_content",
            "text": source,
            "download": False,
        }
    if principal_id:
        return {
            "tool_name": "sync_account",
            "account_id": principal_id,
            "force_update": False,
        }
    return {}

def _truncate(value: Any, max_length: int) -> str:
    text = _clean_text(value)
    if len(text) <= max_length:
        return text
    return text[:max_length]

def _first_item_value(item: dict, *keys: str) -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return ""

def _int_value(value: Any) -> int:
    if value in (None, ""):
        return 0
    try:
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return 0

def _platform_item_collections(service_name: str) -> tuple[str, ...]:
    if service_name == "telegram":
        return ("messages", "data", "items", "results")
    if service_name == "xiaohongshu":
        return ("notes", "data", "items", "results")
    if service_name == "kuaishou":
        return ("videos", "data", "items", "contents", "results")
    if service_name == "douyin":
        return ("videos", "data", "items", "contents", "results")
    return ()

def _extract_platform_sync_items(service_name: str, parsed_data: Any) -> list[dict]:
    if isinstance(parsed_data, list):
        return [item for item in parsed_data if isinstance(item, dict)]
    if not isinstance(parsed_data, dict):
        return []
    nested_result = parsed_data.get("result")
    if isinstance(nested_result, (dict, list)):
        nested_items = _extract_platform_sync_items(service_name, nested_result)
        if nested_items:
            return nested_items
    for key in _platform_item_collections(service_name):
        value = parsed_data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested_items = _extract_platform_sync_items(service_name, value)
            if nested_items:
                return nested_items
            return [value]
    if service_name in {"douyin", "kuaishou"}:
        detail_item = parsed_data.get("data")
        if isinstance(detail_item, dict):
            return [detail_item]
    return []

def _extract_telegram_channel_id(*values: Any) -> str:
    for value in values:
        text = _clean_text(value)
        if not text:
            continue
        match = re.search(r"(?:https?://)?t\.me/([^/?#\s]+)", text, re.IGNORECASE)
        if match:
            return f"@{match.group(1).strip()}"
        if text.startswith("@"):
            return text
        if text.lstrip("-").isdigit():
            return text
        if "://" not in text and "/" not in text and len(text) >= 3:
            return f"@{text}"
    return ""

def _telegram_message_source_url(item: dict) -> str:
    direct_url = _clean_text(
        _first_item_value(item, "message_url", "url", "link", "permalink", "source_url")
    )
    if direct_url:
        return direct_url

    channel_id = _extract_telegram_channel_id(
        _first_item_value(item, "channel_id", "channel", "username", "chat_id"),
    )
    message_id = _clean_text(_first_item_value(item, "message_id", "id"))
    if channel_id and message_id:
        if channel_id.startswith("@"):
            return f"https://t.me/{channel_id[1:]}/{message_id}"
        return f"telegram://{channel_id}/{message_id}"
    if channel_id:
        return channel_id
    return message_id

def _telegram_reaction_count(item: dict) -> int:
    reactions = item.get("reactions")
    if isinstance(reactions, (int, float, str)):
        return _int_value(reactions)
    if isinstance(reactions, dict):
        return _int_value(
            _first_item_value(reactions, "count", "total", "total_count", "reaction_count")
        )
    if isinstance(reactions, list):
        total = 0
        for reaction in reactions:
            if isinstance(reaction, dict):
                total += _int_value(
                    _first_item_value(reaction, "count", "total", "reaction_count")
                )
            else:
                total += _int_value(reaction)
        return total
    return 0

def _telegram_message_title(item: dict, content: str) -> str:
    explicit_title = _clean_text(_first_item_value(item, "title", "summary", "headline"))
    if explicit_title:
        return explicit_title
    if content:
        first_line = content.splitlines()[0].strip()
        if first_line:
            return first_line[:80]
    message_id = _clean_text(_first_item_value(item, "message_id", "id"))
    if message_id:
        return f"Telegram message {message_id}"
    return "Telegram message"

def _article_payload_from_platform_item(service_name: str, item: dict, account_id: int) -> dict:
    if service_name == "telegram":
        content = _clean_text(
            _first_item_value(item, "text", "message", "content", "caption", "description")
        )
        title = _telegram_message_title(item, content)
        content_url = _telegram_message_source_url(item)
        source_url = content_url
        author = _first_item_value(
            item,
            "author",
            "channel_title",
            "channel_name",
            "username",
            "channel_id",
            "chat_id",
        )
        publish_time = _first_item_value(
            item,
            "publish_time",
            "date",
            "timestamp",
            "time",
        )
        content_type = "telegram_message"
        read_count = _int_value(_first_item_value(item, "views", "read_count", "view_count"))
        like_count = _telegram_reaction_count(item)
        comment_count = _int_value(
            _first_item_value(item, "replies", "reply_count", "comments", "comment_count")
        )
    elif service_name == "xiaohongshu":
        title = _first_item_value(item, "title", "作品标题", "display_title")
        content_url = _first_item_value(item, "url", "作品链接", "share_url", "source_url")
        source_url = _first_item_value(item, "source_url", "url", "作品链接", "share_url")
        author = _first_item_value(item, "author", "作者昵称", "nickname")
        content = _first_item_value(item, "content", "作品描述", "desc", "description")
        publish_time = _first_item_value(item, "publish_time", "发布时间")
        content_type = "xiaohongshu_note"
        read_count = _int_value(_first_item_value(item, "read_count", "收藏数量", "collect_count"))
        like_count = _int_value(_first_item_value(item, "likes", "like_count", "点赞数量"))
        comment_count = _int_value(_first_item_value(item, "comments", "comment_count", "评论数量"))
    else:
        title = _first_item_value(item, "title", "caption", "desc", "description", "aweme_desc")
        content_url = _first_item_value(item, "url", "canonical_url", "source_url", "share_url")
        source_url = _first_item_value(item, "source_url", "url", "canonical_url", "share_url")
        author = _first_item_value(item, "author", "name", "nickname", "author_name")
        content = _first_item_value(item, "content", "caption", "desc", "description", "title", "aweme_desc")
        publish_time = _first_item_value(item, "publish_time", "create_time", "发布时间")
        content_type = "kuaishou_video" if service_name == "kuaishou" else "douyin_video"
        read_count = _int_value(_first_item_value(item, "read_count", "viewCount", "play_count"))
        like_count = _int_value(_first_item_value(item, "likes", "like_count", "realLikeCount", "digg_count"))
        comment_count = _int_value(_first_item_value(item, "comments", "comment_count"))

    if not title:
        title = content or content_url or source_url or f"{service_name} content"
    if not publish_time:
        publish_time = str(int(datetime.now(timezone.utc).timestamp()))

    return {
        "account_id": int(account_id),
        "article_title": _truncate(title, 200),
        "article_author": _truncate(author, 50),
        "article_digest": _truncate(content, 300),
        "article_html": content or json.dumps(item, ensure_ascii=False),
        "article_content_url": _truncate(content_url or source_url, 500),
        "article_source_url": _truncate(source_url or content_url, 500),
        "article_publish_time": _truncate(publish_time, 20),
        "content_type": content_type,
        "article_done": True,
        "article_fail": False,
        "read_count": read_count,
        "like_count": like_count,
        "comment_count": comment_count,
    }

def _article_already_synced(account_id: int, payload: dict) -> bool:
    existing_articles = article_dao.list_by_account(account_id, limit=500) or []
    content_url = payload.get("article_content_url")
    source_url = payload.get("article_source_url")
    title = payload.get("article_title")
    for article in existing_articles:
        if content_url and content_url in {
            article.get("article_content_url"),
            article.get("article_source_url"),
        }:
            return True
        if source_url and source_url in {
            article.get("article_content_url"),
            article.get("article_source_url"),
        }:
            return True
        if title and title == article.get("article_title"):
            return True
    return False

def _persist_platform_sync_items(service_name: str, parsed_data: Any, account_id: Optional[str]) -> int:
    if service_name not in {"douyin", "kuaishou", "xiaohongshu", "telegram"} or not account_id:
        return 0
    try:
        normalized_account_id = int(account_id)
    except (TypeError, ValueError):
        return 0

    stored_count = 0
    for item in _extract_platform_sync_items(service_name, parsed_data):
        payload = _article_payload_from_platform_item(service_name, item, normalized_account_id)
        if not payload.get("article_content_url") and not payload.get("article_title"):
            continue
        if _article_already_synced(normalized_account_id, payload):
            continue
        if article_dao.create(payload):
            stored_count += 1

    if stored_count:
        try:
            account_dao.update(normalized_account_id, {"counts": article_dao.count_by_account(normalized_account_id)})
        except Exception as exc:
            logger.warning(f"Failed to update account {normalized_account_id} article count: {exc}")
    return stored_count

def _get_service_name_for_task(task_type: str, operate: int) -> str:
    """Map task type to service name"""
    if operate in [2, 6]:
        return "ai"

    mapping = {
        'weixin': 'wechat',
        'wechat': 'wechat',
        'article': 'wechat',
        'youtube': 'youtube',
        'douyin': 'douyin',
        'kuaishou': 'kuaishou',
        'xiaohongshu': 'xiaohongshu',
        'xhs': 'xiaohongshu',
        'telegram': 'telegram',
        'bilibili': 'bilibili',
        'cls': 'cls',
        'file': 'file_parser',
        'ai': 'ai',
    }
    return mapping.get(task_type, task_type)

def _get_tool_name(
    service_name: str,
    operate: int,
    article_id: int,
    account_id: str | None = None,
) -> str:
    """Helper to determine tool name based on operation"""
    if service_name == "ai":
        return "analyze_article" if operate == 2 else "deep_think_article"

    if operate == 5:
        return "delete_article" if article_id != -1 else "delete_articles_by_account"

    if article_id != -1:
        # Single
        mapping = {
            "wechat": "wechat_sync_article",
            "douyin": "douyin_video_detail",
            "kuaishou": "sync_content",
            "youtube": "youtube_sync_video",
            "xiaohongshu": "xiaohongshu_content_detail",
            "telegram": "telegram_sync_channel",
            "bilibili": "bilibili_video_detail",
        }
        return mapping.get(service_name, "sync_single_article")
    else:
        if service_name == "youtube":
            return "youtube_sync_channel" if account_id else "youtube_batch_sync"
        # Batch
        mapping = {
            "wechat": "wechat_sync_history",
            "douyin": "douyin_account_videos",
            "kuaishou": "sync_content",
            "xiaohongshu": "sync_notes",
            "telegram": "telegram_sync_channel",
            "bilibili": "bilibili_user_videos",
        }
        return mapping.get(service_name, "sync_batch")

def monitor_threads(
    task_id: Optional[int] = None,
    task_type: Optional[str] = None,
    article_id: int = -1,
    operate: int = -1,
    stage: Optional[str] = None,
    **kwargs
):
    """
    Monitor and execute job tasks.
    Unified version supporting multiple protocols.
    """
    from api.main import app

    task: Optional[dict] = None
    try:
        with app.app_context():
            if task_id:
                task = job_task_adapter.get_by_id(task_id)
                if task:
                    # Robustly retrieve missing fields from task object
                    if task_type is None:
                        task_type = task.get('task_type')
                    if operate == -1:
                        operate = task.get('operate', -1)

                    job_task_adapter.update_status(task_id, "running")

        # Determine service and protocol
        if task_type is None and task_id is None:
            logger.info("Monitor thread started in passive mode (waiting for tasks)")
            return

        service_name = _get_service_name_for_task(task_type, operate)
        if not service_name:
            raise ValueError(f"No service found for task type: {task_type}")

        # Choose protocol based on service
        # env_key = f"PROTOCOL_{service_name.upper()}"
        key = "SERVER_PROTOCOL"
        # Prioritize local environment, fallback to settings default (mcp)
        # protocol = os.getenv(env_key, "mcp").lower()
        protocol = os.getenv(key, "mcp").lower()
        # Note: Remote connection details (URL, Auth) are handled by MCPClientManager
        # via MCP_{PLUGIN}_URL environment variables.
        # This allows transparent switching between Local Stdio and Remote SSE/HTTP.

        service_alias = f"{service_name}_{protocol}"

        # Prepare arguments
        # Ensure account_id is strictly a string if present (handling int 0 or other types)
        raw_account_id = kwargs.pop('account_id', None)
        if raw_account_id is None and task:
            raw_account_id = task.get('account_id')

        account_id = str(raw_account_id) if raw_account_id is not None else None
        account_record = None
        if account_id:
            try:
                with app.app_context():
                    account_record = account_dao.get_by_id(int(account_id))
            except Exception as lookup_error:
                logger.warning(f"Failed to load account {account_id} for sync args: {lookup_error}")
        if not account_record and isinstance(kwargs.get("account"), dict):
            account_payload = kwargs["account"]
            account_record = account_payload.get("raw") if isinstance(account_payload.get("raw"), dict) else account_payload

        # Ensure article_id is strictly a string if present (handling int 0 or other types)
        raw_article_id = article_id
        article_id_str = str(raw_article_id) if raw_article_id is not None and raw_article_id != -1 else None

        task_args = {
            "task_id": task_id,
            "article_id": article_id_str,
            "operate": operate,
            "account_id": account_id,
            **kwargs
        }
        if stage:
            task_args["stage"] = stage

        if (
            service_name == "youtube"
            and article_id_str is None
            and (account_id or stage == "fresh-sub")
        ):
            from api.rest.services.live_content_sync import sync_live_content_from_payload

            live_payload = {
                "platform": "youtube",
                "user_id": kwargs.get("user_id", "my"),
                "max_videos": kwargs.get("max_videos")
                or kwargs.get("max_results")
                or kwargs.get("fetch_count")
                or 10,
                "max_transcribe_items": kwargs.get("max_transcribe_items") or 3,
                "use_browser_credentials": kwargs.get(
                    "use_browser_credentials", True
                ),
                "browser_credentials_browser": kwargs.get(
                    "browser_credentials_browser"
                ),
                "proxy_url": kwargs.get("proxy_url"),
                "auto_stock_workflow": kwargs.get(
                    "auto_stock_workflow", False
                ),
                "execution_policy": kwargs.get("execution_policy"),
                "enable_simulation": kwargs.get("enable_simulation", True),
                "enable_rag": kwargs.get("enable_rag", True),
            }
            if account_id:
                live_payload["account_id"] = int(account_id) if str(account_id).isdigit() else account_id
                if account_record:
                    live_payload["account_name"] = _first_account_value(
                        account_record,
                        "account_name",
                        "name",
                    )
                    live_payload["account_url"] = _first_account_value(
                        account_record,
                        "account_url",
                        "accountUrl",
                        "url",
                    )
                    live_payload["platform_account_id"] = _first_account_value(
                        account_record,
                        "account_id",
                        "accountExternalId",
                        "platform_account_id",
                    )
                    live_payload["account_id_unique"] = _first_account_value(
                        account_record,
                        "account_id_unique",
                        "accountUniqueId",
                    )
                    live_payload["account_biz"] = _first_account_value(
                        account_record,
                        "account_biz",
                        "accountBiz",
                    )

            with app.app_context():
                live_result = sync_live_content_from_payload(live_payload)
            if task:
                with app.app_context():
                    job_task_adapter.update_status(
                        task_id,
                        "completed",
                        f"articles_count={live_result.get('articles_count', 0)}",
                    )
            return

        tool_name = _get_tool_name(
            service_name,
            operate,
            article_id,
            account_id=account_id,
        )
        if article_id_str is None and account_id:
            if service_name == "douyin":
                account_source = _derive_account_source(account_record)
                detail_id = _extract_douyin_video_id(
                    account_source,
                    _first_account_value(account_record, "account_id", "accountExternalId"),
                    _first_account_value(account_record, "account_id_unique", "accountUniqueId"),
                )
                if detail_id:
                    tool_name = "douyin_video_detail"
                    task_args["detail_id"] = detail_id
                else:
                    sec_user_id = _extract_douyin_sec_user_id(
                        account_source,
                        _first_account_value(account_record, "account_biz", "accountBiz"),
                        _first_account_value(account_record, "account_id_unique", "accountUniqueId"),
                        _first_account_value(account_record, "account_id", "accountExternalId"),
                    )
                    if not sec_user_id:
                        raise ValueError("Douyin account sync requires sec_user_id or a video URL/detail_id; no default account is used")
                    task_args["sec_user_id"] = sec_user_id
            elif service_name == "kuaishou":
                kuaishou_target = _resolve_kuaishou_account_sync_target(account_record)
                if not kuaishou_target:
                    raise ValueError(
                        "Kuaishou account sync requires a real作品链接、账号主页链接或 principalId; no default account is used"
                    )
                tool_name = kuaishou_target.pop("tool_name")
                task_args.update(kuaishou_target)
            elif service_name == "xiaohongshu":
                note_source = _derive_account_source(account_record)
                if not note_source:
                    raise ValueError("Xiaohongshu sync requires a note URL/share text; no default account is used")
                if "xiaohongshu.com" not in note_source and "xhslink.com" not in note_source:
                    raise ValueError("Xiaohongshu real sync supports note URL/share text only; user-profile sync is not available")
                task_args["user_id"] = note_source
                task_args.setdefault("limit", kwargs.get("limit", 20))
            elif service_name == "telegram":
                channel_id = _extract_telegram_channel_id(
                    _derive_account_source(account_record),
                    _first_account_value(account_record, "account_id_unique", "accountUniqueId"),
                    _first_account_value(account_record, "account_biz", "accountBiz"),
                    _first_account_value(account_record, "account_id", "accountExternalId"),
                )
                if not channel_id:
                    raise ValueError(
                        "Telegram account sync requires @channel, t.me link, or numeric channel ID"
                    )
                task_args["channel_id"] = channel_id
                task_args.setdefault("limit", kwargs.get("limit", 50))

        logger.info(f"Executing task {task_id} via {service_alias} for {tool_name}")

        executor = get_service_executor()

        timeout = kwargs.get('timeout', 300)
        logger.info(f"Submitting call to {service_alias} (timeout={timeout}s)...")
        result = executor.submit_call(service_alias, tool_name, task_args, timeout=timeout)
        logger.info(f"Call to {service_alias} completed.")

        # Handle Result
        success = False
        error_reason = None

        if result is None:
            error_reason = f"Service {service_alias} returned None"
        else:
            # 鲁棒地解析结果内容
            parsed_data = _robust_parse_mcp_result(result)

            if isinstance(parsed_data, dict):
                success = parsed_data.get('success', True)
                if not success:
                    error_reason = parsed_data.get('message', 'Inner tool failure')
                    # Special handling for session errors
                    if error_reason == "no session" and account_id:
                        logger.warning(f"Session expired for account {account_id}")
                        with app.app_context():
                            account_dao.update(account_id, {'status': 4})
            else:
                # 如果返回了字符串或其他，假设成功但记录
                logger.info(f"Non-dict result received: {parsed_data}")
                success = True

        # Update final status
        if task:
            with app.app_context():
                if success:
                    stored_count = _persist_platform_sync_items(service_name, parsed_data, account_id)
                    result_message = f"stored_articles={stored_count}" if stored_count else None
                    job_task_adapter.update_status(task_id, "completed", result_message)
                else:
                    job_task_adapter.update_status(task_id, "failed", error_reason or "Unknown failure")

    except Exception as e:
        logger.error(f"Error in monitor_threads: {e}")
        logger.error(traceback.format_exc())
        if task:
            with app.app_context():
                job_task_adapter.update_status(task_id, "failed", str(e))

def _robust_parse_mcp_result(result: Any) -> Any:
    """Robustly parse result from MCP or API calls, handling nested JSON and TextContent."""
    try:
        import json
        import re

        # 1. Check for protocol error
        if hasattr(result, 'isError') and result.isError:
            return {"success": False, "message": f"Protocol Error: {result}"}

        # 2. Extract raw text
        text = ""
        if isinstance(result, str):
            text = result
        elif hasattr(result, 'content'):
            parts = []
            content_items = result.content if isinstance(result.content, list) else [result.content]
            for p in content_items:
                if hasattr(p, 'text'):
                    parts.append(p.text)
                elif isinstance(p, dict) and 'text' in p:
                    parts.append(p['text'])
                else:
                    parts.append(str(p))
            text = "".join(parts)
        elif isinstance(result, dict):
            # If it's already a dict, check if it contains a 'content' field that's a string or list
            if "content" in result:
                inner = result["content"]
                if isinstance(inner, str):
                    text = inner
                elif isinstance(inner, list) and inner and "text" in inner[0]:
                    text = inner[0]["text"]
                else:
                    return result # Return as is
            else:
                return result
        else:
            text = str(result)

        # 3. Clean and parse JSON
        text = text.strip()

        # Handle markdown blocks
        if "```" in text:
            blocks = re.findall(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
            if blocks:
                text = blocks[0]

        # Handle stringified TextContent
        if "TextContent(type='text', text='" in text:
            match = re.search(r"text='({.*?})'", text, re.DOTALL)
            if match:
                text = match.group(1).replace("\\n", "\n").replace("\\\"", "\"")

        # Handle nested "response" field (common in some bridge patterns)
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "response" in data and isinstance(data["response"], str):
                # Try to parse the inner response if it looks like JSON
                inner_text = data["response"].strip()
                if "```" in inner_text:
                    inner_blocks = re.findall(r'```(?:json)?\s*(.*?)\s*```', inner_text, re.DOTALL)
                    if inner_blocks:
                        inner_text = inner_blocks[0]

                try:
                    inner_data = json.loads(inner_text)
                    return inner_data
                except:
                    # If inner is not JSON, return outer but maybe the inner response IS what we want
                    return data
            return data
        except:
            # Fallback for plain text success
            if not text:
                return {"success": True}
            return text

    except Exception as e:
        logger.error(f"Error in _robust_parse_mcp_result: {e}")
        return {"success": False, "message": str(e)}

def main(*, shutdown_executor: bool = False):
    """Main loop for background processing.

    The job manager often runs as a background helper inside the main web
    process. In that embedded mode it must not own the global ServiceExecutor
    lifecycle, otherwise a helper-thread exit can shut down the shared
    executor while the API process is still serving requests.
    """
    executor = get_service_executor()
    logger.info("Unified Job Manager started.")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        if shutdown_executor:
            executor.shutdown()

if __name__ == "__main__":
    main(shutdown_executor=True)

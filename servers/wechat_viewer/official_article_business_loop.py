#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Real-data business loop for WeChat official account latest-article capture.

Flow:
1) input account_names / keyword mode
2) open target via automation and click/read latest article(s)
3) deduplicate by article url/title
4) persist new items to local JSONL
5) print run report

Usage:
  python dataproai/src/servers/wechat_viewer/official_article_business_loop.py \
    --account 财联社 \
    --account 东方财富
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from automation.wechat_automation import WeChatAutomation
from mcp_core.llm_protocol import LLMProtocolFactory

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_SRC = SCRIPT_DIR.parent.parent.parent
PROJECT_ROOT = PROJECT_SRC.parent
for path in [str(SCRIPT_DIR), str(SCRIPT_DIR.parent), str(PROJECT_SRC), str(PROJECT_ROOT)]:
    if path not in sys.path:
        sys.path.insert(0, path)

if load_dotenv is not None:
    load_dotenv()


def _normalise_account_list(values: Optional[Iterable[str]]) -> List[str]:
    if not values:
        return []
    results: List[str] = []
    seen = set()
    for value in values:
        if not value:
            continue
        for item in str(value).split(","):
            item = item.strip()
            if item and item not in seen:
                seen.add(item)
                results.append(item)
    return results


def _safe_state_load(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"seen": {}, "last_run_id": ""}
    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        seen = payload.get("seen", {})
        if not isinstance(seen, dict):
            seen = {}
        return {"seen": seen, "last_run_id": payload.get("last_run_id", "")}
    except Exception:
        return {"seen": {}, "last_run_id": ""}


def _safe_state_save(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _article_fingerprint(title: str, url: str) -> str:
    normalized_title = " ".join((title or "").replace("\n", " ").split()).strip()
    url = (url or "").strip()
    raw = f"{url}::{normalized_title}".lower().encode("utf-8")
    return hashlib.sha1(raw).hexdigest()


def _now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _append_jsonl(path: Path, items: List[Dict[str, Any]]) -> None:
    if not items:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def _build_automation():
    dep_manager = importlib.import_module("deps.manager").get_dependency_manager()
    init_result = dep_manager.initialize_all()
    if hasattr(init_result, "__await__"):
        import asyncio

        asyncio.get_event_loop().run_until_complete(init_result)

    try:
        ocr_processor = dep_manager.get_dependency("ocr_processor")
    except Exception:
        ocr_processor = None

    try:
        llm_client = dep_manager.get_dependency("llm_chain")
    except Exception:
        llm_client = None
    if llm_client is None:
        llm_client = LLMProtocolFactory.create_wechat_viewer_llm_client("ai")

    return WeChatAutomation(
        dep_manager=dep_manager,
        ocr_processor=ocr_processor,
        llm_client=llm_client,
    )


def _extract_articles(result_payload: Dict[str, Any], read_articles: bool) -> List[Dict[str, Any]]:
    if not isinstance(result_payload, dict):
        return []
    articles = result_payload.get("articles") or []
    if isinstance(articles, list) and articles:
        return [
            article
            for article in articles
            if isinstance(article, dict) and article.get("title")
        ]

    visible_articles = result_payload.get("visible_articles") or []
    visible_titles = result_payload.get("visible_titles") or []
    visible_read_titles = result_payload.get("read_titles") or []
    if read_articles:
        return []

    merged = []
    used_titles = set()
    for record in list(visible_articles) + [
        {"title": t} for t in visible_titles + visible_read_titles
    ]:
        if not isinstance(record, dict):
            continue
        title = (record.get("title") or "").strip()
        if not title:
            continue
        key = re.sub(r"\s+", "", title)
        if key in used_titles:
            continue
        used_titles.add(key)
        merged.append(
            {
                "title": title,
                "content": record.get("content") or "",
                "url": record.get("url") or record.get("link") or "",
                "read_success": bool(record.get("read_success")),
            }
        )
    return merged


def _business_score(automation: WeChatAutomation, article: Dict[str, Any]) -> float:
    title = article.get("title", "")
    content = article.get("content", "")
    if not hasattr(automation, "_article_trading_signal_score"):
        return 0.0
    try:
        return float(automation._article_trading_signal_score(title, content))
    except Exception:
        return 0.0


async def run_business_loop(
    account_names: List[str],
    *,
    keyword: str = "公众号",
    max_articles: int = 1,
    read_articles: bool = True,
    state_file: Path,
    output_file: Path,
    logger: logging.Logger,
) -> Dict[str, Any]:
    state = _safe_state_load(state_file)
    seen = state.get("seen", {})
    automation = _build_automation()

    requests = []
    if account_names:
        for account_name in account_names:
            requests.append(
                {
                    "mode": "specific",
                    "account_name": account_name,
                    "kwargs": {
                        "account_name": account_name,
                        "max_articles": max_articles,
                        "read_articles": read_articles,
                    },
                }
            )
    else:
        requests.append(
            {
                "mode": "keyword",
                "account_name": "",
                "kwargs": {
                    "account_name": None,
                    "max_articles": max_articles,
                    "read_articles": read_articles,
                    "search_keyword": keyword or "公众号",
                },
            }
        )

    run_id = hashlib.sha1(_now_iso().encode("utf-8")).hexdigest()[:12]
    run_snapshot = {
        "run_id": run_id,
        "started_at": _now_iso(),
        "status": "running",
        "requests": [],
        "new_items": [],
        "skipped_items": 0,
        "total_items": 0,
    }

    for request in requests:
        account_name = request["account_name"]
        kwargs = dict(request["kwargs"])

        if "search_keyword" not in kwargs:
            kwargs["search_keyword"] = keyword or "公众号"

        logger.info("Start capture: mode=%s account=%r", request["mode"], account_name)
        result = await automation.open_latest_official_account_article(
            **kwargs
        )
        result_data = getattr(result, "data", None) or {}
        status_name = getattr(result, "status", None)
        status = status_name.name if hasattr(status_name, "name") else str(status_name)
        articles = _extract_articles(result_data, read_articles=read_articles)
        run_snapshot["total_items"] += len(articles)

        request_record = {
            "account_name": account_name,
            "search_keyword": kwargs.get("search_keyword"),
            "status": status,
            "message": getattr(result, "message", ""),
            "mode": result_data.get("mode", request["mode"]),
            "article_count": len(articles),
            "article_titles": [article.get("title") for article in articles],
        }
        run_snapshot["requests"].append(request_record)

        new_items: List[Dict[str, Any]] = []
        for article in articles:
            title = (article.get("title") or "").strip()
            url = (article.get("url") or article.get("link") or "").strip()
            fingerprint = _article_fingerprint(title, url)
            if seen.get(fingerprint):
                run_snapshot["skipped_items"] += 1
                continue

            payload = {
                "run_id": run_id,
                "captured_at": _now_iso(),
                "account_name": account_name or "keyword",
                "mode": request_record["mode"],
                "search_keyword": kwargs.get("search_keyword"),
                "title": title,
                "url": url,
                "content": article.get("content", ""),
                "read_success": bool(article.get("read_success", False)),
                "detection_method": article.get("detection_method", ""),
                "score": _business_score(automation, article),
                "fingerprint": fingerprint,
            }
            seen[fingerprint] = {
                "url": url,
                "title": title,
                "fingerprint": fingerprint,
                "captured_at": _now_iso(),
            }
            run_snapshot["new_items"].append(payload)
            new_items.append(payload)

        if new_items:
            _append_jsonl(output_file, new_items)
            logger.info("Persisted %s new article(s) for %r", len(new_items), account_name)
        else:
            logger.info("No new article(s) for %r", account_name)

    state["seen"] = seen
    state["last_run_id"] = run_id
    _safe_state_save(state_file, state)
    run_snapshot["status"] = "completed"
    run_snapshot["finished_at"] = _now_iso()
    return run_snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Wechat official account business-loop capture (real data)"
    )
    parser.add_argument(
        "--account",
        action="append",
        default=[],
        help="Specific official account name, can repeat or comma-separated",
    )
    parser.add_argument(
        "--keyword",
        default="公众号",
        help="Fallback keyword mode, used when --account is not provided",
    )
    parser.add_argument(
        "--max-articles",
        type=int,
        default=1,
        help="How many latest articles to click/read each account",
    )
    parser.add_argument(
        "--no-read-articles",
        action="store_true",
        help="Skip opening article bodies, only collect visible titles",
    )
    parser.add_argument(
        "--state-file",
        default=str(PROJECT_SRC / "wechat_viewer_business_state.json"),
        help="Path for dedupe state file",
    )
    parser.add_argument(
        "--output-file",
        default=str(PROJECT_SRC / "wechat_viewer_business_items.jsonl"),
        help="Path for new article items (jsonl)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger("wechat-official-business-loop")

    account_names = _normalise_account_list(args.account)
    loop_request = run_business_loop(
        account_names=account_names,
        keyword=args.keyword,
        max_articles=max(1, args.max_articles),
        read_articles=not args.no_read_articles,
        state_file=Path(args.state_file),
        output_file=Path(args.output_file),
        logger=logger,
    )

    import asyncio

    report = asyncio.get_event_loop().run_until_complete(loop_request)

    logger.info("Run snapshot: %s", json.dumps(report, ensure_ascii=False))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

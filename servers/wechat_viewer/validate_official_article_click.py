#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Manual verification script for WeChat official-account article clicking.

Usage:
  python dataproai/src/servers/wechat_viewer/validate_official_article_click.py
"""

import asyncio
import logging
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from deps.manager import get_dependency_manager
from mcp_core.llm_protocol import LLMProtocolFactory
from automation.wechat_automation import WeChatAutomation


def _build_logger() -> logging.Logger:
    logger = logging.getLogger("wechat-official-article-validate")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


def _build_automation(logger: logging.Logger) -> WeChatAutomation:
    dep_manager = get_dependency_manager()
    init_result = dep_manager.initialize_all()
    if asyncio.iscoroutine(init_result):
        # keep bootstrap robust in case init remains async in this environment
        return asyncio.get_event_loop().run_until_complete(_build_automation_async(dep_manager, logger))

    return _build_automation_sync(dep_manager)


async def _build_automation_async(dep_manager, logger: logging.Logger) -> WeChatAutomation:
    ocr_processor = None
    try:
        ocr_processor = dep_manager.get_dependency("ocr_processor")
    except Exception:
        ocr_processor = None
    llm_client = LLMProtocolFactory.create_wechat_viewer_llm_client("ai")
    if llm_client is not None:
        logger.debug("LLM client initialized: %s", type(llm_client).__name__)
    return WeChatAutomation(
        dep_manager=dep_manager,
        ocr_processor=ocr_processor,
        llm_client=llm_client,
    )


def _build_automation_sync(dep_manager) -> WeChatAutomation:
    try:
        ocr_processor = dep_manager.get_dependency("ocr_processor")
    except Exception:
        ocr_processor = None
    llm_client = LLMProtocolFactory.create_wechat_viewer_llm_client("ai")
    return WeChatAutomation(
        dep_manager=dep_manager,
        ocr_processor=ocr_processor,
        llm_client=llm_client,
    )


async def _run() -> int:
    logger = _build_logger()
    dep_manager = get_dependency_manager()
    init_result = dep_manager.initialize_all()
    if asyncio.iscoroutine(init_result):
        await init_result
        ocr_processor = dep_manager.get_dependency("ocr_processor") if hasattr(dep_manager, "get_dependency") else None
    else:
        try:
            ocr_processor = dep_manager.get_dependency("ocr_processor")
        except Exception:
            ocr_processor = None
    llm_client = LLMProtocolFactory.create_wechat_viewer_llm_client("ai")

    automation = WeChatAutomation(
        dep_manager=dep_manager,
        ocr_processor=ocr_processor,
        llm_client=llm_client,
    )

    logger.info("=== 场景1: 精准指定公众号 ===")
    account_result = await automation.open_latest_official_account_article(
        "财联社",
        max_articles=1,
        read_articles=True,
    )
    logger.info("scene1 status=%s message=%s data=%s", account_result.status, account_result.message, account_result.data)

    logger.info("=== 场景2: 搜索关键字'公众号' ===")
    keyword_result = await automation.open_latest_official_account_article(
        None,
        max_articles=1,
        read_articles=True,
        search_keyword="公众号",
    )
    logger.info("scene2 status=%s message=%s data=%s", keyword_result.status, keyword_result.message, keyword_result.data)

    return 0 if account_result.status.name in {"SUCCESS", "PARTIAL_SUCCESS"} and keyword_result.status.name in {"SUCCESS", "PARTIAL_SUCCESS"} else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_run()))

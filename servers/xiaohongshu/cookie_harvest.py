"""
Xiaohongshu cookie harvester — independent of douyin / kuaishou / weixin.

Reads cookies from the user's real, daily-use browser (Chrome/Edge/Firefox/
Safari) for xiaohongshu.com domains and writes them to
``xiaohongshu_cookies.json`` so the xiaohongshu MCP service authenticates
without forcing the user to scan a QR code.

Architecture identical to the douyin / kuaishou / wechat harvesters,
but the file paths, domain list, and required-key set are
xiaohongshu-specific. There is no shared state with any other harvester.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


XIAOHONGSHU_DOMAINS = (
    "xiaohongshu.com",
    ".xiaohongshu.com",
    "www.xiaohongshu.com",
    "edith.xiaohongshu.com",  # API host
)
COOKIE_FILE = Path(__file__).resolve().parent / "xiaohongshu_cookies.json"

MIN_COOKIES_FOR_VALID_HARVEST = 5

# At least one of these proves the user is logged in (web-id alone is anonymous)
XIAOHONGSHU_REQUIRED_KEYS = {"web_session", "a1", "webId", "xsecappid", "unread"}


def _import_browser_cookie3():
    try:
        import browser_cookie3
        return browser_cookie3
    except ImportError as exc:
        raise RuntimeError(
            "browser-cookie3 is not installed. Run: "
            "dataproai/src/servers/xiaohongshu/.mcp_venv/bin/pip install browser-cookie3"
        ) from exc


def _harvest_from_browser(browser_fn, domain: str) -> List:
    try:
        return list(browser_fn(domain_name=domain))
    except Exception as exc:
        logger.debug(f"  {browser_fn.__name__}({domain!r}) failed: {exc}")
        return []


def harvest_xiaohongshu_cookies() -> List:
    bc3 = _import_browser_cookie3()
    sources = [
        getattr(bc3, "chrome", None),
        getattr(bc3, "edge", None),
        getattr(bc3, "brave", None),
        getattr(bc3, "firefox", None),
        getattr(bc3, "safari", None),
    ]
    by_name: Dict[str, "object"] = {}
    for source in sources:
        if source is None:
            continue
        for domain in XIAOHONGSHU_DOMAINS:
            for cookie in _harvest_from_browser(source, domain):
                by_name[cookie.name] = cookie
    return list(by_name.values())


def cookies_to_dict(cookies) -> Dict[str, str]:
    return {c.name: c.value for c in cookies if c.value}


def is_logged_in(cookies_dict: Dict[str, str]) -> bool:
    return any(key in cookies_dict for key in XIAOHONGSHU_REQUIRED_KEYS)


def write_cookie_file(cookies_dict: Dict[str, str], path: Path = COOKIE_FILE) -> None:
    payload = {
        "_harvested_at": int(time.time()),
        "_harvested_at_iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "_source": "browser_cookie3",
        "_count": len(cookies_dict),
        "cookies": cookies_dict,
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    logger.info(f"wrote {len(cookies_dict)} cookies to {path}")


def harvest_and_persist() -> Dict[str, str]:
    cookies = harvest_xiaohongshu_cookies()
    cookies_dict = cookies_to_dict(cookies)
    if len(cookies_dict) < MIN_COOKIES_FOR_VALID_HARVEST:
        raise RuntimeError(
            f"only {len(cookies_dict)} xiaohongshu cookies found in any browser — "
            "log into xiaohongshu.com in Chrome/Edge/Firefox/Safari at least once."
        )
    if not is_logged_in(cookies_dict):
        raise RuntimeError(
            f"harvested {len(cookies_dict)} anonymous cookies but none of "
            f"{sorted(XIAOHONGSHU_REQUIRED_KEYS)} present — login required."
        )
    write_cookie_file(cookies_dict)
    return cookies_dict


def run_continuous_harvest(interval_seconds: int = 1800) -> None:
    logger.info(f"xiaohongshu cookie harvest loop starting, interval={interval_seconds}s")
    while True:
        try:
            d = harvest_and_persist()
            logger.info(
                "harvest ok: %s cookies, candidate_session_cookies=%s",
                len(d),
                is_logged_in(d),
            )
        except RuntimeError as exc:
            logger.warning(f"harvest skipped: {exc}")
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"unexpected harvest error: {exc}")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Harvest xiaohongshu cookies from the user's daily browser")
    p.add_argument("--once", action="store_true")
    p.add_argument("--interval", type=int, default=int(os.environ.get("XIAOHONGSHU_HARVEST_INTERVAL_SECONDS", "1800")))
    p.add_argument("--print", dest="print_cookies", action="store_true")
    args = p.parse_args()

    if args.print_cookies:
        cookies = harvest_xiaohongshu_cookies()
        d = cookies_to_dict(cookies)
        print(json.dumps(d, ensure_ascii=False, indent=2))
        print(f"\n# {len(d)} cookies. candidate_session_cookies={is_logged_in(d)}")
    elif args.once:
        try:
            d = harvest_and_persist()
            print(
                f"OK — wrote {len(d)} cookies. "
                f"candidate_session_cookies={is_logged_in(d)}"
            )
        except RuntimeError as exc:
            print(f"SKIP — {exc}")
            raise SystemExit(1)
    else:
        run_continuous_harvest(args.interval)

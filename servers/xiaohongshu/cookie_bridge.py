"""
Xiaohongshu cookie bridge — reads ``xiaohongshu_cookies.json`` written by
``cookie_harvest.py`` and writes the cookie string into the service's
``settings.yaml`` ``cookie:`` field, which is the format the XHS downloader
actually consumes (``source/module.py:154 self.headers["Cookie"]``).

Why a bridge
------------
The harvester writes a nested JSON with metadata
({"_harvested_at": ..., "cookies": {name: value, ...}}). The xiaohongshu
service's Settings class reads ``settings.yaml`` with a flat string under
``cookie:``. This bridge converts one to the other so we never have to
mutate the harvester output format and never have to change the service's
Settings consumer.

Independent of douyin / kuaishou / weixin
-----------------------------------------
Touches only xiaohongshu paths. No imports from other servers.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Optional

from yaml import safe_load, dump as yaml_dump

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent
HARVEST_FILE = ROOT / "xiaohongshu_cookies.json"
SETTINGS_FILE = ROOT / "settings.yaml"


def _read_harvested_cookies(path: Path = HARVEST_FILE) -> Dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(f"harvester output missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    cookies = payload.get("cookies") if isinstance(payload, dict) else None
    if not isinstance(cookies, dict) or not cookies:
        raise ValueError(f"no cookies found in {path}")
    return {k: v for k, v in cookies.items() if isinstance(k, str) and not k.startswith("_")}


def _cookies_to_header_string(cookies: Dict[str, str]) -> str:
    return "; ".join(f"{name}={value}" for name, value in cookies.items() if value)


def _read_or_default_settings(path: Path = SETTINGS_FILE) -> dict:
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return safe_load(f) or {}


def _write_settings(data: dict, path: Path = SETTINGS_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        yaml_dump(data, f, allow_unicode=True, sort_keys=False)
    tmp.replace(path)


def apply_harvest_to_settings(
    harvest_path: Path = HARVEST_FILE,
    settings_path: Path = SETTINGS_FILE,
) -> int:
    """Read the harvested cookie file and merge it into settings.yaml.

    Returns the number of cookies written into the cookie header. Raises
    FileNotFoundError / ValueError if the harvest is missing or empty —
    we never blow away an existing valid cookie with junk."""
    cookies = _read_harvested_cookies(harvest_path)
    header = _cookies_to_header_string(cookies)
    settings = _read_or_default_settings(settings_path)
    settings["cookie"] = header
    _write_settings(settings, settings_path)
    logger.info(
        f"wrote {len(cookies)} cookies ({len(header)} chars) into {settings_path}"
    )
    return len(cookies)


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Apply harvested cookies to xiaohongshu settings.yaml")
    p.add_argument("--harvest", type=Path, default=HARVEST_FILE)
    p.add_argument("--settings", type=Path, default=SETTINGS_FILE)
    p.add_argument("--print", dest="print_only", action="store_true",
                   help="dry-run: show resulting cookie header but don't write settings")
    args = p.parse_args()

    try:
        if args.print_only:
            cookies = _read_harvested_cookies(args.harvest)
            print(_cookies_to_header_string(cookies))
            print(f"\n# {len(cookies)} cookies")
        else:
            n = apply_harvest_to_settings(args.harvest, args.settings)
            print(f"OK — applied {n} cookies to {args.settings}")
    except (FileNotFoundError, ValueError) as exc:
        print(f"SKIP — {exc}")
        raise SystemExit(1)

"""Browser credential helpers for YouTube yt-dlp calls."""

from __future__ import annotations

import os
import plistlib
import platform
import re
import socket
import subprocess
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional, Sequence, Tuple


YTDLP_BROWSER_NAMES = {
    "brave",
    "chrome",
    "chromium",
    "edge",
    "firefox",
    "opera",
    "safari",
    "vivaldi",
    "whale",
}


BUNDLE_ID_TO_YTDLP_BROWSER = {
    "com.google.chrome": "chrome",
    "com.google.chrome.canary": "chrome",
    "com.apple.safari": "safari",
    "org.mozilla.firefox": "firefox",
    "com.microsoft.edgemac": "edge",
    "com.brave.browser": "brave",
    "org.chromium.chromium": "chromium",
    "com.vivaldi.vivaldi": "vivaldi",
    "com.operasoftware.opera": "opera",
    "kr.co.whale.browser": "whale",
}


DEFAULT_BROWSER_FALLBACK_ORDER = (
    "chrome",
    "chromium",
    "brave",
    "edge",
    "firefox",
    "safari",
    "vivaldi",
    "opera",
    "whale",
)

DEFAULT_PROXY_CANDIDATES = (
    "socks5h://127.0.0.1:10808",
    "http://127.0.0.1:10808",
)


def normalize_browser_name(browser: Any) -> Optional[str]:
    """Return a yt-dlp browser name from a browser name or bundle id."""
    if browser in (None, ""):
        return None

    value = str(browser).strip().lower()
    if not value:
        return None

    if value in YTDLP_BROWSER_NAMES:
        return value

    mapped = BUNDLE_ID_TO_YTDLP_BROWSER.get(value)
    if mapped:
        return mapped

    compact = re.sub(r"[^a-z0-9]+", "", value)
    aliases = {
        "googlechrome": "chrome",
        "chromecanary": "chrome",
        "microsoftedge": "edge",
        "bravebrowser": "brave",
        "mozillafirefox": "firefox",
    }
    return aliases.get(compact)


def macos_default_browser() -> Optional[str]:
    """Detect the user's default macOS web browser through LaunchServices."""
    if platform.system() != "Darwin":
        return None

    try:
        proc = subprocess.run(
            [
                "defaults",
                "export",
                "com.apple.LaunchServices/com.apple.launchservices.secure",
                "-",
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=3,
        )
    except Exception:
        return None

    if proc.returncode != 0 or not proc.stdout:
        return None

    try:
        launch_services = plistlib.loads(proc.stdout)
    except Exception:
        return None

    handlers = launch_services.get("LSHandlers", [])
    if not isinstance(handlers, list):
        return None

    prioritized_handlers: List[Dict[str, Any]] = []
    fallback_handlers: List[Dict[str, Any]] = []
    for handler in handlers:
        if not isinstance(handler, dict):
            continue
        content_type = handler.get("LSHandlerContentType")
        scheme = handler.get("LSHandlerURLScheme")
        if content_type == "com.apple.default-app.web-browser":
            prioritized_handlers.insert(0, handler)
        elif scheme == "https":
            prioritized_handlers.append(handler)
        elif scheme == "http":
            fallback_handlers.append(handler)

    for handler in [*prioritized_handlers, *fallback_handlers]:
        browser = normalize_browser_name(handler.get("LSHandlerRoleAll"))
        if browser:
            return browser
    return None


def configured_browser() -> Optional[str]:
    """Read an explicit YouTube browser credential override from environment."""
    for key in (
        "DATAPROAI_YOUTUBE_COOKIES_BROWSER",
        "YOUTUBE_COOKIES_BROWSER",
        "DATAPROAI_BROWSER_COOKIES_BROWSER",
    ):
        browser = normalize_browser_name(os.environ.get(key))
        if browser:
            return browser
    return None


def default_browser() -> Optional[str]:
    """Return the best detected browser for user credentials."""
    return configured_browser() or macos_default_browser()


def browser_cookie_sources(preferred_browser: Any = None) -> List[Tuple[str, ...]]:
    """
    Return yt-dlp cookiesfrombrowser sources, with the user's default browser first.

    A caller-provided browser is treated as an explicit request. Otherwise the
    OS default browser is preferred, then common installed browsers are tried as
    fallbacks for machines where LaunchServices cannot be read.
    """
    ordered: List[str] = []
    explicit = normalize_browser_name(preferred_browser)
    detected = explicit or default_browser()
    if detected:
        ordered.append(detected)
    for browser in DEFAULT_BROWSER_FALLBACK_ORDER:
        if browser not in ordered:
            ordered.append(browser)
    return [(browser,) for browser in ordered]


def apply_browser_credentials(
    ydl_opts: Dict[str, Any],
    *,
    preferred_browser: Any = None,
    enabled: bool = True,
) -> Dict[str, Any]:
    """Return a copy of yt-dlp options with default-browser cookies enabled."""
    options = dict(ydl_opts)
    if not enabled:
        return options

    sources = browser_cookie_sources(preferred_browser)
    if sources:
        options["cookiesfrombrowser"] = sources[0]
    return options


def describe_cookie_source(cookie_source: Optional[Sequence[str]]) -> str:
    """Human-readable label for logs without exposing cookie values."""
    if not cookie_source:
        return "none"
    return ":".join(str(part) for part in cookie_source if part)


def normalize_proxy_url(proxy: Any) -> Optional[str]:
    """Return a normalized proxy URL or None when the input is unusable."""
    if proxy in (None, ""):
        return None

    value = str(proxy).strip()
    if not value:
        return None

    if "://" not in value:
        value = f"http://{value}"

    parsed = urlparse(value)
    if not parsed.scheme or not parsed.hostname or not parsed.port:
        return None
    return value


def configured_proxy_url(preferred_proxy: Any = None) -> Optional[str]:
    """Return an explicit or environment-configured proxy URL."""
    explicit = normalize_proxy_url(preferred_proxy)
    if explicit:
        return explicit

    for key in (
        "DATAPROAI_YOUTUBE_PROXY_URL",
        "YOUTUBE_PROXY_URL",
        "DATAPROAI_PROXY_URL",
        "ALL_PROXY",
        "HTTPS_PROXY",
        "HTTP_PROXY",
    ):
        configured = normalize_proxy_url(os.environ.get(key))
        if configured:
            return configured
    return None


def detect_local_proxy_url() -> Optional[str]:
    """Return the first reachable local proxy candidate."""
    for candidate in DEFAULT_PROXY_CANDIDATES:
        parsed = urlparse(candidate)
        host = parsed.hostname
        port = parsed.port
        if not host or not port:
            continue
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return candidate
        except OSError:
            continue
    return None


def resolve_ytdlp_proxy(
    preferred_proxy: Any = None,
    *,
    auto_detect: bool = True,
) -> Optional[str]:
    """Resolve the proxy URL used for yt-dlp network calls."""
    configured = configured_proxy_url(preferred_proxy)
    if configured:
        return configured
    if auto_detect:
        return detect_local_proxy_url()
    return None

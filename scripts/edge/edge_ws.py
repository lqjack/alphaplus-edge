# -*- coding: utf-8 -*-
"""Production WebSocket URL helpers for Edge tunnel clients."""

from __future__ import annotations

import os
from urllib.parse import quote, urlparse, urlunparse


def gateway_public_base_url(gateway_url: str) -> str:
    explicit = (os.getenv("GATEWAY_PUBLIC_URL") or os.getenv("EDGE_GATEWAY_PUBLIC_URL") or "").strip()
    if explicit:
        return explicit.rstrip("/")
    return (gateway_url or "").strip().rstrip("/")


def gateway_ws_url(*, gateway_url: str, token: str, path: str = "/api/edge/tunnel/ws") -> str:
    base = gateway_public_base_url(gateway_url)
    parsed = urlparse(base)
    scheme = parsed.scheme.lower()
    if scheme == "https":
        ws_scheme = "wss"
    elif scheme == "http":
        ws_scheme = "ws"
    elif scheme in {"wss", "ws"}:
        ws_scheme = scheme
        base = urlunparse(parsed._replace(scheme="https" if scheme == "wss" else "http"))
        parsed = urlparse(base)
    else:
        ws_scheme = "ws"

    netloc = parsed.netloc or parsed.path
    normalized_path = path if path.startswith("/") else f"/{path}"
    query = f"token={quote(token, safe='')}"
    return urlunparse((ws_scheme, netloc, normalized_path, "", query, ""))


def tunnel_ssl_context():
    """Return None (default verify) unless insecure skip is explicitly enabled."""
    if (os.getenv("EDGE_TUNNEL_INSECURE_SKIP_VERIFY") or "").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return None

    import ssl

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

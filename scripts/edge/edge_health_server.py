#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal Edge health + local MCP tool callback server."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List


def _edge_services() -> List[str]:
    raw = os.getenv("EDGE_SERVICES", "xiaohongshu,wx_cli,opencli_weixin,wechat_viewer")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _service_health(service: str) -> Dict[str, Any]:
    try:
        from core.service_ports import get_port

        port = get_port(service, "api")
    except Exception:
        port = None
    return {"service": service, "port": port, "status": "unknown"}


class EdgeHealthHandler(BaseHTTPRequestHandler):
    server_version = "EdgeHealth/1.0"

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") == "/health":
            services = [_service_health(name) for name in _edge_services()]
            self._send_json(
                200,
                {
                    "ok": True,
                    "edge_id": os.getenv("EDGE_ID", "local"),
                    "services": services,
                    "timestamp": time.time(),
                },
            )
            return
        self._send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path.rstrip("/") != "/api/tools/call":
            self._send_json(404, {"ok": False, "error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            payload = json.loads(raw or "{}")
        except json.JSONDecodeError:
            self._send_json(400, {"ok": False, "error": "invalid json"})
            return

        server = str(payload.get("server") or "").strip()
        name = str(payload.get("name") or "").strip()
        arguments = payload.get("arguments") if isinstance(payload.get("arguments"), dict) else {}
        if not server or not name:
            self._send_json(400, {"ok": False, "error": "server and name are required"})
            return

        try:
            from core.service_ports import get_port

            port = get_port(server, "api")
        except Exception as exc:
            self._send_json(502, {"ok": False, "error": f"unknown service {server}: {exc}"})
            return

        import urllib.request

        request_body = json.dumps({"name": name, "arguments": arguments}).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/tools/call",
            data=request_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=float(os.getenv("EDGE_TOOL_TIMEOUT", "180"))) as response:
                data = json.loads(response.read().decode("utf-8") or "{}")
        except Exception as exc:
            self._send_json(502, {"ok": False, "error": str(exc), "server": server, "name": name})
            return

        if isinstance(data, dict):
            data.setdefault("transport", "callback")
            data.setdefault("edge_id", os.getenv("EDGE_ID", "local"))
        self._send_json(200, data if isinstance(data, dict) else {"ok": True, "result": data})

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        if os.getenv("EDGE_HEALTH_QUIET", "").lower() in {"1", "true", "yes"}:
            return
        super().log_message(format, *args)


def main() -> int:
    parser = argparse.ArgumentParser(description="Edge health + tool callback server")
    parser.add_argument("--host", default=os.getenv("EDGE_HEALTH_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("EDGE_HEALTH_PORT", "10490")))
    args = parser.parse_args()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    dataproai_src = os.path.join(repo_root, "dataproai", "src")
    if dataproai_src not in sys.path:
        sys.path.insert(0, dataproai_src)

    httpd = ThreadingHTTPServer((args.host, args.port), EdgeHealthHandler)
    print(f"Edge health server listening on http://{args.host}:{args.port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

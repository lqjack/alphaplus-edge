#!/usr/bin/env python3
"""
LIVE Edge gateway tool routing — Gateway /api/edge/tools/call → Edge callback → local MCP.

No mocks. Requires:
  - Gateway on GATEWAY_URL (default http://127.0.0.1:8001)
  - Edge health on EDGE_CALLBACK_BASE_URL with MCP servers on :10350 / :10470 / :10475 / :10485
  - Device registered (bash scripts/edge/register-with-gateway.sh)

Exit 0 when all runnable probes pass; 1 on failure; skips probes when MCP offline.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ProbeResult:
    name: str
    status: str  # pass | fail | skip
    detail: str = ""


def _http_json(
    method: str,
    url: str,
    body: Optional[Dict[str, Any]] = None,
    timeout: float = 180.0,
) -> Tuple[int, Dict[str, Any]]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8") or "{}"
            return response.status, json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            payload = {"detail": raw}
        return exc.code, payload


def _port_up(host: str, port: int) -> bool:
    import socket

    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


def _gateway_edge_tool_call(
    gateway_url: str,
    server: str,
    name: str,
    arguments: Dict[str, Any],
    *,
    edge_id: str = "",
    timeout: float = 180.0,
) -> ProbeResult:
    label = f"gateway→edge:{server}/{name}"
    url = f"{gateway_url.rstrip('/')}/api/edge/tools/call"
    payload: Dict[str, Any] = {"server": server, "name": name, "arguments": arguments}
    if edge_id:
        payload["edge_id"] = edge_id
    status, data = _http_json("POST", url, payload, timeout=timeout)
    if status == 409 and data.get("detail") == "EDGE_OFFLINE":
        return ProbeResult(label, "fail", "EDGE_OFFLINE — register edge + start health server")
    if status >= 400:
        return ProbeResult(label, "fail", f"HTTP {status}: {data}")
    transport = data.get("transport") if isinstance(data, dict) else None
    if transport not in {"callback", "tunnel"}:
        return ProbeResult(label, "fail", f"expected edge transport, got {transport!r}")
    if isinstance(data, dict) and data.get("success") is False:
        err = str(data.get("error") or data.get("message") or "tool returned success=false")
        return ProbeResult(label, "pass", f"routed; tool reported: {err[:200]}")
    return ProbeResult(label, "pass", f"transport={transport}")


def _service_api_port(service: str, default: int) -> int:
    try:
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        src = os.path.join(repo_root, "dataproai", "src")
        if src not in sys.path:
            sys.path.insert(0, src)
        from core.service_ports import get_port

        return int(get_port(service, "api"))
    except Exception:
        return default


def _gateway_edge_opencli_doctor(
    gateway_url: str,
    server: str,
    *,
    edge_id: str = "",
    timeout: float = 180.0,
) -> ProbeResult:
    return _gateway_edge_tool_call(
        gateway_url,
        server,
        "opencli_doctor",
        {},
        edge_id=edge_id,
        timeout=timeout,
    )


def run_probes(args: argparse.Namespace) -> List[ProbeResult]:
    results: List[ProbeResult] = []

    code, health = _http_json("GET", f"{args.gateway_url.rstrip('/')}/health", timeout=5.0)
    if code >= 400:
        results.append(ProbeResult("gateway_health", "fail", f"HTTP {code}"))
        return results
    results.append(ProbeResult("gateway_health", "pass"))

    code, _ = _http_json("GET", f"{args.edge_health_url.rstrip('/')}/health", timeout=5.0)
    if code >= 400:
        results.append(ProbeResult("edge_health", "fail", f"HTTP {code}"))
        return results
    results.append(ProbeResult("edge_health", "pass"))

    xhs_port = _service_api_port("xiaohongshu", 10350)
    if _port_up("127.0.0.1", xhs_port):
        results.append(
            _gateway_edge_opencli_doctor(
                args.gateway_url,
                "xiaohongshu",
                edge_id=args.edge_id,
                timeout=args.timeout,
            )
        )
    else:
        results.append(
            ProbeResult("gateway→edge:xiaohongshu/opencli_doctor", "skip", f":{xhs_port} down")
        )

    wx_port = _service_api_port("wx_cli", 10475)
    if _port_up("127.0.0.1", wx_port):
        results.append(
            _gateway_edge_tool_call(
                args.gateway_url,
                "wx_cli",
                "wx_daemon_status",
                {},
                edge_id=args.edge_id,
                timeout=args.timeout,
            )
        )
        if args.wx_search_query:
            results.append(
                _gateway_edge_tool_call(
                    args.gateway_url,
                    "wx_cli",
                    "wx_search_messages",
                    {"query": args.wx_search_query, "limit": args.wx_search_limit},
                    edge_id=args.edge_id,
                    timeout=args.timeout,
                )
            )
    else:
        results.append(ProbeResult("gateway→edge:wx_cli/wx_daemon_status", "skip", f":{wx_port} down"))

    weixin_port = _service_api_port("opencli_weixin", 10485)
    if _port_up("127.0.0.1", weixin_port):
        results.append(
            _gateway_edge_opencli_doctor(
                args.gateway_url,
                "opencli_weixin",
                edge_id=args.edge_id,
                timeout=args.timeout,
            )
        )
    else:
        results.append(
            ProbeResult("gateway→edge:opencli_weixin/opencli_doctor", "skip", f":{weixin_port} down")
        )

    viewer_port = _service_api_port("wechat_viewer", 10470)
    if _port_up("127.0.0.1", viewer_port):
        results.append(
            _gateway_edge_opencli_doctor(
                args.gateway_url,
                "wechat_viewer",
                edge_id=args.edge_id,
                timeout=args.timeout,
            )
        )
    else:
        results.append(
            ProbeResult("gateway→edge:wechat_viewer/opencli_doctor", "skip", f":{viewer_port} down")
        )

    return results


def main() -> int:
    if os.getenv("SKIP_LIVE_EDGE", "").strip().lower() in {"1", "true", "yes"}:
        print("SKIP: SKIP_LIVE_EDGE=1")
        return 0

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway-url", default=os.getenv("GATEWAY_URL", "http://127.0.0.1:8001"))
    parser.add_argument(
        "--edge-health-url",
        default=os.getenv("EDGE_CALLBACK_BASE_URL", "http://127.0.0.1:10490"),
    )
    parser.add_argument("--edge-id", default=os.getenv("EDGE_ID", "local-edge"))
    parser.add_argument("--wx-search-query", default=os.getenv("EDGE_LIVE_WX_SEARCH_QUERY", "测试"))
    parser.add_argument("--wx-search-limit", type=int, default=int(os.getenv("EDGE_LIVE_WX_SEARCH_LIMIT", "3")))
    parser.add_argument("--timeout", type=float, default=float(os.getenv("EDGE_TOOL_TIMEOUT", "180")))
    args = parser.parse_args()

    print("==> Edge gateway tool LIVE E2E")
    print(f"    gateway: {args.gateway_url}")
    print(f"    edge:    {args.edge_health_url}")
    print(f"    edge_id: {args.edge_id}")

    results = run_probes(args)
    passed = failed = skipped = 0
    for item in results:
        print(f"{item.status.upper()}: {item.name}" + (f" — {item.detail}" if item.detail else ""))
        if item.status == "pass":
            passed += 1
        elif item.status == "fail":
            failed += 1
        else:
            skipped += 1

    print()
    print(f"Summary: {passed} passed, {failed} failed, {skipped} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

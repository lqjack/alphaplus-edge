#!/usr/bin/env python3
"""Real Edge LIVE checks for OpenCLI / wx-cli — no mocks."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class LiveCheckResult:
    name: str
    status: str  # pass | fail | skip
    detail: str = ""
    data: Optional[Dict[str, Any]] = None


def parse_opencli_doctor(stdout: str) -> Tuple[bool, List[str]]:
    """Return (healthy, issues). Treat [FAIL]/[MISSING] lines and Issues bullets as unhealthy."""
    issues: List[str] = []
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("[FAIL]") or stripped.startswith("[MISSING]"):
            issues.append(stripped)
    in_issues = False
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped == "Issues:":
            in_issues = True
            continue
        if in_issues and stripped.startswith("•"):
            issues.append(stripped.lstrip("• ").strip())
    # Deduplicate while preserving order
    seen = set()
    unique: List[str] = []
    for item in issues:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return (len(unique) == 0, unique)


def run_opencli_doctor(bin_name: str = "opencli", timeout: float = 120.0) -> LiveCheckResult:
    if not shutil.which(bin_name):
        return LiveCheckResult("opencli_doctor", "skip", f"{bin_name} not in PATH")
    try:
        proc = subprocess.run(
            [bin_name, "doctor"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return LiveCheckResult("opencli_doctor", "fail", f"{bin_name} doctor timed out after {timeout}s")
    combined = "\n".join(part for part in (proc.stdout, proc.stderr) if part)
    healthy, issues = parse_opencli_doctor(combined)
    if healthy:
        return LiveCheckResult("opencli_doctor", "pass", "opencli doctor healthy")
    detail = "; ".join(issues[:3]) if issues else "opencli doctor reported issues"
    return LiveCheckResult("opencli_doctor", "fail", detail, {"issues": issues, "output": combined[-2000:]})


def run_wx_daemon_status(bin_name: Optional[str] = None, timeout: float = 60.0) -> LiveCheckResult:
    wx_bin = bin_name or os.getenv("WX_CLI_BIN", "wx")
    if not shutil.which(wx_bin):
        return LiveCheckResult("wx_daemon_status", "skip", f"{wx_bin} not in PATH")
    try:
        proc = subprocess.run(
            [wx_bin, "daemon", "status"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return LiveCheckResult("wx_daemon_status", "fail", f"{wx_bin} daemon status timed out")
    out = (proc.stdout or proc.stderr or "").strip()
    if proc.returncode != 0:
        return LiveCheckResult("wx_daemon_status", "fail", out or f"exit {proc.returncode}")
    lowered = out.lower()
    if "not running" in lowered or "not initialized" in lowered or "error" in lowered:
        return LiveCheckResult("wx_daemon_status", "fail", out)
    return LiveCheckResult("wx_daemon_status", "pass", out or "wx daemon running")


def _port_listening(host: str, port: int) -> bool:
    import socket

    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


def probe_mcp_tool(
    port: int,
    tool_name: str,
    arguments: Optional[Dict[str, Any]] = None,
    *,
    host: str = "127.0.0.1",
    timeout: float = 180.0,
) -> LiveCheckResult:
    label = f"mcp:{port}/{tool_name}"
    if not _port_listening(host, port):
        return LiveCheckResult(label, "skip", f"no listener on {host}:{port}")
    body = json.dumps({"name": tool_name, "arguments": arguments or {}}).encode("utf-8")
    req = urllib.request.Request(
        f"http://{host}:{port}/api/tools/call",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return LiveCheckResult(label, "fail", f"HTTP {exc.code}: {raw[:500]}")
    except Exception as exc:
        return LiveCheckResult(label, "fail", str(exc))

    if isinstance(payload, dict) and payload.get("success") is False:
        err = str(payload.get("error") or payload)
        return LiveCheckResult(label, "fail", err, payload)
    return LiveCheckResult(label, "pass", "tool call ok", payload if isinstance(payload, dict) else None)


def resolve_service_port(service: str, channel: str = "api") -> Optional[int]:
    try:
        from core.service_ports import get_port

        return int(get_port(service, channel))
    except Exception:
        return None


def run_edge_live_suite() -> List[LiveCheckResult]:
    results: List[LiveCheckResult] = []
    results.append(run_opencli_doctor())
    results.append(run_wx_daemon_status())

    xhs_port = resolve_service_port("xiaohongshu")
    if xhs_port:
        results.append(probe_mcp_tool(xhs_port, "opencli_doctor"))

    wx_port = resolve_service_port("wx_cli")
    if wx_port:
        results.append(probe_mcp_tool(wx_port, "wx_daemon_status"))
        search_query = os.getenv("EDGE_LIVE_WX_SEARCH_QUERY", "").strip()
        if search_query:
            results.append(
                probe_mcp_tool(
                    wx_port,
                    "wx_search_messages",
                    {"query": search_query, "limit": int(os.getenv("EDGE_LIVE_WX_SEARCH_LIMIT", "3"))},
                )
            )

    for service in ("opencli_weixin", "wechat_viewer"):
        port = resolve_service_port(service)
        if port:
            results.append(probe_mcp_tool(port, "opencli_doctor"))

    return results


def summarize(results: List[LiveCheckResult]) -> Tuple[int, int, int]:
    passed = sum(1 for r in results if r.status == "pass")
    failed = sum(1 for r in results if r.status == "fail")
    skipped = sum(1 for r in results if r.status == "skip")
    return passed, failed, skipped

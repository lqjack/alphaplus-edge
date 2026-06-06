#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Edge WebSocket tunnel client — connects local Edge to cloud Gateway."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Dict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from edge_ws import gateway_ws_url, tunnel_ssl_context


async def _dispatch_local_tool(message: Dict[str, Any]) -> Dict[str, Any]:
    server = str(message.get("server") or "").strip()
    name = str(message.get("name") or "").strip()
    arguments = message.get("arguments") if isinstance(message.get("arguments"), dict) else {}
    callback_base = os.getenv("EDGE_CALLBACK_BASE_URL", "http://127.0.0.1:10490").rstrip("/")
    payload = json.dumps({"server": server, "name": name, "arguments": arguments}).encode("utf-8")
    req = urllib.request.Request(
        f"{callback_base}/api/tools/call",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=float(os.getenv("EDGE_TOOL_TIMEOUT", "180"))) as response:
            data = json.loads(response.read().decode("utf-8") or "{}")
            if isinstance(data, dict):
                data.setdefault("transport", "tunnel")
            return data if isinstance(data, dict) else {"ok": True, "result": data}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "error": body[:300], "status": exc.code}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def run_tunnel(*, gateway_url: str, token: str, edge_id: str) -> None:
    try:
        import websockets
    except ImportError as exc:
        raise SystemExit("websockets package required: pip install websockets") from exc

    ws_url = gateway_ws_url(gateway_url=gateway_url, token=token)
    ssl_context = tunnel_ssl_context()
    while True:
        try:
            connect_kwargs = {"ping_interval": 20, "ping_timeout": 20}
            if ssl_context is not None:
                connect_kwargs["ssl"] = ssl_context
            async with websockets.connect(ws_url, **connect_kwargs) as websocket:
                print(f"[edge-tunnel] connected edge_id={edge_id}", flush=True)
                await websocket.send(json.dumps({"type": "hello", "edge_id": edge_id}))
                while True:
                    raw = await websocket.recv()
                    message = json.loads(raw)
                    msg_type = message.get("type")
                    if msg_type == "tool_call":
                        result = await _dispatch_local_tool(message)
                        await websocket.send(
                            json.dumps(
                                {
                                    "type": "tool_result",
                                    "id": message.get("id"),
                                    "ok": not result.get("error"),
                                    **result,
                                }
                            )
                        )
                    elif msg_type in {"pong", "heartbeat_ack"}:
                        continue
                    elif msg_type == "ping":
                        await websocket.send(json.dumps({"type": "pong"}))
        except Exception as exc:
            print(f"[edge-tunnel] disconnected: {exc}; retrying in 5s", flush=True)
            await asyncio.sleep(5)


def main() -> int:
    parser = argparse.ArgumentParser(description="Edge tunnel client")
    parser.add_argument("--gateway-url", default=os.getenv("GATEWAY_URL", "http://127.0.0.1:8001"))
    parser.add_argument("--token", default=os.getenv("EDGE_DEVICE_TOKEN", ""))
    parser.add_argument("--edge-id", default=os.getenv("EDGE_ID", "local-edge"))
    args = parser.parse_args()
    if not args.token:
        print("EDGE_DEVICE_TOKEN is required", file=sys.stderr)
        return 2
    asyncio.run(run_tunnel(gateway_url=args.gateway_url, token=args.token, edge_id=args.edge_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

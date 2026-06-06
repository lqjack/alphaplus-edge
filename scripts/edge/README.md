# Edge-local stack

User-side bridge for sensitive MCP services (小红书 OpenCLI, wx-cli, 公众号, wechat_viewer).

**独立公开仓（营销 + Demo + 同步导出）：** [`alphaplus-edge/`](../../alphaplus-edge/) · 设计说明 [`docs/architecture/edge-standalone-repo.md`](../../docs/architecture/edge-standalone-repo.md)  
同步命令：`bash scripts/edge/sync-to-standalone-repo.sh`（**不删除** 本目录任何文件）

## Quick start

```bash
export EDGE_ID=local-edge
export EDGE_DEVICE_TOKEN=dev-edge-token
export GATEWAY_URL=http://127.0.0.1:8001

bash scripts/edge/start-edge-stack.sh
bash scripts/edge/edge-doctor.sh
```

## Components

| Script | Purpose |
|--------|---------|
| `start-edge-stack.sh` | Health server (:10490) + WebSocket tunnel + Gateway registration |
| `edge_health_server.py` | Local `/health` and `/api/tools/call` callback |
| `edge_tunnel_client.py` | NAT-friendly tunnel to Gateway `/api/edge/tunnel/ws` |
| `register-with-gateway.sh` | `POST /api/edge/devices/register` |
| `edge-doctor.sh` | Connectivity checks |
| `start-mac-gateway.sh` | macOS 本地启动 Gateway `:8001`（`GATEWAY_SERVICE_AUTOSTART_ENABLED=false`，仅 Edge API） |
| `edge-mcp-lib.sh` | Edge MCP 共享启动库（端口 / Python / 依赖 / 代理清理） |
| `start-edge-mcp.sh` | 启动全部 Edge MCP（`EDGE_MCP_SERVICES` 默认四服务） |
| `verify-edge-mcp.sh` | 四路 MCP `/health` 探针 |
| `verify-edge-live.sh` | LIVE：`opencli doctor` / `wx daemon status` / 本地 MCP 探针（`SKIP_LIVE_EDGE=1` 可跳过） |
| `edge-post-install-wizard.sh` | DMG 安装后向导：doctor → MCP → 可选 Gateway → LIVE → `verify-edge-macos.sh` |
| `harvest-xhs-cookies.sh` | 从 Chrome/Safari 采集 xhs cookie → `settings.yaml`（LIVE 前置） |
| `harvest-wechat-cookies.sh` | 从浏览器采集 mp.weixin.qq.com cookie（对齐 xhs 工作流） |
| `harvest-douyin-cookies.sh` | 从浏览器采集 douyin.com cookie |
| `live-edge-xhs-rag-e2e.sh` | LIVE：xhs share→stock-flow→RAG（`--check-stack` / `--check-auth` / 全链需 `XHS_LIVE_SHARE_URL`） |
| `start-mac-rag-stack.sh` | Mac 最小 cloud stack（gateway + dataproai_backend + RAG + skills + ai + stock） |
| `rotate-device-token.sh` | `POST /api/edge/devices/rotate-token` |
| `edge_ws.py` | 生产 `wss://` URL 构建 |
| `edge-desktop/` | Tauri 桌面安装包 scaffold |

## Env vars

- `EDGE_ID` — device id (default `local-edge`)
- `EDGE_DEVICE_TOKEN` — shared secret with Gateway
- `EDGE_CALLBACK_BASE_URL` — usually `http://127.0.0.1:10490`
- `GATEWAY_URL` — cloud Gateway base URL
- `GATEWAY_PUBLIC_URL` — production HTTPS base for `wss://` tunnel
- `EDGE_TOKEN_GRACE_SECONDS` — old token grace after rotation (default 3600)
- `EDGE_ADMIN_KEY` — ops key for forced rotation
- `EDGE_REGISTRY_STORE=sqlite` — persist devices across Gateway restarts
- `EDGE_REGISTRY_PATH` — SQLite file (default `dataproai/data/edge_registry.sqlite`)
- `VITE_EDGE_HEALTH_URL` — frontend health probe (workbench card)

See [`docs/architecture/edge-local-gateway-deployment.md`](../../docs/architecture/edge-local-gateway-deployment.md).

## WeChat OpenCLI canonical service

- **Canonical:** `opencli_weixin` (`:10485`) — register this for new integrations.
- **Alias:** `wechat_viewer` (`:10470`) — same `OpenCLIWeixinToolHandler`; kept for backward compatibility.

## Python / venv strategy (edge MCP)

| Scope | Python | venv |
|-------|--------|------|
| Edge MCP 四路 | `python3.12` via `edge-mcp-lib.sh` | per-server `.mcp_venv`; `wechat_viewer` 默认 `requirements-opencli.txt`（legacy 用 `requirements-legacy.txt`） |
| Cloud data MCP | `dataproai/.venv` preferred | `service_ports.json` `venv` field |
| Stock backend | `stock/.venv` | reads ports via `service_urls.py` → `service_ports.json` |

Do not hardcode ports in application code; use `core.service_ports.get_port` or `service_urls.service_url`.

## macOS 安装包 (AlphaPlus Edge)

```bash
# 构建 DMG（含 .app + Python runtime + 安装脚本）
bash scripts/edge/build-macos-installer.sh

# 安装
open dist/edge-macos/AlphaPlus-Edge-0.1.0-macos.dmg
# 双击 Install AlphaPlus Edge.command

# 安装后向导（推荐，真 HTTP/MCP，无 mock）
bash scripts/edge/edge-post-install-wizard.sh
# 或仅快速验证
bash scripts/edge/start-mac-gateway.sh   # 本地 :8001（无 autostart，~10s）
bash scripts/edge/verify-edge-macos.sh
# 本地 Gateway + Edge MCP + Gateway 路由 LIVE
bash scripts/edge/start-mac-gateway.sh
bash scripts/edge/start-edge-mcp.sh
bash scripts/edge/verify-edge-mcp.sh
EDGE_START_TUNNEL=false bash scripts/edge/start-edge-stack.sh
bash scripts/edge/live-edge-gateway-tool-e2e.sh
```

产物路径：
- DMG：`dist/edge-macos/AlphaPlus-Edge-0.1.0-macos.dmg`
- App：`~/Applications/AlphaPlus Edge.app`
- Runtime：`~/Library/Application Support/AlphaPlus-Edge/runtime`

详见 [`edge-desktop/README.md`](../../edge-desktop/README.md)。

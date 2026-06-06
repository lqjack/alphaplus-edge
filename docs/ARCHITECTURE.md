# Edge 架构（独立仓摘要）

**完整 SSOT：** dataproaiset [`docs/architecture/edge-local-gateway-deployment.md`](https://github.com/lqjack/dataproaiset/blob/main/docs/architecture/edge-local-gateway-deployment.md)

本文件为 **alphaplus-edge 公开仓** 读者优化版；实现细节以 monorepo 为准，发布前 `scripts/sync-from-monorepo.sh` 对齐。

---

## 1. 拓扑

```text
┌──────────────────────── 用户设备（Edge） ────────────────────────┐
│  Edge Agent (:10490)                                              │
│    ├─ xiaohongshu MCP   :10350 / :10351                          │
│    ├─ wx_cli MCP        :10475 / :10478                          │
│    ├─ opencli_weixin    :10485 / :10488                          │
│    └─ wechat_viewer     :10470 (alias)                           │
│         ↓ OpenCLI / wx-cli / Chrome Bridge                        │
└───────────────────────────────┬──────────────────────────────────┘
                                │ WSS Tunnel + HTTPS
                                ▼
┌──────────────────────── 云端（Cloud） ───────────────────────────┐
│  Neura Gateway :8001                                              │
│    POST /api/tools/call  ·  /api/edge/devices/*  ·  tunnel/ws    │
│  stock · skills_api · RAG · market …                              │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. 数据分级

| 级别 | 示例 | 存放 | 上传 Cloud |
|------|------|------|------------|
| **L0** | Cookie、Chrome profile、wx DB 路径 | 仅 Edge | 否 |
| **L1** | 聊天全文、未脱敏笔记 HTML | Edge 默认 | 否（除非用户「同步 RAG」） |
| **L2** | 标题、标的、情感分、引用片段 | Edge 生成 → Cloud | 是（默认 ingest） |
| **L3** | 行情、公开新闻 | Cloud | 是 |

---

## 3. Edge Agent 模块

| 模块 | 文件 | 职责 |
|------|------|------|
| Health + Callback | `edge_health_server.py` | `:10490/health`，本地 tool callback |
| Tunnel | `edge_tunnel_client.py` | `wss://…/api/edge/tunnel/ws` |
| Registrar | `register-with-gateway.sh` | 设备注册、心跳 |
| Supervisor | `start-edge-mcp.sh` | 拉起四路 Edge MCP |
| Doctor | `edge-doctor.sh` | 连通性 + LIVE 探针 |

---

## 4. Gateway 路由规则

1. `POST /api/tools/call` 解析 `server` + `tool`  
2. 若匹配 `edge_tools.yaml` 前缀 → 查 `edge_id` 隧道 → 转发 Edge  
3. Edge 离线 → **409 EDGE_OFFLINE**（不 fallback 云端 opencli）  
4. 否则 → Cloud MCP

配置：[config/edge_tools.yaml](../config/edge_tools.yaml)

---

## 5. 端口表（Edge 本机）

| 服务 | API | MCP |
|------|-----|-----|
| xiaohongshu | 10350 | 10351 |
| wx_cli | 10475 | 10478 |
| opencli_weixin | 10485 | 10488 |
| wechat_viewer | 10470 | — |
| edge-agent | 10490 | — |

详见 [config/service_ports.edge.json](../config/service_ports.edge.json)

---

## 6. 环境变量

| 变量 | Edge | Cloud |
|------|------|-------|
| `GATEWAY_URL` / `CLOUD_GATEWAY_URL` | 指向 Cloud | localhost:8001 |
| `EDGE_DEVICE_TOKEN` | ✓ | 校验 |
| `OPENCLI_BIN` / `WX_CLI_BIN` | ✓ | ✗ |
| `GATEWAY_PUBLIC_URL` | WSS 基址 | 公网 HTTPS |

完整模板：[.env.example](../.env.example)

---

## 7. 验收命令

```bash
bash scripts/edge/edge-doctor.sh
bash scripts/edge/verify-edge-mcp.sh
SKIP_LIVE_EDGE=1 bash scripts/edge/verify-edge-live.sh
bash scripts/edge/live-edge-gateway-tool-e2e.sh   # 需 Gateway
```

Monorepo 完整清单见 SSOT 文档 §10。

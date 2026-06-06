# 对接 dataproaiset 云端（Neura Gateway）

Edge **不能单独完成投研闭环**——需要 Cloud 侧的 Gateway + Stock + RAG。  
本仓负责本机桥接；Cloud 部署见 [dataproaiset](https://github.com/lqjack/dataproaiset)。

---

## 1. 最小 Cloud 依赖

| 服务 | 端口 | 必需 |
|------|------|------|
| Neura Gateway | 8001 | ✅ |
| stock_backend | 50000 | 内容中枢 / workflow |
| skills_api | 10001 | skill 编排 |
| rag_server_v2 | 40000 | RAG 写入 |
| ai | 10520 | 可选增强 |

**仅测 Edge 路由：** 只需 Gateway（`start-mac-gateway.sh`）。

**测 XHS→RAG 全链：** 见 monorepo `scripts/edge/start-mac-rag-stack.sh`。

---

## 2. 注册流程

```bash
export GATEWAY_URL=https://alphaplus-api.datapro.asia
export EDGE_ID=my-laptop
export EDGE_DEVICE_TOKEN=   # 首次留空，register 返回

bash scripts/edge/register-with-gateway.sh
# 保存返回的 device_token 到 .env.edge
```

API 契约：

| 方法 | 路径 |
|------|------|
| POST | `/api/edge/devices/register` |
| POST | `/api/edge/devices/heartbeat` |
| GET | `/api/edge/devices/{id}/status` |
| POST | `/api/edge/devices/rotate-token` |
| WS | `/api/edge/tunnel/ws` |

---

## 3. Stock 前端配置

| 变量 | Edge 用户典型值 |
|------|----------------|
| `VITE_STOCK_API_URL` | Cloud Gateway `/api/stock` 或 backend 代理 |
| `VITE_EDGE_HEALTH_URL` | `http://127.0.0.1:10490/health` |
| `VITE_DEPLOY_MODE` | `edge` |

工作台 **EdgeBridgeCard** 轮询 health URL，显示 `edge_ready` / `EDGE_OFFLINE`。

---

## 4. 部署画像

| Profile | Cloud | Edge | 用户 |
|---------|-------|------|------|
| **edge-user** | 团队 SaaS Gateway | 本机 Edge 包 | 投研个人 |
| **cloud-team** | 机房全量 Docker | 可选每分析师一台 Edge | 机构 |
| **edge-hybrid** | 本机 Gateway + Edge | 同机 | 开发演示 |
| **EDGE_MODE=local** | monorepo 一机全栈 | 内嵌 | 开发 |

---

## 5. 生产 WSS

```bash
export GATEWAY_PUBLIC_URL=https://alphaplus-api.datapro.asia
# Tunnel: wss://alphaplus-api.datapro.asia/api/edge/tunnel/ws
```

Dev only: `EDGE_TUNNEL_INSECURE_SKIP_VERIFY=1`

持久化注册表（Cloud 侧）：

```bash
export EDGE_REGISTRY_STORE=sqlite
export EDGE_REGISTRY_PATH=/var/lib/alphaplus/edge_registry.sqlite
```

---

## 6. NeuraDesk / Cursor

- MCP 可指向 **本机** Edge MCP 聚合（如 xiaohongshu `:10351`）  
- 或 Cloud Gateway + `X-Edge-Id` 代理路由  
- **禁止** Plugin SSH 到 Cloud 执行 opencli  

NeuraDesk 仓：`llm-gateway`，env `DATAPROAI_GATEWAY_URL`。

---

## 7. 跨仓链接

| 文档 | 位置 |
|------|------|
| Gateway README | dataproaiset `gateway/README.md` |
| Standalone Docker | dataproaiset `docs/operations/standalone-docker-deploy.md` |
| 生态命名 | dataproaiset `docs/architecture/ecosystem-naming.md` |
| Edge SSOT | dataproaiset `docs/architecture/edge-local-gateway-deployment.md` |

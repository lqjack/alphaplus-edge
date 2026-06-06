# AlphaPlus Edge — 演示与 Demo 手册

**目标：** 任何人 clone 本仓后，在 15 分钟内完成「可展示、可录屏、可写进文章」的闭环。

---

## 1. 演示环境分级

| 级别 | 依赖 | 适合 |
|------|------|------|
| **L0 契约** | 仅 Python 3.10+ | CI、无 Gateway |
| **L1 本机栈** | Gateway 本机 `:8001` | 开发者完整路由 |
| **L2 LIVE** | OpenCLI + Chrome + wx-cli | 真 XHS/微信采集 |
| **L3 全链** | L2 + Cloud RAG + stock-flow | 产品级 Demo |

---

## 2. Quickstart Demo（5 分钟，L1）

### 2.1 终端脚本

```bash
# 终端 A — 启动 Cloud Gateway（dataproaiset monorepo）
cd ../dataproaiset
bash scripts/edge/start-mac-gateway.sh   # 或你的 Ubuntu Gateway

# 终端 B — 启动 Edge
cd alphaplus-edge
cp .env.example .env.edge
export $(grep -v '^#' .env.edge | xargs)
export GATEWAY_URL=http://127.0.0.1:8001
export EDGE_DEVICE_TOKEN=dev-edge-token

bash scripts/edge/start-edge-stack.sh
bash scripts/edge/edge-doctor.sh
```

### 2.2 预期输出（录屏要点）

1. `Started edge-health (pid …)`  
2. `OK: edge health reachable` — JSON 含 `"status":"ok"`  
3. `OK: gateway edge API reachable` — 设备列表含 `local-edge`  
4. （可选）OpenCLI / wx 探针 — LIVE 需本机依赖

### 2.3 一键 Demo 脚本

```bash
bash demos/quickstart-demo.sh
```

---

## 3. Gateway → Edge → MCP（L1，无浏览器）

```bash
# Gateway + Edge stack 已启动
bash scripts/edge/live-edge-gateway-tool-e2e.sh
```

**展示点：** Cloud 下发 `opencli_doctor` / `wx_search` → Edge callback → JSON 返回。

---

## 4. 小红书 → RAG 全链（L3）

**前置：** OpenCLI 登录小红书、`XHS_LIVE_SHARE_URL` 环境变量

```bash
bash scripts/edge/live-edge-xhs-rag-e2e.sh --check-stack
# 全链：
export XHS_LIVE_SHARE_URL='https://www.xiaohongshu.com/explore/...'
bash scripts/edge/live-edge-xhs-rag-e2e.sh
```

**展示点：** 时间线 `edge` → `cloud`；RAG 文档出现在 Cloud。

---

## 5. macOS 桌面 Demo（L1+）

```bash
# 构建（开发者）
bash scripts/edge/build-macos-installer.sh
open dist/edge-macos/AlphaPlus-Edge-0.1.0-macos.dmg

# 用户路径：安装 → 打开 App → 填 Gateway URL → 注册 → 启动 Tunnel
bash scripts/edge/edge-post-install-wizard.sh
bash scripts/edge/verify-edge-macos.sh
```

**录屏分镜：**

| 时间 | 画面 | 旁白 |
|------|------|------|
| 0:00–0:20 | 痛点：多平台 + 隐私 | 「登录态不能上云」 |
| 0:20–1:00 | 安装 DMG / 打开 App | 「一键本机桥接」 |
| 1:00–2:00 | 注册 Gateway + Tunnel 绿 | 「WSS 连云端，Cookie 留本机」 |
| 2:00–2:30 | Stock 工作台「本机桥接已就绪」 | 「和 AlphaPlus 闭环」 |
| 2:30–3:00 | GitHub Star + 免责声明 | CTA |

---

## 6. 与 Stock 工作台联调（L3 UI）

**前置：** stock frontend 指向 Cloud Gateway，`VITE_EDGE_HEALTH_URL=http://127.0.0.1:10490/health`

1. 打开 `https://alphaplus.datapro.asia`（或本机 `:52000`）  
2. **系统设置 → Edge 桥接**（权限配置收口在 Settings，演示默认 **CLS 财联社** 数据源）  
3. 内容中枢 → 财联社同步 → 策略 → 复盘决策链  

### 已提供的产品截图（2026-06-06）

| Step | 文件 | 用途 |
|------|------|------|
| 内容中枢 | `assets/screenshots/alphaplus01-content-hub.png` | README / 掘金 / 知乎 |
| 策略演化 | `assets/screenshots/alphaplus02-strategy.png` | 闭环文章 #2 |
| 复盘 · CLS | `assets/screenshots/alphaplus03-audit-cls-trace.png` | 微信群 / B 端 |

Monorepo 副本：`docs/assets/alphaplus/`（见 [README](../../../docs/assets/alphaplus/README.md)）

截图清单见 [ASSETS_NEEDED.md](./ASSETS_NEEDED.md)。

---

## 7. Demo 模式（无 LIVE 依赖）

用于 landing / 文章嵌入：

| 命令 | 说明 |
|------|------|
| `SKIP_LIVE_EDGE=1 bash scripts/edge/verify-edge-live.sh` | 跳过 opencli/wx LIVE |
| `python3 -m pytest scripts/edge/test_edge_*_contract.py -q` | 契约测试 |

---

## 8. 故障展示（可选，增信）

故意停 Edge → 内容中枢应显示 `EDGE_OFFLINE`（409），**不** fallback 云端 opencli。

```bash
kill $(cat .edge-runtime/edge-health.pid)
# 在 UI 触发 xhs 采集 → 应看到明确 offline 指引
```

---

## 9. 录屏技术建议

| 项 | 建议 |
|----|------|
| 分辨率 | 1920×1080，终端字体 14pt+ |
| 终端 | 清屏后再跑 doctor，保留 JSON 输出 |
| 隐私 | 打码微信 ID、Cookie、真实笔记内容 |
| 导出 | MP4 H.264；GIF 用于 GitHub README（< 5MB） |

---

## 10. 演示检查清单

- [ ] `edge-doctor.sh` 全绿或 SKIP 说明清晰  
- [ ] 架构图出现在 README / 幻灯片  
- [ ] 文末免责声明  
- [ ] GitHub 链接带 UTM  
- [ ] 无收益承诺、无「全自动交易」表述  

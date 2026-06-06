# GitHub / Hacker News 社区帖

**Landing / Repo:**

- `https://github.com/lqjack/alphaplus-edge?utm_source=github&utm_medium=community_post&utm_campaign=edge_launch`
- Cloud closed-loop（可选）: `https://alphaplus-landing.datapro.asia/?utm_source=github&utm_medium=edge_post`

---

## Post Copy（英文，HN / Reddit r/selfhosted）

**Title:** AlphaPlus Edge – run browser/WeChat MCP locally, orchestrate RAG in the cloud

**Problem:** Research workflows need Xiaohongshu, WeChat MP, and personal WeChat signals—but SaaS cannot host your Chrome cookies or local WeChat DB.

**What this repo is:**

- Local Edge Agent (`:10490`) + MCP servers for OpenCLI / wx-cli
- WSS tunnel to Neura Gateway – same `POST /api/tools/call` contract
- L0/L1 data stays on device; only L2 summaries go to cloud RAG (user-triggered)

**What you can verify without trusting slides:**

```bash
bash scripts/edge/start-edge-stack.sh
bash scripts/edge/edge-doctor.sh
bash scripts/edge/live-edge-gateway-tool-e2e.sh  # needs Gateway
```

Apache 2.0. Pairs with [dataproaiset](https://github.com/lqjack/dataproaiset) for cloud stack.

Feedback welcome from anyone building MCP local execution or privacy-boundary research tools.

*Output is for research assistance only; not investment advice.*

---

## Post Copy（中文，GitHub Discussions）

**标题：** 开源 AlphaPlus Edge：Cookie 不出机，MCP 接云端 RAG

**矛盾：** 跨平台收投研线索很费时间，但 Chrome 登录态、微信本地库不能交给 SaaS。

**本仓提供：**

- 本机 Edge Agent + 小红书/微信/公众号 MCP（OpenCLI、wx-cli）
- WSS 隧道注册 Neura Gateway，云端仍用 `POST /api/tools/call`
- macOS DMG / Tauri 桌面版 scaffold
- LIVE E2E：`live-edge-gateway-tool-e2e.sh`（真 HTTP，无 mock）

**快速开始：** 见 README 30 秒区块  
**完整 Demo：** [docs/DEMO.md](../DEMO.md)

Cloud 闭环（因子/归因/closed-loop）在 dataproaiset + alphapulse landing，Edge 负责**敏感面本地化**。

欢迎 Issue：安装环境、doctor 探针、Tunnel 稳定性。

本项目输出仅用于研究辅助，不构成投资建议或收益承诺。

---

## 配图建议

- edge-doctor 终端 JSON 全绿（待录 GIF）
- Edge–Cloud ASCII 架构（README 已有）
- **Cloud 闭环三步截图（已提供）：**
  - `assets/screenshots/alphaplus01-content-hub.png` — 内容中枢 / CLS
  - `assets/screenshots/alphaplus02-strategy.png` — 策略演化
  - `assets/screenshots/alphaplus03-audit-cls-trace.png` — 财联社复盘决策链

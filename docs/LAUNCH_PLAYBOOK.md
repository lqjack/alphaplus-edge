# AlphaPlus Edge 独立公开仓 — 发布与营销 Playbook

> **版本:** v1.0 · **日期:** 2026-06-06  
> **目标:** 在 **不删除** dataproaiset monorepo 内 `scripts/edge/`、`edge-desktop/` 的前提下，新增 **public GitHub 闭环**（`github.com/lqjack/alphaplus-edge`），完成叙事、Demo、可用对接与 90 天营销节奏。

---

## 0. 一句话策略

| 仓 | 角色 | 受众 | CTA |
|----|------|------|-----|
| **alphaplus-edge**（public） | 本机敏感面桥接 · MCP · 安装包 · 营销 | 工程师、隐私敏感投研 | Star → doctor → 接 Cloud |
| **dataproaiset**（monorepo） | Gateway / Stock / RAG / closed-loop | 团队部署、全栈 | 私有化 Cloud / 演示环境 |

**原则：** monorepo 的 Edge **保留**；独立仓是 **导出副本 + 对外叙事**，代码用 `sync-to-standalone-repo.sh` 对齐。

---

## 1. 可用闭环（用户旅程）

```text
① Clone alphaplus-edge (public)
        ↓
② bash demos/quickstart-demo.sh          ← L1：doctor + 契约（无浏览器）
        ↓
③ 配置 .env.edge
   GATEWAY_PUBLIC_URL=https://alphaplus-api.datapro.asia
        ↓
④ bash scripts/edge/register-with-gateway.sh
   bash scripts/edge/start-edge-stack.sh
        ↓
⑤ Cloud: POST /api/tools/call → Edge MCP（WSS tunnel）
        ↓
⑥ Stock UI: 系统设置 → Edge 桥接（绿）→ 内容/策略闭环（可选 L3）
```

### 1.1 生产 URL（当前 Ubuntu 部署）

| 用途 | URL | 说明 |
|------|-----|------|
| **Neura Gateway（Edge 注册 / WSS）** | `https://alphaplus-api.datapro.asia` | `:8001` tunnel |
| **Stock / closed-loop UI** | `https://alphaplus.datapro.asia` | `:52000` |
| **NeuraDesk 控制台** | `https://gateway.datapro.asia` | `:3000`，**不是** Edge API |
| **Landing** | `https://alphaplus-landing.datapro.asia` | Vercel |

独立仓文档与 `.env.example` 默认指向 **alphaplus-api** 作为 `GATEWAY_PUBLIC_URL`。

### 1.2 Demo 分级（对外怎么讲）

| 级别 | 命令 / 文档 | 依赖 | 营销用途 |
|------|-------------|------|----------|
| **L0** | `pytest scripts/edge/test_edge_*_contract.py` | Python | CI badge、技术可信度 |
| **L1** | `demos/quickstart-demo.sh` | Gateway 可达 | README 视频、GitHub 首发 |
| **L2** | `live-edge-gateway-tool-e2e.sh` | Edge + Gateway | 技术博客主 Demo |
| **L3** | `live-edge-xhs-rag-e2e.sh` + Stock UI | OpenCLI/wx-cli | 产品级录屏、B 端 |

**首发建议：** 先推 **L1**（不依赖用户本机微信/小红书登录），文案写清 L2/L3 需本机依赖。

---

## 2. 需你（Jack）另外提供 — 阻塞清单

以下 **无法代填**，收到后可执行 §4 发布命令。

### P0 — 缺任一项不建议 `public` push

| # | 项 | 说明 | 你的回复 |
|---|-----|------|----------|
| 1 | GitHub 确认 | org=`lqjack`，repo=`alphaplus-edge` | ☐ 确认 / 改名：____ |
| 2 | 生产 Gateway | 默认 `https://alphaplus-api.datapro.asia` | ☐ 确认 / 替换：____ |
| 3 | Demo 视觉（二选一） | 3min MP4 **或** doctor 全绿 GIF | ☐ 链接：____ |
| 4 | 免责声明终审 | 中英文各一版 | ☐ 已过 / 待法务 |
| 5 | SECURITY 邮箱 | `security@___` | ☐ ____ |

### P1 — 首发后 2 周内

| # | 项 | 说明 |
|---|-----|------|
| 6 | 工作台截图 | Stock 闭环三步（内容/策略/复盘） | ✅ 见 `assets/screenshots/` |
| 7 | 掘金/知乎账号 | 发技术文 #1 |
| 8 | 微信群 2–3 个 | 冷启动转发 [wechat-group-post.md](./delivery/wechat-group-post.md) |
| 9 | Apple 签名 | DMG Release（可选 v0.1.0 仅 CLI） |

### P2 — 90 天增强

| # | 项 |
|---|-----|
| 10 | 英文 README、Product Hunt |
| 11 | Edge 专用 Landing 路径（或复用 alphapulse `#/edge`） |
| 12 | 客户 Logo / 案例（B 端 One-Pager） |

完整表：[ASSETS_NEEDED.md](./ASSETS_NEEDED.md)

---

## 3. 发布前执行（仓库侧，已就绪部分）

### 3.1 Monorepo → 独立树同步

```bash
cd ~/dataproaiset/dataproaiset
bash scripts/edge/sync-to-standalone-repo.sh
```

**不修改** monorepo 内 `scripts/edge/`、`edge-desktop/`。

### 3.2 本地验证

```bash
cd alphaplus-edge
cp .env.example .env.edge
# 编辑 GATEWAY_PUBLIC_URL=https://alphaplus-api.datapro.asia
bash demos/quickstart-demo.sh
python3 -m pytest scripts/edge/test_edge_ws_contract.py -q
```

### 3.3 替换占位符（收到 P0 后）

```bash
cd alphaplus-edge
export GITHUB_ORG=lqjack
export GATEWAY_PUBLIC_URL=https://alphaplus-api.datapro.asia
bash scripts/apply-public-urls.sh    # 批量替换 org 占位符 / 旧 Gateway URL
bash scripts/publish-to-github.sh
```

检查清单：[PUBLISH_CHECKLIST.md](./PUBLISH_CHECKLIST.md)

---

## 4. 营销节奏（90 天）

### Phase 0 — 准备周（D-7 ~ D-1）

| 天 | 动作 | 产出 |
|----|------|------|
| D-7 | 填 ASSETS_NEEDED P0 | 表格回复 / Issue |
| D-6 | `sync-to-standalone-repo.sh` + L1 Demo 录屏 | MP4/GIF → `assets/` |
| D-5 | README 终稿 + 架构图 | public 树 |
| D-4 | 内测 2 人跑 quickstart | Issue 反馈修 doc |
| D-3 | 法务过免责声明 | README 文末 |
| D-2 | 预写 GitHub / 知乎 / 微信群文案 | [delivery/](./delivery/) |
| D-1 | `publish-to-github.sh` dry-run | private fork 试 push |

### Phase 1 — 发布周（D0 ~ D+7）

| 天 | 渠道 | 内容 | 文档 |
|----|------|------|------|
| **D0** | GitHub public | push + Release `v0.1.0`（CLI） | PUBLISH_CHECKLIST |
| D0 | GitHub Discussions | 「Edge 安装互助」帖 | github-community-post |
| D+1 | 掘金/CSDN | 文章 #1 痛点：登录态不能上云 | juejin-article-outline |
| D+2 | 知乎 | 长文 #1（可拆分自掘金） | zhihu-long-form |
| D+3 | 微信群 | 短帖 + Demo 链接 | wechat-group-post |
| D+5 | B 站/视频号 | 3min Demo 上传 | DEMO.md 分镜 |
| D+7 | 复盘 | Stars / doctor Issue 数 | 更新 KPI 表 |

### Phase 2 — 深度内容（D+8 ~ D+30）

| 周 | 主题 | 动作 |
|----|------|------|
| W2 | MCP + WSS 技术深潜 | 文章 #2 + 录屏 L2 e2e |
| W3 | 小红书/微信 → RAG 场景 | 文章 #3 + L3 录屏（需 LIVE） |
| W4 | macOS DMG（若签名就绪） | Release v0.2.0 + 少数派/雪球短文 |

### Phase 3 — 转化（D+31 ~ D+90）

| 周 | 目标 | 动作 |
|----|------|------|
| W5–6 | Cloud 注册设备 ↑ | 文档强调 alphaplus-api + closed-loop |
| W7–8 | 团队试点 | B 端 One-Pager + 预约 Demo |
| W9–12 | 案例 / 二次传播 | 用户故事 1 篇；KPI 复盘 |

### KPI（90 天建议，见 MARKETING_PLAN.md）

| 指标 | 目标 |
|------|------|
| GitHub Stars | 200 |
| doctor 成功反馈 | 20 |
| 技术文章 | 3 篇 |
| Cloud 注册 Edge 设备 | 50 |

---

## 5. 内容与叙事索引

| 文档 | 用途 |
|------|------|
| [NARRATIVE.md](./NARRATIVE.md) | 电梯演讲、矛盾、受众变体 |
| [MARKETING_PLAN.md](./MARKETING_PLAN.md) | 全渠道矩阵、飞轮、IP 分层 |
| [DEMO.md](./DEMO.md) | 录屏分镜、L0–L3 命令 |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | L0–L3 数据分级、MCP 端口 |
| [CLOUD_INTEGRATION.md](./CLOUD_INTEGRATION.md) | Gateway 注册、WSS、Stock 配置 |
| [delivery/](./delivery/) | 各渠道成稿模板 |

**对外统一矛盾：** 「跨平台收线索很费时间，但敏感登录态不能交给 SaaS。」

**合规句（全文末）：** 本项目输出仅用于研究辅助，不构成投资建议或收益承诺。

---

## 6. 发布后双仓维护节奏

| 频率 | Monorepo | 独立 public 仓 |
|------|----------|----------------|
| **每次 Edge 功能合并 main** | 正常开发 `scripts/edge/` | `bash scripts/edge/sync-to-standalone-repo.sh` |
| **每 2 周** | — | tag `v0.x.y` + CHANGELOG |
| **每次 Gateway 契约变更** | `gateway/config/edge_tools.yaml` | sync + 文档 CLOUD_INTEGRATION |
| **营销素材更新** | 链到 public 仓 | `assets/` + README |

Monorepo 架构 SSOT：[`docs/architecture/edge-local-gateway-deployment.md`](../../docs/architecture/edge-local-gateway-deployment.md)

---

## 7. monorepo 侧配合（不删 Edge）

| 项 | 位置 | 说明 |
|----|------|------|
| Edge 运维 SSOT | `scripts/edge/` | **保留** |
| Tauri 源码 | `edge-desktop/` | **保留** |
| Gateway 实现 | `gateway/edge_*.py` | **保留** |
| 导出目录 | `alphaplus-edge/` | 营销 + sync 目标 |
| 架构说明 | `docs/architecture/edge-standalone-repo.md` | 双仓策略 |
| 主营销方案 | `docs/MARKETING_PLAN.md` §2.0 | 链到本 Playbook |

Stock 演示模式（CLS-only）与 Edge 独立仓 **并行**：演示用财联社降低配置门槛；Edge 仓面向 **需要本机 MCP 的用户**。

---

## 8. 你回复模板（复制填写）

```text
【AlphaPlus Edge 公开发布 — P0 确认】

1. GitHub: lqjack/alphaplus-edge  （确认 / 改名：____）
2. Gateway: https://alphaplus-api.datapro.asia  （确认 / 替换：____）
3. Demo: [ ] 3min MP4  [ ] doctor GIF  链接：____
4. 免责声明: [ ] 已审  [ ] 待审
5. security@邮箱: ____
6. Landing CTA: 复用 alphapulse / 独立 /edge 路径：____
7. Apple 签名 v0.2: 有 / 无 / 稍后
```

收到后可在 monorepo 根目录执行：

```bash
export GITHUB_ORG=lqjack
export GATEWAY_PUBLIC_URL=https://alphaplus-api.datapro.asia
bash scripts/edge/sync-to-standalone-repo.sh
cd alphaplus-edge && bash scripts/apply-public-urls.sh && bash scripts/publish-to-github.sh
```

---

*Playbook v1.0 · 对齐 dataproaiset docs/MARKETING_PLAN.md · alphaplus-edge/docs/MARKETING_PLAN.md*

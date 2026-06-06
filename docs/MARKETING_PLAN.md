# AlphaPlus Edge 全渠道推广方案

> **制定日期**: 2026-06-06  
> **版本**: v1.0  
> **状态**: 公开发布草案；对外前须过合规清单（见 dataproaiset `compliance-checklist.md`）

## 对外表达基线

- 定位为 **「本机敏感数据桥接 + 云端投研编排」**，不包装成自动交易或收益工具。
- 强调 **隐私边界**：Cookie、微信 DB、浏览器登录态不出机；云端只收 L2 摘要。
- 不承诺收益、胜率、采集覆盖率 100%。
- 所有材料文末带：**本项目输出仅用于研究辅助，不构成投资建议或收益承诺。**

---

## 一、产品定位

### 1.1 在生态中的位置

```text
┌─────────────────────────────────────────────────────────────────┐
│                    AlphaPlus 产品矩阵                            │
├─────────────────────────────────────────────────────────────────┤
│  dataproaiset (monorepo)     │  alphaplus-edge (本仓, public)   │
│  ─────────────────────     │  ────────────────────────────   │
│  Neura Gateway :8001       │  Edge Agent :10490              │
│  Stock / RAG / Skills      │  本机 MCP (xhs/wx/公众号)        │
│  Landing / closed-loop     │  Tauri 桌面 + WSS Tunnel         │
└─────────────────────────────────────────────────────────────────┘
         Cloud 算力 ◄──── WSS ────► Edge 敏感面
```

### 1.2 核心差异化

| 卖点 | 说明 | 解决的痛点 |
|------|------|-----------|
| **敏感面本地化** | OpenCLI、wx-cli 只在用户设备跑 | SaaS 不愿托管用户 Chrome / 微信 DB |
| **契约统一** | 云端仍 `POST /api/tools/call`，路由自动选 Edge/Cloud | 集成方不用写两套 API |
| **MCP 原生** | Cursor / NeuraDesk 可指向本机聚合端口 | 工程师 5 行接入 |
| **可验证闭环** | `live-edge-gateway-tool-e2e.sh` 真 HTTP，无 mock | GitHub 可信度 |
| **桌面一键** | macOS DMG + Tauri 注册/轮换 token | 非工程师也能装 |

### 1.3 目标用户

| 优先级 | 画像 | 获取渠道 |
|--------|------|---------|
| ⭐⭐⭐⭐⭐ | AI/数据工程师，要 MCP + 本地浏览器 | GitHub、掘金、HN |
| ⭐⭐⭐⭐ | 投研个人，小红书/微信线索进 RAG | 微信群、知乎、雪球 |
| ⭐⭐⭐ | 小团队 SaaS，Cloud 部署 + 员工各装 Edge | BD、技术博客 |
| ⭐⭐ | 隐私敏感行业（律所、家族办公室） | 合规向长文 |

---

## 二、GitHub 开源推广（P0）

### 2.1 README 结构（已落地）

见仓库根 [README.md](../README.md)：

1. 一句话 Banner  
2. 30 秒 Quickstart  
3. ASCII 架构图  
4. Demo 表格 → `docs/DEMO.md`  
5. 与 monorepo 关系说明（**不删 monorepo edge**）  
6. 合规声明  

### 2.2 GitHub 配套

| 任务 | 状态 | 备注 |
|------|------|------|
| LICENSE Apache 2.0 | ✅ | |
| CONTRIBUTING.md | ✅ | |
| Issue 模板 | ✅ | `.github/ISSUE_TEMPLATE/` |
| CI contract smoke | ✅ | 无 LIVE 依赖 |
| CHANGELOG | ✅ | |
| Release DMG 附件 | ⬜ | 需 CI + 签名（见 ASSETS_NEEDED） |
| GitHub Discussions | ⬜ | 启用后挂「Edge 安装互助」 |

### 2.3 UTM 链接（待填正式域名）

| 渠道 | URL 模板 |
|------|----------|
| GitHub README | `https://github.com/lqjack/alphaplus-edge?utm_source=github&utm_medium=readme` |
| GitHub Release | `?utm_source=github&utm_medium=release` |
| 掘金/CSDN | `?utm_source=juejin&utm_medium=article&utm_campaign=edge_launch` |
| 知乎 | `?utm_source=zhihu&utm_medium=long_form&utm_campaign=edge_launch` |

Landing 可复用 alphapulse 或单独 Edge 页 —— **需你确认 URL**（见 [ASSETS_NEEDED.md](./ASSETS_NEEDED.md)）。

---

## 三、内容营销矩阵

### 3.1 技术博客规划

| # | 标题 | 卖点 | 平台 | 字数 |
|---|------|------|------|------|
| 1 | 《为什么投研 SaaS 不能把用户 Chrome 放云端》 | 信任边界 | 掘金/知乎 | 2500 |
| 2 | 《AlphaPlus Edge：MCP + WSS 隧道实战》 | 技术深度 | CSDN/掘金 | 4000 |
| 3 | 《小红书/微信线索进 RAG，数据不出本机》 | 场景 Demo | 少数派/雪球 | 3000 |
| 4 | 《5 分钟跑通 Edge LIVE E2E》 | Quickstart | GitHub Discussions | 1500 |

文章 1 大纲见 [NARRATIVE.md](./NARRATIVE.md) § 长文结构。

### 3.2 短视频 / 演示

| 类型 | 时长 | 要点 |
|------|------|------|
| 产品 Demo | 3 min | 装 Edge → doctor 全绿 → 控制台「本机桥接已就绪」 |
| 技术解析 | 8 min | Tunnel + tools/call 路由动画 |
| 30s 快闪 | 30s | 「Cookie 不出机，RAG 在云端」 |

分镜脚本：[DEMO.md](./DEMO.md) § 录屏分镜。

### 3.3 渠道文案

| 文件 | 用途 |
|------|------|
| [delivery/github-community-post.md](./delivery/github-community-post.md) | GitHub / HN |
| [delivery/zhihu-long-form.md](./delivery/zhihu-long-form.md) | 知乎 |
| [delivery/wechat-group-post.md](./delivery/wechat-group-post.md) | 微信群 |
| [delivery/juejin-article-outline.md](./delivery/juejin-article-outline.md) | 掘金 |

---

## 四、B 端话术（精简 One-Pager）

```text
┌──────────────────────────────────────────────────────────────┐
│  AlphaPlus Edge — 本机敏感数据桥接                            │
├──────────────────────────────────────────────────────────────┤
│  问题：云端 SaaS 无法托管用户浏览器登录态 / 微信本地库          │
│  方案：Edge Agent 在用户设备执行 OpenCLI/wx-cli；              │
│        云端 Gateway 编排 RAG/Agent/行情                         │
│  价值：合规边界清晰 · MCP 标准接入 · 可私有化 Cloud             │
│  集成：POST /api/tools/call + X-Edge-Id · 开源 Apache 2.0     │
│  演示：docs/DEMO.md · live-edge-gateway-tool-e2e.sh           │
└──────────────────────────────────────────────────────────────┘
```

---

## 五、增长飞轮

```text
GitHub Stars + 技术博客
        ↓
工程师试用 Edge MCP（本地端口）
        ↓
接入 dataproaiset Cloud closed-loop
        ↓
团队采购 / 定制 Cloud 部署
        ↓
收入反哺 Edge 安装包与文档
        ↓
（回到内容营销）
```

### KPI（首 90 天建议）

| 指标 | 目标 |
|------|------|
| GitHub Stars | 200 |
| Edge doctor 成功反馈（Issue/Discussion） | 20 |
| 技术文章 | 3 篇 |
| Cloud Gateway 注册设备数 | 50 |

---

## 六、知识产权分层（对齐 monorepo 策略）

| 层级 | Edge 仓公开 | 保留在 dataproaiset |
|------|-------------|---------------------|
| L1 开放 | Agent 脚本、Tunnel、Doctor、文档 | — |
| L2 API | Gateway Edge API 契约文档 | Gateway 实现 |
| L3 闭源 | — | RAG 融合算法、领域模型权重 |

---

## 七、执行清单（首周）

| 优先级 | 任务 | 负责人 |
|--------|------|--------|
| P0 | 填 [ASSETS_NEEDED.md](./ASSETS_NEEDED.md) 中 lqjack / URL | **你** |
| P0 | `gh repo create` 公开仓 + push | **你** |
| P0 | 录 3 分钟 Demo（按 DEMO.md） | **你** |
| P1 | 发 GitHub 社区帖（delivery 模板） | 你/我 |
| P1 | 知乎/掘金文章 #1 | 你 |
| P2 | Release 附 DMG（需 Apple 签名） | 你 |

---

*方案版本 v1.0 | 2026-06-06 | 对齐 dataproaiset docs/MARKETING_PLAN.md*

# AlphaPlus Edge — 内容叙事手册

**用途：** 对外文案、演讲、博客、短视频的统一故事线。  
**原则：** 讲边界与能力，不讲算法细节；讲可验证 Demo，不讲收益承诺。

---

## 1. 电梯演讲（30 秒）

> 做投研的人都要刷小红书、公众号、微信——但这些登录态和数据不能.upload 到别人的服务器。  
> **AlphaPlus Edge** 是一台跑在你电脑上的桥：浏览器和微信库留在本机，云端只做 RAG 和 Agent 编排。  
> 对开发者就是标准 **MCP + Gateway**，5 分钟能跑通 LIVE 测试。开源 Apache 2.0。

---

## 2. 问题叙事（痛点 → 矛盾）

### 2.1 用户看到的矛盾

| 他们想要 | 他们害怕 |
|----------|----------|
| 云端 AI 帮整理跨平台线索 | Chrome Cookie / 微信聊天记录上云 |
| 一条 API 调抖音、小红书、公众号 | 每个平台一套爬虫、一套合规风险 |
| 和 Cursor 里其他 MCP 一起用 | 厂商锁死在私有桌面客户端 |

### 2.2 一句话矛盾（所有渠道统一）

**「跨平台收线索很费时间，但敏感登录态又不能交给 SaaS。」**

（与 alphapulse landing 叙事同族，Edge 侧强调 **privacy + MCP**，landing 侧强调 **closed-loop JSON**。）

---

## 3. 解决方案叙事（三段式）

### Act 1 — 划界（10 秒）

敏感面在 **Edge**：OpenCLI、wx-cli、本机 MCP `:10350–10490`。  
算力在 **Cloud**：Gateway、RAG、Stock、Skills。

### Act 2 — 连接（20 秒）

Edge 通过 **WSS 隧道** 注册到 Gateway。  
云端 `POST /api/tools/call` 不变——需要本机浏览器的路由到 Edge，其余走 Cloud MCP。

### Act 3 — 闭环（20 秒）

用户在工作台粘贴小红书链接 → Edge 采集 L2 摘要 → Cloud 写 RAG → 时间线标注 `execution_location: edge`。  
**可复盘、可审计、Cookie 不出机。**

---

## 4. 受众变体话术

### 4.1 工程师（GitHub / 掘金）

**标题角度：** 「MCP 本地执行面 + 云端控制面」

- 强调：`live-edge-gateway-tool-e2e.sh` 真 HTTP
- 强调：NeuraDesk / Cursor 指向 `127.0.0.1:10351` MCP
- CTA：Star + 跑 doctor

### 4.2 投研用户（微信 / 雪球）

**标题角度：** 「小红书/微信线索进知识库，数据留在自己电脑」

- 强调：不用把微信聊天记录发给第三方
- 强调：和 AlphaPlus 云端研报流程衔接
- CTA：下载 macOS 安装包 / 加 waitlist

### 4.3 B 端 / 合规（商务）

**标题角度：** 「可私有化 Cloud + 员工本机 Edge 的数据分级方案」

- 强调 L0–L3 数据分级表（见 ARCHITECTURE.md）
- 强调设备 token 可撤销、审计日志不含 L1 正文
- CTA：预约 Demo、看 One-Pager

---

## 5. 长文结构模板（博客 #1）

```markdown
# 为什么投研 SaaS 不能把用户 Chrome 放云端

## 1. 背景（300 字）
- 多平台线索：小红书情绪、公众号深度、微信私域
- 传统做法：云端 Playwright + 用户 Cookie → 合规与信任问题

## 2. Edge–Cloud 划界（600 字）
- 数据分级 L0–L3 表
- 架构 ASCII 图
- 与「全云端采集」对比

## 3. 5 分钟动手（800 字）
- clone alphaplus-edge
- start-edge-stack + edge-doctor
- curl /health 截图

## 4. 与 AlphaPlus 云端闭环（400 字）
- stock-flow + RAG 时间线
- closed-loop 链接（landing）

## 5. 总结（200 字）
- 开源地址 + 免责声明
```

---

## 6. 禁用表述

| ❌ 避免 | ✅ 改用 |
|---------|---------|
| AI 自动帮你赚钱 | 研究辅助、线索整理 |
| 100% 采集成功 | 依赖本机登录态，doctor 可自检 |
| 云端看不到任何数据 | 用户显式同步时上传 L2 摘要 |
| 比 XX 竞品强 X 倍 | 可验证 E2E 脚本 + 架构边界 |

---

## 7. 视觉叙事元素

| 素材 | 用途 | 状态 |
|------|------|------|
| Edge–Cloud 架构图 | README、PPT | ✅ ASCII（README） |
| 内容 → 策略 → 复盘截图 trio | README、社交、文章 | ✅ `assets/screenshots/alphaplus01–03` |
| doctor 终端全绿 GIF | GitHub、掘金 | ⬜ **需你录制** |
| 数据分级信息图 | 知乎、B 端 | ⬜ 可用 Figma 模板 |

清单详情：[ASSETS_NEEDED.md](./ASSETS_NEEDED.md)

---

## 8. 与 monorepo 品牌对齐

| 对外名 | 含义 |
|--------|------|
| **AlphaPlus Edge** | 本产品（本仓） |
| **AlphaPlus / dataproaiset** | 全栈 monorepo |
| **Neura Gateway** | 云端 API 入口 :8001 |
| **NeuraDesk** | 可选控制台（独立仓 llm-gateway） |

命名 SSOT：dataproaiset `docs/architecture/ecosystem-naming.md`

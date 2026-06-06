# 知乎长文大纲 — Edge 本地桥接

**UTM:** `https://github.com/lqjack/alphaplus-edge?utm_source=zhihu&utm_medium=long_form&utm_campaign=edge_launch`

---

## 标题候选

1. 为什么投研 SaaS 不能把用户的 Chrome 放在云端？
2. 小红书/微信线索进 RAG，数据如何不出本机？
3. MCP 实战：本机 OpenCLI + 云端 Gateway 怎么分工？

**原则：** 一篇只讲一个矛盾 —— **隐私边界 vs 跨平台采集效率**。

---

## 正文结构（约 3000 字）

### 1. 开场（300 字）

- 场景：同一标的，小红书情绪、公众号深度、微信私域讨论
- 痛点：云端爬虫要么拿不到登录态，要么用户不敢给 Cookie

### 2. Edge–Cloud 划界（800 字）

- L0–L3 数据分级表（摘自 ARCHITECTURE.md）
- ASCII 架构图
- 与「全云端 Playwright」对比：合规、信任、运维成本

### 3. 技术实现（1000 字）

- Edge Agent 四模块：Health / Tunnel / Registrar / MCP Supervisor
- Gateway 路由：`tools_require_edge_prefix` → 409 EDGE_OFFLINE
- 代码片段：`curl http://127.0.0.1:10490/health`
- **不展开** 融合算法、embedding 细节

### 4. 5 分钟动手（600 字）

```bash
git clone https://github.com/lqjack/alphaplus-edge
bash scripts/edge/start-edge-stack.sh
bash scripts/edge/edge-doctor.sh
```

- 预期输出截图说明
- macOS 用户：DMG 路径

### 5. 与 AlphaPlus 云端闭环（400 字）

- 演示环境：https://alphaplus.datapro.asia（默认 **CLS 财联社** 数据源）
- 配图：`assets/screenshots/alphaplus01-content-hub.png` → `02-strategy` → `03-audit-cls-trace`
- stock 内容中枢时间线 `execution_location: edge`（Edge 用户）
- landing closed-loop 链接（可选）

### 6. 总结 + 免责声明（200 字）

- GitHub Star CTA
- 研究辅助，不构成投资建议

---

## 文末固定块

> 本项目输出仅用于研究辅助，不构成投资建议或收益承诺。  
> 开源地址：https://github.com/lqjack/alphaplus-edge

---

## 配图

1. 数据分级信息图（可选 Figma）
2. **CLS 闭环三步截图**（已提供）：`alphaplus01-content-hub` / `02-strategy` / `03-audit-cls-trace`
3. doctor 终端截图（待录 GIF）
4. （可选）Tunnel 序列图 mermaid

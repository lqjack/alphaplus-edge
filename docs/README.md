# AlphaPlus Edge — 文档中心

**独立公开仓文档入口。** monorepo 内 `scripts/edge/` 与 `edge-desktop/` **保留不动**；本目录为对外营销、Demo、发布闭环。

---

## 快速导航

| 你要做什么 | 文档 |
|-----------|------|
| **公开发布 Playbook（90 天节奏）** | [LAUNCH_PLAYBOOK.md](./LAUNCH_PLAYBOOK.md) ⬅️ **执行总纲** |
| **了解产品故事** | [NARRATIVE.md](./NARRATIVE.md) |
| **全渠道推广执行** | [MARKETING_PLAN.md](./MARKETING_PLAN.md) |
| **跑 Demo / 录屏** | [DEMO.md](./DEMO.md) |
| **对接 Cloud Gateway** | [CLOUD_INTEGRATION.md](./CLOUD_INTEGRATION.md) |
| **架构与数据分级** | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| **公开发布前检查** | [PUBLISH_CHECKLIST.md](./PUBLISH_CHECKLIST.md) |
| **需你提供的素材** | [ASSETS_NEEDED.md](./ASSETS_NEEDED.md) ⬅️ **阻塞项** |
| **各渠道文案模板** | [delivery/](./delivery/) |

---

## 闭环关系

```text
dataproaiset (monorepo, private/full-stack)
  ├── scripts/edge/          ← 运维 SSOT，不删除
  ├── edge-desktop/          ← Tauri 源码 SSOT
  ├── gateway/edge_*         ← Cloud 路由实现
  └── alphaplus-edge/        ← 导出 + 营销 + Demo（本树）
           │
           │  bash scripts/edge/sync-to-standalone-repo.sh
           ▼
github.com/lqjack/alphaplus-edge  (public, planned)
  ├── README + docs/           ← 获客叙事
  ├── demos/quickstart-demo.sh ← 5 分钟可验证
  └── scripts/edge/            ← 同步副本
           │
           │  WSS Tunnel + POST /api/tools/call
           ▼
Cloud Neura Gateway (dataproaiset 部署)
  └── stock / RAG / closed-loop
```

---

## 5 分钟本地验证

```bash
# monorepo 根目录 — 同步最新代码到独立树
bash scripts/edge/sync-to-standalone-repo.sh

cd alphaplus-edge
cp .env.example .env.edge
export GATEWAY_URL=http://127.0.0.1:8001   # 需本机 Gateway 或 Cloud URL
bash demos/quickstart-demo.sh
```

无 Gateway 时仍可跑契约测试：

```bash
python3 -m pytest scripts/edge/test_edge_ws_contract.py -q
```

---

## 渠道文案索引

| 渠道 | 文件 | 状态 |
|------|------|------|
| GitHub / HN | [delivery/github-community-post.md](./delivery/github-community-post.md) | ✅ 模板 |
| 知乎长文 | [delivery/zhihu-long-form.md](./delivery/zhihu-long-form.md) | ✅ 模板 |
| 微信群 | [delivery/wechat-group-post.md](./delivery/wechat-group-post.md) | ✅ 模板 |
| 掘金 / CSDN | [delivery/juejin-article-outline.md](./delivery/juejin-article-outline.md) | ✅ 大纲 |

---

## 与 monorepo 营销方案关系

本仓 [MARKETING_PLAN.md](./MARKETING_PLAN.md) 从 dataproaiset [`docs/MARKETING_PLAN.md`](../../docs/MARKETING_PLAN.md) 派生，聚焦：

- **单一矛盾：** 敏感面本地化 vs 跨平台采集
- **受众：** 工程师 + 隐私敏感投研用户（P0）
- **CTA：** Star 独立仓 → 可选接入 alphapulse closed-loop

架构 SSOT 仍在 monorepo：[`docs/architecture/edge-local-gateway-deployment.md`](../../docs/architecture/edge-local-gateway-deployment.md)

独立仓设计说明：[`docs/architecture/edge-standalone-repo.md`](../../docs/architecture/edge-standalone-repo.md)

# 公开发布检查清单

在 `gh repo create` 并设为 **public** 之前逐项确认。

---

## A. 仓库元数据

- [x] GitHub org / repo 名已确定：`lqjack/alphaplus-edge`
- [ ] LICENSE Copyright 正确
- [ ] README 合规声明完整
- [ ] `.gitignore` 不含密钥、`.edge-runtime`、DMG 构建产物
- [ ] Topics: `mcp`, `edge-computing`, `research`, `opencli`, `alphaplus`

---

## B. 代码同步

- [ ] 已运行 `bash scripts/edge/sync-to-standalone-repo.sh`（从 monorepo）
- [ ] `scripts/edge/*` 与 monorepo 一致（或 tag 对齐）
- [ ] `edge-desktop/` 已同步（无 `target/` 提交）
- [ ] `config/edge_tools.yaml` 与 gateway 一致
- [ ] **monorepo 内 edge 未删除** — 仅新增 `alphaplus-edge/` 导出目录

---

## C. 可运行性

- [ ] `cp .env.example .env.edge` 文档清晰
- [ ] `bash demos/quickstart-demo.sh` 在干净环境通过（L1）
- [ ] `python3 -m pytest scripts/edge/test_edge_*_contract.py -q` 绿
- [ ] CI workflow `.github/workflows/contract-smoke.yml` 绿

---

## D. 演示素材

- [ ] 至少 1 个视觉 Demo — ✅ 截图 trio 已就绪；可选补 MP4/GIF
- [ ] Demo 无敏感 Cookie / 聊天记录
- [ ] UTM 链接已填入 MARKETING_PLAN.md

---

## E. 合规

- [ ] 免责声明中英文（若面向国际）
- [ ] 无收益承诺、无「自动交易」表述
- [ ] SECURITY.md 漏洞上报邮箱有效

---

## F. 发布命令（示例）

```bash
cd alphaplus-edge
git init
git add .
git commit -m "Initial public release: AlphaPlus Edge docs + sync scaffold"

gh repo create lqjack/alphaplus-edge --public --source=. --remote=origin
git push -u origin main

# 可选 Release + DMG
gh release create v0.1.0 dist/edge-macos/AlphaPlus-Edge-0.1.0-macos.dmg \
  --title "AlphaPlus Edge 0.1.0" \
  --notes-file CHANGELOG.md
```

---

## G. 发布后

- [ ] monorepo README 增加 alphaplus-edge 链接
- [ ] dataproaiset `docs/architecture/edge-standalone-repo.md` 更新状态
- [ ] 发 GitHub Discussions 帖（delivery 模板）
- [ ] 记录 Stars / Issue 到 MARKETING_PLAN KPI 表

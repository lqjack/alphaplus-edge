# 需你提供的素材与信息清单

公开发布 **alphaplus-edge** 独立 GitHub 仓前，以下项需你确认或提供。  
已在文档中用 `lqjack`、`YOUR_URL` 占位的地方，收到后会批量替换。

---

## 最小阻塞集（P0 — 缺一项不建议 public push）

| # | 项 | 说明 |
|---|-----|------|
| **1** | GitHub org / 用户名 | 如 `lqjack` |
| **5** | 生产 Gateway URL | Edge 注册与 WSS，如 `https://gateway.datapro.asia` |
| **9 或 10** | Demo 视觉 | 3 分钟 MP4 **或** doctor 全绿 GIF（**产品截图 trio 已就绪**） |
| **23** | 免责声明终审 | 法务过一遍中英文 |

收到以上 4 项后，可执行：

```bash
export GITHUB_ORG=lqjack   # 你的 org
bash scripts/edge/sync-to-standalone-repo.sh   # monorepo 根目录
cd alphaplus-edge && bash scripts/publish-to-github.sh
```

---

## 1. 仓库与品牌（P0 — 阻塞发布）

| # | 项 | 说明 | 示例 / 你的填写 |
|---|-----|------|----------------|
| 1 | **GitHub 组织/用户名** | 公开仓 owner | `lqjack`（待你确认）→ ______ |
| 2 | **仓库名确认** | 默认 `alphaplus-edge` | 确认 / 改名 ______ |
| 3 | **License 署名** | LICENSE Copyright 行 | 公司名 / 个人名 ______ |
| 4 | **联系邮箱** | SECURITY.md、README | security@______ |

---

## 2. 云端与 Landing URL（P0）

| # | 项 | 说明 | 你的填写 |
|---|-----|------|---------|
| 5 | **生产 Gateway URL** | Edge 注册与 Tunnel | 默认 `https://alphaplus-api.datapro.asia` → ______ |
| 6 | **Edge 专用 Landing** | 可选；无则复用 alphapulse | ______ |
| 7 | **Waitlist 表单** | 与 landing API 或独立 | ______ |
| 8 | **文档站 / GitHub Pages** | 可选 | ______ |

---

## 3. 演示素材（P0 — 营销必需）

| # | 项 | 规格 | 状态 |
|---|-----|------|------|
| 9 | **3 分钟产品 Demo 视频** | MP4，见 DEMO.md 分镜 | ⬜ 待录（截图已就绪） |
| 10 | **edge-doctor 全绿终端 GIF** | < 5MB，README 用 | ⬜ 待录 |
| 11 | **工作台 / 闭环截图** | PNG | ✅ `assets/screenshots/alphaplus01–03` |
| 12 | **架构图（高清）** | 可选 Figma 导出，README 现用 ASCII | ⬜ 可选 |
| 13 | **DMG 安装过程录屏** | macOS 30–60s | ⬜ 待录 |

> 若暂无法 LIVE 录制 OpenCLI/xhs，可用 **L1 doctor + 契约测试** 录屏，文案注明「LIVE 需本机登录态」。

---

## 4. macOS 发布（P1）

| # | 项 | 说明 |
|---|-----|------|
| 14 | **Apple Developer 签名** | `APPLE_SIGNING_IDENTITY` |
| 15 | **Notarization 账号** | `APPLE_ID` + app-specific password |
| 16 | **DMG 分发策略** | GitHub Release vs 自有 CDN |
| 17 | **OpenCLI npm 包名确认** | 现文档 `@jackwener/opencli` |

---

## 5. 营销账号（P1）

| # | 渠道 | 用途 |
|---|------|------|
| 18 | 掘金 / CSDN | 技术文 #1–#2 |
| 19 | 知乎 | 长文 + 专栏 |
| 20 | 微信群（2–3 个） | 冷启动 |
| 21 | B 站 / 视频号 | Demo 上传 |
| 22 | Product Hunt / HN | 可选英文首发 |

---

## 6. 法律与合规（P0）

| # | 项 | 说明 |
|---|-----|------|
| 23 | **免责声明终审** | 法务过一遍中英文 |
| 24 | **隐私政策链接** | 若收集 device 注册信息 |
| 25 | **小红书/微信 ToS** | 对外文案是否需额外声明 |

---

## 7. 可选增强（P2）

| # | 项 |
|---|-----|
| 26 | 英文 README（README.en.md） |
| 27 | GitHub Sponsors / 商业支持邮箱 |
| 28 | Edge 专用 Discord / 飞书群 |
| 29 | 客户 Logo（B 端 One-Pager） |

---

## 8. 提供方式建议

请直接回复或开 Issue，格式：

```text
GitHub org: lqjack
Gateway URL: https://alphaplus-api.datapro.asia
Landing: https://alphaplus-landing.datapro.asia/edge  (或复用主 landing)
Demo 视频: https://...  (上传后)
Apple 签名: 有/无
```

收到 P0 项后，可执行：

```bash
# monorepo 内
bash scripts/edge/sync-to-standalone-repo.sh
cd alphaplus-edge && git init && gh repo create ...
```

---

**当前阻塞公开发布的最小集：** #1、#5、#9 或 #10（视频/GIF，截图已有）、#23。

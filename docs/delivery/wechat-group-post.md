# 微信群推广文案

**链接（带 UTM）：**  
`https://github.com/lqjack/alphaplus-edge?utm_source=wechat&utm_medium=group&utm_campaign=edge_launch`

---

## 版本 A — 隐私角度（推荐首发）

各位好，分享一个我们刚开源的组件 **AlphaPlus Edge**：

做投研都要刷小红书、公众号、微信，但 **登录态和聊天记录不适合.upload 到 SaaS**。

Edge 跑在你自己电脑上，云端只做 RAG 和 Agent 编排——Cookie 不出机。

开发者：`bash edge-doctor.sh` 5 分钟自检  
macOS 也有桌面安装包

GitHub：  
https://github.com/lqjack/alphaplus-edge

和 AlphaPlus 云端控制台配套用，不是单独玩具。

⚠️ 仅研究辅助，不构成投资建议。

---

## 版本 B — 工程师角度

开源 **AlphaPlus Edge** —— 本机 MCP（OpenCLI / wx-cli）+ WSS 隧道接 Neura Gateway。

云端仍 `POST /api/tools/call`，路由自动走 Edge 或 Cloud。  
有 LIVE E2E 脚本，无 mock。

适合：Cursor / 自研 Agent 要接小红书、微信本地库的同学。

👉 https://github.com/lqjack/alphaplus-edge

---

## 版本 C — 二次跟进（3 天后）

上次发的 Edge，有同学问和 ChatGPT 爬虫有啥区别：

- 不是云端代登录，是 **你本机浏览器/OpenCLI**
- 云端只收你确认同步的摘要，不是全文扒库
- 和 AlphaPlus 内容中枢、RAG 是一条 workflow

安装问题可以 GitHub Issue，我们收 doctor 日志。

---

## 发布检查

- [ ] 链接 UTM 正确
- [ ] 无收益承诺
- [ ] 至少附 1 张闭环截图（推荐 `assets/screenshots/alphaplus03-audit-cls-trace.png`）或架构图

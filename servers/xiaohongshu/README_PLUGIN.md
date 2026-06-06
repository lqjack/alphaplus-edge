# 小红书 Server × llm-gateway Plugin 全流程

## 能力矩阵

| Plugin 阶段 | MCP 工具 | 说明 |
|-------------|----------|------|
| 大V入库 `xhs-kol-ingest` | `sync_kol_notes` / `sync_notes` | 笔记 URL → XHS-Downloader 抽取 |
| 爆款分析 | `get_note_info` | 标题/正文/点赞/评论 |
| Mirofish 校准 | `get_note_metrics` | 仅互动指标 → `calibrate_with_real` |
| 发前检查 | `browser_open` + `browser_state` | OpenCLI 已登录 Chrome |
| 互动沙盘（真实） | `xhs_like_note` / `xhs_comment_note` / `xhs_reply_comment` | Browser Bridge 点击/填写 |
| 推演沙盘 | Mirofish `run_agent_interactions` | 与真实互动分离 |

## 启动

```bash
cd dataproai/src/servers/xiaohongshu
export XIAOHONGSHU_BACKEND=opencli   # 默认
export OPENCLI_BROWSER_SESSION=dataproai
pip install -r requirements.txt
python api_server.py   # :10350
python mcp_server.py   # :10351
```

前置：`npm i -g @jackwener/opencli` 且 `opencli doctor` 通过；Chrome 已登录小红书。

## llm-gateway 登记

```bash
# manifest: config/dataproai-servers/xiaohongshu.manifest.json
bun run sync:dataproai
```

环境：

```bash
DATAPROAI_GATEWAY_URL=http://127.0.0.1:8080
# Mirofish 校准时可设：
XHS_METRICS_URL=http://127.0.0.1:10350
```

## 与 Mirofish 闭环

1. `simulate_burst`（Mirofish）发前预测  
2. 发布后用 `get_note_metrics` 拉真实互动  
3. `calibrate_with_real` + `advance_simulation_stage`  
4. `merge:plugin-proposals` 沉淀经验  

详见 `llm-gateway/docs/mirofish-xhs-integration.md`。

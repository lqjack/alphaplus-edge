# 掘金 / CSDN 技术文大纲

**标题：** 《AlphaPlus Edge 实战：MCP 本地执行面 + WSS 云端隧道》

**UTM:** `?utm_source=juejin&utm_medium=article&utm_campaign=edge_launch`

---

## 标签

`MCP` `OpenCLI` `边缘计算` `Python` `投研工具`

---

## 大纲

### 1. 背景

- MCP 生态：工具在云端 vs 工具在本机
- 投研场景：哪些 tool **必须** edge（xhs、wx_cli）

### 2. 架构

- 组件表 + 端口表
- Sequence：UI → Gateway → Tunnel → Edge callback
- **Cloud 闭环截图**：`assets/screenshots/alphaplus01–03`（CLS Demo）

### 3. 核心代码走读（节选）

- `edge_health_server.py` — callback 入口
- `edge_tunnel_client.py` — WSS 重连
- `gateway/config/edge_tools.yaml` — 路由前缀

（链接 monorepo 源码，本仓 sync 后路径一致）

### 4. 本地跑通

分步骤 + 预期输出，引用 DEMO.md

### 5. 测试与 CI

```bash
python3 -m pytest scripts/edge/test_edge_ws_contract.py -q
```

### 6. 总结

- Star 链接
- dataproaiset 全栈链接
- 免责声明

---

## 代码块必备

```bash
export GATEWAY_URL=http://127.0.0.1:8001
bash scripts/edge/start-edge-stack.sh
curl -s http://127.0.0.1:10490/health | jq
```

---

## 字数目标

3500–4500 字（掘金偏好可拆 2 篇：架构一篇、E2E 一篇）

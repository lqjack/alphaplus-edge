# wx-cli MCP Server

个人微信本地数据 MCP/API 封装，底层调用 [jackwener/wx-cli](https://github.com/jackwener/wx-cli)。

## 前置

1. 安装：`npm install -g @jackwener/wx-cli`
2. macOS：`sudo wx init`（见 wx-cli README 签名步骤）
3. 环境变量：`WX_CLI_BIN=wx`（可选）

## 启动

```bash
cd dataproai/src/servers/wx_cli
python api_server.py   # http://127.0.0.1:10475
python mcp_server.py   # stdio MCP
```

## llm-gateway 注册

```bash
bun run register:wx-cli
```

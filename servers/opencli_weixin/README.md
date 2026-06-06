# OpenCLI Weixin Server

DataproAI server wrapping [jackwener/OpenCLI](https://github.com/jackwener/opencli/) for **WeChat Official Account** workflows — replaces Playwright-based browser automation in `wechat_viewer`.

## Prerequisites

```bash
npm install -g @jackwener/opencli
opencli doctor
```

- Chrome with **Browser Bridge** extension installed and connected
- For `weixin drafts` / `create-draft`: logged into [mp.weixin.qq.com](https://mp.weixin.qq.com)

## Start API (port 10485)

```bash
cd dataproai/src/servers/opencli_weixin
python api_server.py
```

## Tools

| Tool | OpenCLI command |
|------|-----------------|
| `opencli_doctor` | `opencli doctor` |
| `weixin_search` | `opencli weixin search <query>` |
| `weixin_download` | `opencli weixin download --url ...` |
| `weixin_drafts` | `opencli weixin drafts` |
| `weixin_create_draft` | `opencli weixin create-draft ...` |
| `browser_open` | `opencli browser dataproai open <url>` |
| `web_automation_*` | Mapped to OpenCLI browser primitives |

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENCLI_BIN` | `opencli` | OpenCLI executable |
| `OPENCLI_BROWSER_SESSION` | `dataproai` | Browser session name |
| `OPENCLI_TIMEOUT` | `180` | Command timeout (seconds) |

## Related

- `wx_cli` — personal WeChat chat via local DB (not browser)
- `wechat_viewer` MCP — now uses the same OpenCLI handler (`tool_handler_wechat_viewer.py`)

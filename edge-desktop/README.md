# AlphaPlus Edge Desktop (Tauri)

桌面版 Edge 桥接：一键启动本机 health server + 云端 WSS tunnel，并支持 Gateway 注册与 device token 轮换。

## macOS 安装包（推荐）

### 构建（开发者）

```bash
bash scripts/edge/build-macos-installer.sh
```

产物：

| 文件 | 说明 |
|------|------|
| `dist/edge-macos/AlphaPlus-Edge-0.1.0-macos.dmg` | 分发用 DMG |
| `dist/edge-macos/runtime/` | 最小 Python runtime（`scripts/edge` + `dataproai/src/core`） |
| `edge-desktop/src-tauri/target/release/bundle/macos/*.app` | 未打包 .app |

### 安装（用户）

1. 打开 `AlphaPlus-Edge-0.1.0-macos.dmg`
2. 双击 **Install AlphaPlus Edge.command**
3. 安装位置：
   - App：`~/Applications/AlphaPlus Edge.app`
   - Runtime：`~/Library/Application Support/AlphaPlus-Edge/runtime`
   - 环境模板：`~/Library/Application Support/AlphaPlus-Edge/edge.env`

首次打开若被 Gatekeeper 拦截：系统设置 → 隐私与安全性 → 仍要打开。

### 使用

1. 打开 **AlphaPlus Edge.app**
2. 填写 **Gateway URL**（云端或本机 `http://127.0.0.1:8001`）
3. 点击 **注册到 Gateway**，保存返回的 Device Token
4. 点击 **一键启动 Tunnel**

配置会保存在浏览器 localStorage（桌面 WebView）。

### 功能验证

```bash
# 本地 Gateway（~10s，无 cloud 服务 autostart）
bash scripts/edge/start-mac-gateway.sh

# 契约 + 本机 health server 真 HTTP（无 mock）
bash scripts/edge/verify-edge-macos.sh
```

CLI 等价（不装 .app）：

```bash
bash scripts/edge/install.sh          # 打印 env，可选启动 stack
bash scripts/edge/start-edge-stack.sh
bash scripts/edge/edge-doctor.sh
```

## 前置

- macOS 10.15+
- Python 3.10+（系统 `python3`）
- `pip install --user websockets`（安装脚本会自动执行）
- 可选：OpenCLI + wx-cli + 本地 MCP（小红书/微信能力）

## 开发

```bash
cd edge-desktop
npm install
npm run dev
```

开发时 runtime 默认使用仓库根目录（`edge-desktop/../..`）。打包安装后使用 Application Support 中的 runtime。

## 打包与签名

```bash
export APPLE_SIGNING_IDENTITY="Developer ID Application: Your Name (TEAMID)"
export APPLE_NOTarize=1
export APPLE_ID=you@example.com
export APPLE_APP_SPECIFIC_PASSWORD=xxxx-xxxx-xxxx-xxxx
export APPLE_TEAM_ID=TEAMID
bash scripts/edge/build-macos-signed.sh
```

未配置签名时产出**未签名** `.app`/DMG，可用于内测。

## 生产 WSS

桌面端将 `Public WSS Base` 写入 `GATEWAY_PUBLIC_URL`，tunnel 自动连接 `wss://…/api/edge/tunnel/ws`。

## 与 CLI 关系

| 能力 | CLI | Tauri |
|------|-----|-------|
| Health server | `edge_health_server.py` | `start_edge_stack` |
| Tunnel | `edge_tunnel_client.py` | `start_edge_stack` |
| Register | `register-with-gateway.sh` | `register_with_gateway` |
| Token 轮换 | `rotate-device-token.sh` | `rotate_device_token` |

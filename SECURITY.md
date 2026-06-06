# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅        |

## Reporting a vulnerability

Email: **security@YOUR_DOMAIN** (replace before public launch)

Please include:

- Description and impact
- Steps to reproduce
- Whether Edge device token or Gateway JWT is involved (do not send actual tokens)

We aim to respond within 7 business days.

## Scope

- Edge Agent (`edge_health_server.py`, tunnel client)
- Local MCP binding (must stay `127.0.0.1` by default)
- Device token handling

Out of scope: dataproaiset Cloud Gateway (report to monorepo SECURITY.md).

## Best practices for users

- Do not expose `:10490` or Edge MCP ports to LAN/WAN
- Rotate `EDGE_DEVICE_TOKEN` if compromised: `bash scripts/edge/rotate-device-token.sh`
- Use `GATEWAY_PUBLIC_URL` with valid TLS in production

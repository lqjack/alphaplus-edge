# -*- coding: utf-8 -*-
"""
WeChat Viewer MCP handler — OpenCLI backend (replaces Playwright).

Requires:
  npm i -g @jackwener/opencli
  Chrome + Browser Bridge extension (opencli doctor)
"""

import sys
from pathlib import Path

servers_dir = Path(__file__).resolve().parent.parent.parent
shared_dir = servers_dir / "shared"
for path in (str(servers_dir), str(shared_dir)):
    if path not in sys.path:
        sys.path.insert(0, path)

from shared.opencli_weixin_handler import OpenCLIWeixinToolHandler


class WechatViewerToolHandler(OpenCLIWeixinToolHandler):
    """MCP handler for wechat_viewer — delegates to OpenCLI."""

    pass

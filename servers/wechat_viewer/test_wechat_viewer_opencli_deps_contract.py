"""Contract: OpenCLI wechat_viewer backend does not import legacy YOLO/Playwright at init."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SERVER_DIR = Path(__file__).resolve().parent


@pytest.fixture(autouse=True)
def _opencli_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WECHAT_VIEWER_BACKEND", "opencli")
    monkeypatch.syspath_prepend(str(SERVER_DIR))
    for name in list(sys.modules):
        if name == "api_server" or name.startswith("automation.") or name.startswith("ocr."):
            sys.modules.pop(name, None)


def test_opencli_api_server_skips_legacy_imports() -> None:
    with patch.dict(os.environ, {"WECHAT_VIEWER_BACKEND": "opencli"}, clear=False):
        api = importlib.import_module("api_server")
        importlib.reload(api)
        server = api.WeChatViewerAPIServer()
    assert server.tool_handler is not None
    assert server.automation is None
    assert server.ocr_processor is None


def test_requirements_opencli_has_no_ultralytics() -> None:
    text = (SERVER_DIR / "requirements-opencli.txt").read_text(encoding="utf-8")
    assert "ultralytics" not in text
    assert "playwright" not in text
    assert "opencv-python" not in text


def test_requirements_legacy_includes_vision_stack() -> None:
    text = (SERVER_DIR / "requirements-legacy.txt").read_text(encoding="utf-8")
    assert "ultralytics" in text
    assert "playwright" in text

#!/usr/bin/env python3
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from edge_ws import gateway_public_base_url, gateway_ws_url


class EdgeWsContractTests(unittest.TestCase):
    def test_https_gateway_becomes_wss(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"GATEWAY_PUBLIC_URL": "", "EDGE_GATEWAY_PUBLIC_URL": ""},
            clear=False,
        ):
            url = gateway_ws_url(
                gateway_url="http://127.0.0.1:8001",
                token="abc123",
            )
        self.assertTrue(url.startswith("ws://127.0.0.1:8001/api/edge/tunnel/ws?token=abc123"))

    def test_public_url_overrides_gateway(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"GATEWAY_PUBLIC_URL": "https://gateway.example.com"},
            clear=False,
        ):
            base = gateway_public_base_url("http://127.0.0.1:8001")
            url = gateway_ws_url(gateway_url="http://127.0.0.1:8001", token="tok")
        self.assertEqual(base, "https://gateway.example.com")
        self.assertEqual(
            url,
            "wss://gateway.example.com/api/edge/tunnel/ws?token=tok",
        )


if __name__ == "__main__":
    unittest.main()

"""Contract tests for Edge gateway tool LIVE E2E helpers (offline)."""

import unittest

from live_edge_gateway_tool_e2e import ProbeResult, _port_up


class EdgeGatewayToolE2EContractTests(unittest.TestCase):
    def test_port_up_localhost_closed(self) -> None:
        self.assertFalse(_port_up("127.0.0.1", 1))

    def test_probe_result_fields(self) -> None:
        item = ProbeResult("test", "pass", "ok")
        self.assertEqual(item.name, "test")
        self.assertEqual(item.status, "pass")


if __name__ == "__main__":
    unittest.main()

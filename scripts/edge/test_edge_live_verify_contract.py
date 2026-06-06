"""Contract tests for Edge LIVE verify helpers (no live opencli/wx calls)."""

import unittest

from edge_live_checks import parse_opencli_doctor


class EdgeLiveVerifyContractTests(unittest.TestCase):
    def test_parse_opencli_doctor_healthy(self) -> None:
        stdout = """
opencli v1.8.0 doctor
[OK] Daemon: running
[OK] Extension: connected
[OK] Connectivity: ok
"""
        healthy, issues = parse_opencli_doctor(stdout)
        self.assertTrue(healthy)
        self.assertEqual(issues, [])

    def test_parse_opencli_doctor_unhealthy(self) -> None:
        stdout = """
[MISSING] Daemon: not running
[FAIL] Connectivity: failed (Failed to start opencli daemon)

Issues:
  • Daemon is not running.
  • Browser connectivity test failed.
"""
        healthy, issues = parse_opencli_doctor(stdout)
        self.assertFalse(healthy)
        self.assertGreaterEqual(len(issues), 2)
        self.assertTrue(any("Daemon" in item for item in issues))


if __name__ == "__main__":
    unittest.main()

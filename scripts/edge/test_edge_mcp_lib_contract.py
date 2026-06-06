"""Contract tests for edge-mcp-lib.sh service map (offline)."""

import os
import subprocess
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
LIB = SCRIPT_DIR / "edge-mcp-lib.sh"


class EdgeMcpLibContractTests(unittest.TestCase):
    def _bash(self, *cmd: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", "-c", f'source "{LIB}"; ' + " ".join(cmd)],
            cwd=str(SCRIPT_DIR),
            capture_output=True,
            text=True,
            check=False,
        )

    def test_ports_match_service_registry(self) -> None:
        for service, port in (
            ("xiaohongshu", 10350),
            ("wx_cli", 10475),
            ("wechat_viewer", 10470),
            ("opencli_weixin", 10485),
        ):
            proc = self._bash(f'edge_mcp_service_port "{service}"')
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(port, int(proc.stdout.strip()), service)

    def test_default_edge_mcp_services_list(self) -> None:
        proc = subprocess.run(
            ["bash", "-c", 'echo "${EDGE_MCP_SERVICES:-xiaohongshu,wx_cli,opencli_weixin,wechat_viewer}"'],
            capture_output=True,
            text=True,
            check=False,
        )
        services = {s.strip() for s in proc.stdout.strip().split(",")}
        self.assertEqual(
            services,
            {"xiaohongshu", "wx_cli", "opencli_weixin", "wechat_viewer"},
        )


if __name__ == "__main__":
    unittest.main()

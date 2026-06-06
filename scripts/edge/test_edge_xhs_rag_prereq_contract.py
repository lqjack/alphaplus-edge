"""Contract: live-edge-xhs-rag-e2e env gates (no live HTTP)."""

import os
import subprocess
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
SCRIPT = SCRIPT_DIR / "live-edge-xhs-rag-e2e.sh"


class EdgeXhsRagPrereqContractTests(unittest.TestCase):
    def _run(self, *extra_env: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["SKIP_LIVE_EDGE_RAG"] = "0"
        for item in extra_env:
            key, _, value = item.partition("=")
            env[key] = value
        return subprocess.run(
            ["bash", str(SCRIPT), *([] if "XHS_LIVE" in "".join(extra_env) else [])],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_skip_env_exits_zero(self) -> None:
        env = os.environ.copy()
        env["SKIP_LIVE_EDGE_RAG"] = "1"
        proc = subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        self.assertIn("SKIP", proc.stdout)

    def test_check_env_requires_share_input(self) -> None:
        env = os.environ.copy()
        env.pop("XHS_LIVE_SHARE_URL", None)
        env.pop("XHS_LIVE_SHARE_TEXT", None)
        proc = subprocess.run(
            ["bash", str(SCRIPT), "--check-env"],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("XHS_LIVE_SHARE_URL", proc.stderr + proc.stdout)

    def test_check_stack_ok_when_services_up(self) -> None:
        """Only runs when Mac stack is up; skipped in CI without services."""
        if os.environ.get("SKIP_LIVE_EDGE_RAG") == "1":
            self.skipTest("SKIP_LIVE_EDGE_RAG=1")
        proc = subprocess.run(
            ["bash", str(SCRIPT), "--check-stack"],
            cwd=str(REPO_ROOT),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0 and "not reachable" in (proc.stderr + proc.stdout):
            self.skipTest("stack not running on this host")
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)
        self.assertIn("OK: cloud+edge stack ready", proc.stdout)

    def test_check_auth_requires_login_cookies(self) -> None:
        proc = subprocess.run(
            ["bash", str(SCRIPT), "--check-auth"],
            cwd=str(REPO_ROOT),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            self.assertIn("OK: xiaohongshu session cookies harvested", proc.stdout)
            return
        self.assertEqual(proc.returncode, 1)
        combined = proc.stderr + proc.stdout
        self.assertTrue(
            "log into xiaohongshu.com" in combined or "only" in combined,
            combined,
        )

    def test_check_env_ok_with_url(self) -> None:
        env = os.environ.copy()
        env["XHS_LIVE_SHARE_URL"] = "https://www.xiaohongshu.com/explore/example"
        proc = subprocess.run(
            ["bash", str(SCRIPT), "--check-env"],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)


if __name__ == "__main__":
    unittest.main()

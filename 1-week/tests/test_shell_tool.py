import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools.file_system.path_guard import PathGuard
from tools.shell_tool import ShellTool


class ShellToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.tool = ShellTool(
            PathGuard(self.root),
            allowed_commands={"printf", "sleep"},
            bubblewrap_path="/usr/bin/bwrap",
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_runs_structured_argv_without_shell_interpretation(self) -> None:
        captured_command: list[str] = []

        def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
            captured_command.extend(command)
            kwargs["stdout"].write(b"$(id)")  # type: ignore[union-attr]
            return SimpleNamespace(returncode=0)

        with patch("tools.shell_tool.shell_tool.subprocess.run", fake_run):
            result = self.tool.execute(
                {
                    "argv": ["printf", "%s", "$(id)"],
                    "working_directory": ".",
                    "timeout_seconds": 2,
                }
            )

        self.assertEqual(result["stdout"], "$(id)")
        self.assertEqual(result["exit_code"], 0)
        self.assertFalse(result["timed_out"])
        self.assertIn("--unshare-all", captured_command)
        self.assertIn("--clearenv", captured_command)
        self.assertEqual(captured_command[-3:], ["/usr/bin/printf", "%s", "$(id)"])
        self.assertNotIn("sh", captured_command)

    def test_rejects_a_command_outside_the_allowlist(self) -> None:
        with self.assertRaisesRegex(ValueError, "not allowed"):
            self.tool.execute(
                {
                    "argv": ["sh", "-c", "id"],
                    "working_directory": ".",
                    "timeout_seconds": 2,
                }
            )

    def test_rejects_working_directory_traversal(self) -> None:
        with self.assertRaisesRegex(ValueError, "traversal"):
            self.tool.execute(
                {
                    "argv": ["printf", "hello"],
                    "working_directory": "../outside",
                    "timeout_seconds": 2,
                }
            )

    def test_reports_a_timeout_without_losing_partial_output(self) -> None:
        def fake_timeout(command: list[str], **kwargs: object) -> SimpleNamespace:
            del command
            kwargs["stdout"].write(b"partial")  # type: ignore[union-attr]
            raise subprocess.TimeoutExpired(cmd="bwrap", timeout=1)

        with patch("tools.shell_tool.shell_tool.subprocess.run", fake_timeout):
            result = self.tool.execute(
                {
                    "argv": ["sleep", "2"],
                    "working_directory": ".",
                    "timeout_seconds": 1,
                }
            )

        self.assertTrue(result["timed_out"])
        self.assertIsNone(result["exit_code"])
        self.assertEqual(result["stdout"], "partial")

    def test_refuses_to_run_without_bubblewrap(self) -> None:
        tool = ShellTool(
            PathGuard(self.root),
            allowed_commands={"printf"},
            bubblewrap_path=None,
        )
        tool.bubblewrap_path = None

        with self.assertRaisesRegex(RuntimeError, "requires Bubblewrap"):
            tool.execute(
                {
                    "argv": ["printf", "hello"],
                    "working_directory": ".",
                    "timeout_seconds": 2,
                }
            )


if __name__ == "__main__":
    unittest.main()

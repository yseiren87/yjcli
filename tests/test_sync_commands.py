from __future__ import annotations

import unittest
from unittest.mock import patch

from typer.testing import CliRunner

from yjcli.cli import app


class SyncConfirmationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_all_sync_commands_expose_yes(self) -> None:
        for command in ("agents", "skills", "make", "all", "migrate"):
            result = self.runner.invoke(app, ["sync", command, "--help"])
            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("--yes", result.output)

    @patch("yjcli.commands.sync.sync_svc.sync_agents")
    def test_invalid_and_empty_answers_are_asked_again(self, sync_agents) -> None:
        result = self.runner.invoke(
            app,
            ["sync", "agents"],
            input="\nyes\nx\ny\n",
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(result.output.count("Continue? [y/n]"), 4)
        self.assertEqual(result.output.count("Enter y or n."), 2)
        sync_agents.assert_called_once()

    @patch("yjcli.commands.sync.sync_svc.sync_agents")
    def test_n_cancels_without_overwriting(self, sync_agents) -> None:
        result = self.runner.invoke(app, ["sync", "agents"], input="n\n")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("sync cancelled.", result.output)
        sync_agents.assert_not_called()

    @patch("yjcli.commands.sync.sync_svc.sync_agents")
    def test_yes_flag_skips_confirmation(self, sync_agents) -> None:
        result = self.runner.invoke(app, ["sync", "agents", "--yes"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertNotIn("Continue?", result.output)
        sync_agents.assert_called_once()

    @patch("yjcli.commands.sync.sync_svc.sync_agents")
    def test_eof_requires_yes_without_overwriting(self, sync_agents) -> None:
        result = self.runner.invoke(app, ["sync", "agents"], input="")
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("non-interactive stdin; pass --yes", result.output)
        sync_agents.assert_not_called()


if __name__ == "__main__":
    unittest.main()

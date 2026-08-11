from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from typer.testing import CliRunner

from yjcli.cli import app
from yjcli.services import scaffold, sync as sync_svc, wiring


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


class DeployTemplateTests(unittest.TestCase):
    def test_platform_creation_installs_run_and_deploy_scripts(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            scaffold.create_platform(root, "cli")

            scripts = root / "cli" / "scripts"
            expected = {
                "run.sh",
                "run.bat",
                "deploy-common.sh",
                "deploy-common.bat",
                "deploy-development.sh",
                "deploy-development.bat",
                "deploy-production.sh",
                "deploy-production.bat",
            }
            self.assertEqual({path.name for path in scripts.iterdir()}, expected)
            for name in expected:
                if name.endswith(".sh"):
                    self.assertTrue((scripts / name).stat().st_mode & 0o111)

    def test_sync_make_preserves_existing_deploy_implementation(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            scaffold.create_platform(root, "cli")
            deploy = root / "cli" / "scripts" / "deploy-common.sh"
            deploy.write_text("custom deployment\n", encoding="utf-8")

            sync_svc.sync_make(root, force=True)

            self.assertEqual(deploy.read_text(encoding="utf-8"), "custom deployment\n")

    def test_make_deploy_routes_to_common_implementation_guard(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            scaffold.create_platform(root, "cli")
            (root / "cli" / "app").mkdir()
            sync_svc.sync_make(root, force=True)

            result = subprocess.run(
                ["make", "cli-deploy-development", "NAME=app"],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("deploy common is not implemented.", result.stdout)
            self.assertIn("deploy-common.sh", result.stdout)


class DiffTemplateTests(unittest.TestCase):
    def test_init_root_templates_create_diff_once_even_with_force(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            wiring.ensure_root_from_templates(root, force=True)
            diff = root / "Diff.md"
            self.assertTrue(diff.is_file())

            custom = "project-owned architecture notes\n"
            diff.write_text(custom, encoding="utf-8")
            wiring.ensure_root_from_templates(root, force=True)

            self.assertEqual(diff.read_text(encoding="utf-8"), custom)

    def test_sync_make_does_not_create_or_read_diff(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            scaffold.create_platform(root, "cli")

            sync_svc.sync_make(root, force=True)

            self.assertFalse((root / "Diff.md").exists())


if __name__ == "__main__":
    unittest.main()

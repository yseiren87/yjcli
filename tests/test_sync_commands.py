from __future__ import annotations

import os
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
                "run.ps1",
                "build-common.sh",
                "build-development.sh",
                "build-production.sh",
                "deploy-common.sh",
                "deploy-development.sh",
                "deploy-production.sh",
                "plugin-build-proto.sh",
                "plugin-build-ssr.sh",
                "plugin-build-docker.sh",
            }
            self.assertEqual({path.name for path in scripts.iterdir()}, expected)
            for name in expected:
                if name.endswith(".sh"):
                    self.assertTrue((scripts / name).stat().st_mode & 0o111)

    def test_sync_make_preserves_existing_build_implementation(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            scaffold.create_platform(root, "cli")
            build = root / "cli" / "scripts" / "build-common.sh"
            build.write_text("custom build\n", encoding="utf-8")

            sync_svc.sync_make(root, force=True)

            self.assertEqual(build.read_text(encoding="utf-8"), "custom build\n")

    def test_make_build_routes_to_common_implementation_guard(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            scaffold.create_platform(root, "cli")
            (root / "cli" / "app").mkdir()
            sync_svc.sync_make(root, force=True)

            result = subprocess.run(
                ["make", "cli-build-development", "NAME=app"],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("build common is not implemented.", result.stdout)
            self.assertIn("build-common.sh", result.stdout)

    def test_make_deploy_routes_to_build_implementation_guard(self) -> None:
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
            self.assertIn("build common is not implemented.", result.stdout)
            self.assertIn("build-common.sh", result.stdout)


class BuildPluginDetectionTests(unittest.TestCase):
    def test_plugin_scripts_are_separate_files_and_executable(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            scaffold.create_platform(root, "cli")

            for name in (
                "plugin-build-proto.sh",
                "plugin-build-ssr.sh",
                "plugin-build-docker.sh",
            ):
                plugin = root / "cli" / "scripts" / name
                self.assertTrue(plugin.is_file())
                self.assertTrue(plugin.stat().st_mode & 0o111)

            build_common = (root / "cli" / "scripts" / "build-common.sh").read_text(
                encoding="utf-8"
            )
            self.assertIn("plugin-build-*.sh", build_common)
            self.assertNotIn("protoc", build_common)

    def test_plugin_proto_runs_standalone_without_build_common(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            scaffold.create_platform(root, "backend")  # scaffold creates backend/proto/

            result = subprocess.run(
                ["bash", "scripts/plugin-build-proto.sh", "development"],
                cwd=root / "backend",
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("protoc codegen is not implemented", result.stdout)

    def test_build_common_and_plugins_are_identical_across_platforms(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            scaffold.create_platform(root, "backend")
            scaffold.create_platform(root, "cli")

            for name in (
                "build-common.sh",
                "plugin-build-proto.sh",
                "plugin-build-ssr.sh",
                "plugin-build-docker.sh",
            ):
                backend_text = (root / "backend" / "scripts" / name).read_text(
                    encoding="utf-8"
                )
                cli_text = (root / "cli" / "scripts" / name).read_text(encoding="utf-8")
                self.assertEqual(backend_text, cli_text)

            plugin_proto = (root / "backend" / "scripts" / "plugin-build-proto.sh").read_text(
                encoding="utf-8"
            )
            self.assertIn("protoc", plugin_proto)
            self.assertNotIn("buf", plugin_proto)

    def test_build_common_flags_protoc_only_when_proto_dir_exists(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            scaffold.create_platform(root, "backend")  # scaffold already creates backend/proto/
            scaffold.create_platform(root, "cli")  # no proto/ sibling

            backend_result = subprocess.run(
                ["bash", "scripts/build-common.sh", "development"],
                cwd=root / "backend",
                capture_output=True,
                text=True,
                check=False,
            )
            cli_result = subprocess.run(
                ["bash", "scripts/build-common.sh", "development"],
                cwd=root / "cli",
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertIn("protoc codegen is not implemented", backend_result.stdout)
            self.assertNotIn("protoc", cli_result.stdout)

    def test_build_common_flags_protoc_for_any_platform_with_proto_dir(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            scaffold.create_platform(root, "cli")
            (root / "cli" / "proto").mkdir()

            result = subprocess.run(
                ["bash", "scripts/build-common.sh", "development"],
                cwd=root / "cli",
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertIn("protoc codegen is not implemented", result.stdout)

    def test_build_common_flags_views_only_for_service_that_has_them(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            scaffold.create_platform(root, "backend-service")
            (root / "backend-service" / "svc1" / "views").mkdir(parents=True)
            (root / "backend-service" / "svc2").mkdir(parents=True)

            all_result = subprocess.run(
                ["bash", "scripts/build-common.sh", "development"],
                cwd=root / "backend-service",
                capture_output=True,
                text=True,
                check=False,
            )
            svc1_result = subprocess.run(
                ["bash", "scripts/build-common.sh", "development", "svc1"],
                cwd=root / "backend-service",
                capture_output=True,
                text=True,
                check=False,
            )
            svc2_result = subprocess.run(
                ["bash", "scripts/build-common.sh", "development", "svc2"],
                cwd=root / "backend-service",
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertIn("template/asset build is not implemented", all_result.stdout)
            self.assertIn("template/asset build is not implemented", svc1_result.stdout)
            self.assertNotIn("template/asset build is not implemented", svc2_result.stdout)

    def test_build_common_flags_views_for_any_platform_with_a_views_service(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            scaffold.create_platform(root, "backend")
            (root / "backend" / "svc1" / "views").mkdir(parents=True)

            result = subprocess.run(
                ["bash", "scripts/build-common.sh", "development"],
                cwd=root / "backend",
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertIn("template/asset build is not implemented", result.stdout)


class DockerBuildPluginTests(unittest.TestCase):
    def test_docker_templates_only_for_deployable_platforms(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            scaffold.create_platform(root, "backend")
            scaffold.create_service(root, "backend", "api")
            scaffold.create_platform(root, "cli")
            scaffold.create_service(root, "cli", "tool")

            self.assertTrue((root / "backend" / "api" / "Dockerfile").is_file())
            self.assertTrue((root / "backend" / "api" / ".dockerignore").is_file())
            self.assertFalse((root / "cli" / "tool" / "Dockerfile").exists())
            self.assertFalse((root / "cli" / "tool" / ".dockerignore").exists())

    def test_dockerfile_stub_has_no_from_instruction(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            scaffold.create_platform(root, "backend")
            scaffold.create_service(root, "backend", "api")

            dockerfile = (root / "backend" / "api" / "Dockerfile").read_text(encoding="utf-8")
            for line in dockerfile.splitlines():
                self.assertFalse(line.strip().upper().startswith("FROM"))

    def test_plugin_resolves_version_from_package_json(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            scaffold.create_platform(root, "backend")
            scaffold.create_service(root, "backend", "web")
            (root / "backend" / "web" / "package.json").write_text(
                '{"name": "web", "version": "1.2.3"}\n', encoding="utf-8"
            )
            (root / "backend" / "web" / ".env.development").write_text(
                "PORT=8080\n", encoding="utf-8"
            )

            result = subprocess.run(
                ["bash", "scripts/plugin-build-docker.sh", "development", "web"],
                cwd=root / "backend",
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("version=1.2.3", result.stdout)

    def test_plugin_resolves_version_from_pyproject_toml(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            scaffold.create_platform(root, "backend")
            scaffold.create_service(root, "backend", "worker")
            (root / "backend" / "worker" / "pyproject.toml").write_text(
                '[project]\nname = "worker"\nversion = "0.9.0"\n', encoding="utf-8"
            )
            (root / "backend" / "worker" / ".env.development").write_text(
                "PORT=9090\n", encoding="utf-8"
            )

            result = subprocess.run(
                ["bash", "scripts/plugin-build-docker.sh", "development", "worker"],
                cwd=root / "backend",
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("version=0.9.0", result.stdout)

    def test_plugin_falls_back_to_version_env_var(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            scaffold.create_platform(root, "backend")
            scaffold.create_service(root, "backend", "goapp")
            (root / "backend" / "goapp" / ".env.development").write_text(
                "PORT=7070\n", encoding="utf-8"
            )

            no_version = subprocess.run(
                ["bash", "scripts/plugin-build-docker.sh", "development", "goapp"],
                cwd=root / "backend",
                capture_output=True,
                text=True,
                check=False,
            )
            with_version = subprocess.run(
                ["bash", "scripts/plugin-build-docker.sh", "development", "goapp"],
                cwd=root / "backend",
                capture_output=True,
                text=True,
                check=False,
                env={**os.environ, "VERSION": "3.0.0"},
            )

            self.assertEqual(no_version.returncode, 0)
            self.assertIn("could not resolve a version", no_version.stdout)
            self.assertEqual(with_version.returncode, 0)
            self.assertIn("version=3.0.0", with_version.stdout)

    def test_plugin_skips_service_without_dockerfile(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            scaffold.create_platform(root, "backend")
            scaffold.create_service(root, "backend", "api")
            (root / "backend" / "api" / "Dockerfile").unlink()

            result = subprocess.run(
                ["bash", "scripts/plugin-build-docker.sh", "development"],
                cwd=root / "backend",
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0)
            self.assertNotIn("docker", result.stdout)

    def test_plugin_is_picked_up_by_build_common(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            scaffold.create_platform(root, "backend")
            scaffold.create_service(root, "backend", "web")
            (root / "backend" / "web" / "package.json").write_text(
                '{"version": "1.0.0"}\n', encoding="utf-8"
            )
            (root / "backend" / "web" / ".env.development").write_text(
                "PORT=8080\n", encoding="utf-8"
            )

            result = subprocess.run(
                ["bash", "scripts/build-common.sh", "development", "web"],
                cwd=root / "backend",
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertIn("[build] docker: web", result.stdout)
            self.assertIn("build common is not implemented.", result.stdout)


class DeployCommonPluginHostTests(unittest.TestCase):
    def test_deploy_scripts_call_deploy_common(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            scaffold.create_platform(root, "backend")

            for name in ("deploy-development.sh", "deploy-production.sh"):
                text = (root / "backend" / "scripts" / name).read_text(encoding="utf-8")
                self.assertIn("deploy-common.sh", text)

            deploy_common = (root / "backend" / "scripts" / "deploy-common.sh").read_text(
                encoding="utf-8"
            )
            self.assertIn("plugin-deploy-*.sh", deploy_common)

    def test_deploy_common_is_a_noop_when_no_deploy_plugins_ship(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            scaffold.create_platform(root, "backend")
            (root / "backend" / "app").mkdir()
            # Fake a successful build so deploy-common.sh's own logic is reached.
            build_dev = root / "backend" / "scripts" / "build-development.sh"
            build_dev.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            build_dev.chmod(build_dev.stat().st_mode | 0o111)

            result = subprocess.run(
                ["bash", "scripts/deploy-development.sh", "app"],
                cwd=root / "backend",
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("development upload is not implemented.", result.stdout)

    def test_deploy_common_runs_a_dropped_in_deploy_plugin(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            scaffold.create_platform(root, "backend")
            (root / "backend" / "app").mkdir()
            build_dev = root / "backend" / "scripts" / "build-development.sh"
            build_dev.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            build_dev.chmod(build_dev.stat().st_mode | 0o111)

            fake_plugin = root / "backend" / "scripts" / "plugin-deploy-fake.sh"
            fake_plugin.write_text(
                '#!/usr/bin/env bash\necho "[deploy] fake plugin ran: $1 $2"\n',
                encoding="utf-8",
            )
            fake_plugin.chmod(fake_plugin.stat().st_mode | 0o111)

            result = subprocess.run(
                ["bash", "scripts/deploy-development.sh", "app"],
                cwd=root / "backend",
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertIn("[deploy] fake plugin ran: development app", result.stdout)


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

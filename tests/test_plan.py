"""Plans and applying them: ownership policies, removals, rollback, references."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from yjcli.apply import ApplyError, apply
from yjcli.cli import _wizard_collect
from yjcli.plan import Change, build_plan
from yjcli.references import stale_references
from yjcli.repo import read_repo
from yjcli.selection import Request, fill_defaults, resolve
from yjcli.ui.wizard import installed_label


def plan_for(root: Path, *, llm=None, platform=None, plugin=None, name=None, proto_lang=None, secrets=None,
             env=None, skill=None, remove=None):
    """The plan `yjcli wizard <args>` would make (plus unit removals)."""
    repo = read_repo(root)
    req, errors = Request(), []
    _wizard_collect(llm, platform, plugin, name, proto_lang, secrets, env, skill)(req, repo, errors)
    assert errors == [], errors
    req.remove.update(remove or {})
    fill_defaults(req, repo)
    cfg, errors = resolve(req, repo)
    assert errors == [], errors
    return build_plan(cfg, repo, version="9.9.9", notes=req.notes)


def run(root: Path, **args):
    plan = plan_for(root, **args)
    apply(plan, root)
    return plan


def snapshot(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): (p.read_bytes() if p.is_file() else None, p.stat().st_mode)
            for p in root.rglob("*")}


class CreateTests(unittest.TestCase):
    def test_new_repository(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "My Shop"
            plan = run(root, llm=["claude"], name=["backend-msa=user", "frontend=web"], proto_lang=["go,python"],
                       plugin=["all"])
            for path in ("backend-msa/user/apps", "backend-msa/user/.env.examples", "frontend/web/package.json",
                         "proto/dist/go/go.mod", "proto/dist/python/pyproject.toml", "tools/builder/proto/builder.sh",
                         "tools/secrets/frontend/web/.env.local-dev", ".claude/skills/yj-proto/SKILL.md",
                         ".claude/settings.json", "CLAUDE.md", "Makefile", "make.ps1", "AGENTS.md", ".gitignore"):
                self.assertTrue((root / path).exists(), path)
            self.assertIn("module my-shop/proto", (root / "proto/dist/go/go.mod").read_text())
            self.assertIn('"name": "web"', (root / "frontend/web/package.json").read_text())
            self.assertIn("__APP_NAME__", (root / "frontend/web/vite.config.ts").read_text())
            self.assertTrue((root / "tools/runner/frontend/runner.sh").stat().st_mode & 0o111)
            self.assertFalse((root / "tools/runner/proto").exists())
            gen = (root / "tools/builder/proto/builder.sh").read_text()
            self.assertIn("gen_go()", gen)
            self.assertNotIn("gen_dart()", gen)
            self.assertIn("PLATFORMS := backend-msa frontend", (root / "Makefile").read_text())
            self.assertIn("!proto/dist/", (root / ".gitignore").read_text())
            self.assertIn("- Backward compatibility: `ask`", (root / "AGENTS.md").read_text())
            self.assertIn("## Changes and compatibility", (root / ".claude/skills/yj-arch-core/SKILL.md").read_text())
            for f in root.rglob("*"):
                if f.is_file() and f.suffix in (".md", ".sh", ".ps1", "") and ".yjcli" not in f.parts:
                    self.assertNotIn("{{", f.read_text(errors="replace"), f)
            self.assertEqual(plan_for(root).file_changes, [])  # idempotent

    def test_secrets_off_platform(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            run(root, llm=["claude"], name=["backend=a"], plugin=["all"], secrets=["none"])
            self.assertFalse((root / "tools/secrets").exists())
            for tool in ("runner", "builder", "deployer"):
                self.assertNotIn("SECRETS_DIR", (root / f"tools/{tool}/backend/{tool}.sh").read_text())
            self.assertIn("does not use `tools/secrets/`", (root / ".claude/skills/yj-arch-core/SKILL.md").read_text())
            self.assertNotIn("!tools/secrets/", (root / ".gitignore").read_text())


class OptionalSkillTests(unittest.TestCase):
    def test_default_on_then_removed_and_added(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            run(root, llm=["claude", "codex"], name=["backend=a1"], plugin=["none"])
            for d in (".claude/skills", ".agents/skills"):
                self.assertTrue((root / d / "yj-secure-coding/SKILL.md").is_file())
                self.assertTrue((root / d / "yj-dependency-security/SKILL.md").is_file())
            self.assertIn("`yj-dependency-security` — when adding", (root / "AGENTS.md").read_text())
            self.assertIn("`yj-secure-coding` — when writing", (root / ".claude/skills/yj-arch-core/SKILL.md").read_text())

            plan = run(root, skill=["yj-dependency-security"])
            self.assertEqual(sorted(r.path for r in plan.removals),
                             [".agents/skills/yj-secure-coding", ".claude/skills/yj-secure-coding"])
            self.assertFalse(plan.removes_code)
            self.assertNotIn("yj-secure-coding", (root / "AGENTS.md").read_text())
            self.assertEqual(read_repo(root).manifest.skills, ["yj-dependency-security"])

            run(root, skill=["none"])
            self.assertNotIn("Also load", (root / "AGENTS.md").read_text())
            self.assertNotIn("Also load", (root / ".claude/skills/yj-arch-core/SKILL.md").read_text())
            self.assertEqual(plan_for(root).file_changes, [])


class EnvironmentTests(unittest.TestCase):
    def envs(self, root: Path, service: str = "backend/a1") -> list[str]:
        return sorted(f.name for f in (root / "tools/secrets" / service).glob(".env.*"))

    def test_fixed_and_added_at_creation(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            run(root, llm=["claude"], name=["backend=a1", "frontend=f1"], plugin=["builder"], env=["development, stage"])
            self.assertEqual(self.envs(root), [".env.development", ".env.local-dev", ".env.production", ".env.stage"])
            self.assertIn("127.0.0.1", (root / "tools/secrets/backend/a1/.env.local-dev").read_text())
            self.assertIn("0.0.0.0", (root / "tools/secrets/backend/a1/.env.stage").read_text())
            package = (root / "frontend/f1/package.json").read_text()
            self.assertIn('"build:stage": "tsc -b && vite build --mode stage",', package)
            self.assertNotIn("__ENV_SCRIPTS__", package)
            self.assertIn("production | development | stage", (root / "Makefile").read_text())
            self.assertEqual(plan_for(root).file_changes, [])

    def test_default_is_local_dev_and_production(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            run(root, llm=["claude"], name=["backend=a1"], plugin=["none"])
            self.assertEqual(self.envs(root), [".env.local-dev", ".env.production"])

    def test_new_services_follow_added_environments(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            run(root, llm=["claude"], name=["backend=a1"], plugin=["none"])
            (root / "tools/secrets/backend/a1/.env.development").write_text("NAME=a1\n")  # a 0.6 repository
            run(root, name=["backend=a2"])
            self.assertEqual(self.envs(root, "backend/a2"), [".env.development", ".env.local-dev", ".env.production"])
            self.assertEqual((root / "tools/secrets/backend/a1/.env.development").read_text(), "NAME=a1\n")

    def test_add_and_remove(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            run(root, llm=["claude"], name=["backend=a1,a2"], plugin=["none"])
            repo = read_repo(root)
            req = Request(envs_add=["stage"])
            fill_defaults(req, repo)
            cfg, _ = resolve(req, repo)
            apply(build_plan(cfg, repo, version="9.9.9"), root)
            self.assertIn(".env.stage", self.envs(root, "backend/a2"))
            self.assertIn("tools/secrets/backend/a2/.env.stage", read_repo(root).manifest.files)

            repo = read_repo(root)
            req = Request(envs_remove=["stage"])
            fill_defaults(req, repo)
            cfg, _ = resolve(req, repo)
            plan = build_plan(cfg, repo, version="9.9.9")
            self.assertEqual({(c.kind, c.path) for c in plan.changes if c.kind == "delete"},
                             {("delete", f"tools/secrets/backend/{s}/.env.stage") for s in ("a1", "a2")})
            self.assertFalse(plan.removes_code)
            apply(plan, root)
            self.assertEqual(self.envs(root, "backend/a2"), [".env.local-dev", ".env.production"])
            self.assertFalse(any(".env.stage" in rel for rel in read_repo(root).manifest.files))

    def test_hand_deleted_environment_leaves_the_manifest(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            run(root, llm=["claude"], name=["backend=a1,a2"], plugin=["none"], env=["stage"])
            (root / "tools/secrets/backend/a1/.env.stage").unlink()
            run(root)  # partly deleted: remembered as an opt-out
            self.assertNotIn(".env.stage", self.envs(root))
            self.assertIn("tools/secrets/backend/a1/.env.stage", read_repo(root).manifest.files)
            (root / "tools/secrets/backend/a2/.env.stage").unlink()
            run(root)
            self.assertFalse(any(".env.stage" in rel for rel in read_repo(root).manifest.files))


class UpdateTests(unittest.TestCase):
    def test_local_edits_are_overwritten_and_reported(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            run(root, llm=["claude"], name=["backend=a1"], plugin=["runner"])
            guide = root / "tools/runner/GUIDE.md"
            guide.write_text(guide.read_text() + "tweak\n")
            agents = root / "AGENTS.md"
            text = agents.read_text()
            start, end = text.index("<!-- yjcli:layout -->"), text.index("<!-- /yjcli:layout -->") + 22
            agents.write_text(text[:start] + text[end:])
            plan = plan_for(root)
            notes = {c.path: c.note for c in plan.changes}
            self.assertEqual(notes["tools/runner/GUIDE.md"], "로컬 수정 덮어씀")
            self.assertEqual(len(plan.review), 3)  # GUIDE.md, the missing block, the edited blocks
            apply(plan, root)
            self.assertNotIn("tweak", guide.read_text())
            self.assertIn("<!-- yjcli:layout -->", agents.read_text())
            backup = root / plan.backup
            self.assertTrue((backup / "tools/runner/GUIDE.md").read_text().endswith("tweak\n"))
            self.assertNotIn("<!-- yjcli:layout -->", (backup / "AGENTS.md").read_text())
            guide_text = (backup / "MERGE.md").read_text()
            self.assertIn("| `tools/runner/GUIDE.md` |", guide_text)
            self.assertNotIn("{{", guide_text)
            self.assertIn("/.yjcli/backup/", (root / ".gitignore").read_text())

    def test_untouched_blocks_are_not_backed_up(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            run(root, llm=["claude"], name=["backend=a1"], plugin=["runner"])
            agents = root / "AGENTS.md"
            agents.write_text(agents.read_text().replace("- `<rule>`", "- my rule"))  # outside the blocks
            plan = run(root, name=["frontend=f1"])
            self.assertIn("AGENTS.md", [c.path for c in plan.changes if c.kind == "merge"])
            self.assertEqual([c.path for c in plan.changes if c.kind == "backup"], [])
            self.assertFalse((root / ".yjcli/backup").exists())

    def test_seeds_stay_and_opt_outs_are_remembered(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            run(root, llm=["claude"], name=["backend=a1"], plugin=["runner"])
            script = root / "tools/runner/backend/runner.sh"
            script.write_text("mine\n")
            (root / "tools/secrets/backend/a1/.env.production").unlink()
            plan = run(root, name=["backend=a2"])
            self.assertEqual(script.read_text(), "mine\n")
            created = {c.path for c in plan.changes if c.kind == "create"}
            self.assertIn("tools/secrets/backend/a2/.env.production", created)
            self.assertNotIn("tools/secrets/backend/a1/.env.production", created)

    def test_skill_additions(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".yjcli/skills").mkdir(parents=True)
            (root / ".yjcli/skills/yj-backend.md").write_text("- local rule\n")
            (root / ".yjcli/skills/yj-typo.md").write_text("x\n")
            plan = run(root, llm=["claude"], name=["backend=a1"], plugin=["none"])
            self.assertTrue((root / ".claude/skills/yj-backend/SKILL.md").read_text().endswith("- local rule\n"))
            self.assertTrue(any("yj-typo.md" in w for w in plan.warnings))

    def test_file_yjcli_never_wrote_is_skipped(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CLAUDE.md").write_text("hand made\n")
            plan = run(root, llm=["claude"], name=["backend=a1"], plugin=["none"])
            self.assertEqual((root / "CLAUDE.md").read_text(), "hand made\n")
            self.assertTrue(any(w.startswith("! CLAUDE.md") for w in plan.warnings))


class RemovalTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.root = root = Path(self._tmp.name)
        run(root, llm=["claude", "codex"], name=["backend=a1,a2", "frontend=f1"], plugin=["runner", "builder"])
        (root / "tools/runner/backend/helper.sh").write_text("# added by the project\n")
        (root / "tools/secrets/backend/a2/.env.local-dev").write_text("API_KEY=real\n")
        (root / ".claude/skills/my-skill").mkdir()
        (root / ".claude/skills/my-skill/SKILL.md").write_text("mine\n")
        (root / "dist/backend/a2").mkdir(parents=True)
        (root / "dist/backend/a2/app").write_text("bin")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def gone(self, *paths: str) -> None:
        for p in paths:
            self.assertFalse((self.root / p).exists(), p)

    def test_plugin_folder_goes_whole(self) -> None:
        plan = run(self.root, plugin=["builder"])
        self.assertEqual([r.path for r in plan.removals], ["tools/runner"])
        self.assertFalse(plan.removes_code)
        self.gone("tools/runner")
        self.assertTrue((self.root / "Makefile").exists())
        run(self.root, plugin=["none"])
        self.gone("Makefile", "make.ps1", "tools/builder")

    def test_service_takes_code_env_and_build(self) -> None:
        plan = run(self.root, remove={"backend": ["a2"]})
        self.assertTrue(plan.removes_code)
        self.gone("backend/a2", "tools/secrets/backend/a2", "dist/backend/a2")
        self.assertEqual(read_repo(self.root).manifest.units["backend"], ["a1"])

    def test_last_service_takes_the_platform(self) -> None:
        run(self.root, remove={"frontend": ["f1"]})
        self.gone("frontend", "tools/runner/frontend", "tools/builder/frontend", "tools/secrets/frontend",
                  ".claude/skills/yj-frontend", ".agents/skills/yj-frontend")
        self.assertNotIn("frontend", read_repo(self.root).manifest.units)

    def test_llm_keeps_shared_paths(self) -> None:
        run(self.root, llm=["codex"])
        self.gone(".claude/skills", "CLAUDE.md", ".claude/settings.json")
        self.assertTrue((self.root / "AGENTS.md").exists())
        self.assertTrue((self.root / ".agents/skills/yj-backend/SKILL.md").exists())

    def test_secrets_off_takes_filled_values(self) -> None:
        run(self.root, secrets=["frontend"])
        self.gone("tools/secrets/backend")
        self.assertIn("backend", read_repo(self.root).manifest.secrets_off)

    def test_dropping_a_platform_from_the_list_is_code_removal(self) -> None:
        plan = plan_for(self.root, platform=["frontend"])
        self.assertIn("backend", [r.path for r in plan.removals if r.code])

    def test_wizard_marks_installed(self) -> None:
        repo = read_repo(self.root)
        self.assertEqual(installed_label(repo, "backend"), "  설치됨 · a1, a2")
        self.assertEqual(installed_label(repo, "cli"), "")

    def test_failed_apply_restores_everything(self) -> None:
        before = snapshot(self.root)
        plan = plan_for(self.root, llm=["codex"], name=["backend=a3"], plugin=["builder"], remove={"backend": ["a2"]})
        self.assertTrue({"create", "rmtree", "delete"} <= {c.kind for c in plan.changes})
        plan.changes.insert(len(plan.changes) - 1, Change("create", "AGENTS.md/blocked", b"x"))
        with self.assertRaises(ApplyError) as caught:
            apply(plan, self.root)
        self.assertEqual(caught.exception.unrestored, [])
        self.assertEqual(snapshot(self.root), before)


class ReferenceTests(unittest.TestCase):
    def test_only_outside_blocks(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text("<!-- yjcli:x -->\ntools/runner/ inside\n<!-- /yjcli:x -->\n"
                                            "see tools/runner/GUIDE.md\nmake backend-build-production\n")
            found = stale_references(root, ["claude"], [], ["backend"])
            self.assertEqual(len(found), 2)
            self.assertIn("AGENTS.md:4", found[0])
            self.assertIn("AGENTS.md:5", found[1])


if __name__ == "__main__":
    unittest.main()

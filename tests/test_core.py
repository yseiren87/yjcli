from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from yjcli.catalog import data_root
from yjcli.catalog.platforms import PLATFORMS
from yjcli.catalog.plugins import PLUGINS, disabled_reasons, drop_dependents, missing_requires
from yjcli.catalog.skills import SKILLS, routing_rows, skills_for
from yjcli.core import render as r
from yjcli.core.manifest import FileRecord, Manifest, dumps, is_older, load
from yjcli.core.names import parse_names
from yjcli.core.planner import build_plan
from yjcli.core.selection import fill_from_manifest, from_args, missing
from yjcli.core.state import read_state


class RenderTests(unittest.TestCase):
    def test_variables_and_blocks(self) -> None:
        text = "a {{x}}\n{{#if on}}\nyes\n{{else}}\nno\n{{/if}}\nend {{#if off}}hidden{{/if}}\n"
        self.assertEqual(r.render(text, {"x": 1, "on": True, "off": False}), "a 1\nyes\nend \n")
        self.assertEqual(r.render(text, {"x": 1, "on": False, "off": False}), "a 1\nno\nend \n")

    def test_nested_blocks(self) -> None:
        text = "{{#if a}}A{{#if b}}B{{/if}}{{/if}}"
        self.assertEqual(r.render(text, {"a": True, "b": False}), "A")
        self.assertEqual(r.render(text, {"a": False, "b": True}), "")

    def test_unknown_variable_fails(self) -> None:
        with self.assertRaises(r.RenderError):
            r.render("{{nope}}", {})
        with self.assertRaises(r.RenderError):
            r.render("{{#if a}}x", {"a": True})

    def test_replace_block(self) -> None:
        text = "top\n<!-- yjcli:s -->\nold\n<!-- /yjcli:s -->\nbottom\n"
        self.assertEqual(r.replace_block(text, "s", "new"), "top\n<!-- yjcli:s -->\nnew\n<!-- /yjcli:s -->\nbottom\n")
        self.assertIsNone(r.replace_block("no markers", "s", "x"))


class NameTests(unittest.TestCase):
    def test_separators(self) -> None:
        for raw in ("a1,a2", "a1 a2", "a1, a2", " a1,,a2 "):
            self.assertEqual(parse_names(raw).names, ["a1", "a2"], raw)

    def test_errors_and_duplicates(self) -> None:
        parsed = parse_names("ok -bad proto ok taken", existing={"taken"})
        self.assertEqual(parsed.names, ["ok"])
        self.assertEqual(len(parsed.errors), 3)
        self.assertEqual(len(parsed.notes), 1)


class PluginTests(unittest.TestCase):
    def test_deployer_needs_builder(self) -> None:
        self.assertEqual(len(missing_requires(["runner", "deployer"])), 1)
        self.assertEqual(missing_requires(["builder", "deployer"]), [])
        self.assertIsNotNone(disabled_reasons(["runner"])["deployer"])
        self.assertIsNone(disabled_reasons(["builder"])["deployer"])
        self.assertIsNone(disabled_reasons([])["builder"])

    def test_dropping_a_requirement_drops_dependents(self) -> None:
        self.assertEqual(drop_dependents(["runner", "deployer"]), (["runner"], ["deployer"]))
        self.assertEqual(drop_dependents(["builder", "deployer"])[1], [])


class SkillCatalogTests(unittest.TestCase):
    """Doc §5.7 — catalog and template consistency."""

    skills_dir = data_root() / "skills"

    def test_every_platform_has_existing_skills(self) -> None:
        ids = {s.id for s in SKILLS}
        for p in PLATFORMS:
            self.assertTrue(p.skills, p.id)
            self.assertTrue(set(p.skills) <= ids, p.id)

    def test_routes_start_with_a_platform(self) -> None:
        platform_ids = {p.id for p in PLATFORMS}
        for skill in SKILLS:
            for pattern, _ in skill.routes:
                self.assertIn(pattern.split("/", 1)[0], platform_ids, pattern)

    def test_skill_templates_and_fragments_exist(self) -> None:
        for skill in SKILLS:
            self.assertTrue((self.skills_dir / skill.id / "SKILL.md").is_file(), skill.id)
        for plugin in PLUGINS:
            if plugin.skill_fragment:
                self.assertTrue((self.skills_dir / "_shared" / plugin.skill_fragment).is_file())

    def test_shared_fragments_are_all_used(self) -> None:
        texts = "\n".join(p.read_text() for p in self.skills_dir.glob("yj-*/SKILL.md"))
        fragments = {p.skill_fragment for p in PLUGINS}
        for f in (self.skills_dir / "_shared").iterdir():
            self.assertTrue(f.name in fragments or f"include:{f.name}" in texts, f"unused fragment {f.name}")

    def test_platform_skills_have_no_tool_paths_or_old_names(self) -> None:
        for skill in SKILLS:
            text = (self.skills_dir / skill.id / "SKILL.md").read_text()
            self.assertNotIn("backend-service", text, skill.id)
            self.assertNotIn("plugin-build", text, skill.id)
            if skill.kind == "platform":
                for bad in ("tools/", ".env.local-dev", "Do not use for"):
                    self.assertNotIn(bad, text, f"{skill.id}: {bad}")

    def test_powershell_templates_are_ascii(self) -> None:
        # Windows PowerShell 5.1 reads BOM-less .ps1 as ANSI: UTF-8 dashes turn into
        # smart quotes and break parsing.
        for f in (data_root() / "plugins").rglob("*.ps1"):
            self.assertTrue(f.read_bytes().isascii(), f"{f.relative_to(data_root())} has non-ASCII bytes")

    def test_native_route_comes_first(self) -> None:
        rows = routing_rows(["browser-extension"], skills_for(["browser-extension"]))
        self.assertIn("native_*", rows[0][0])


def plan_for(root: Path, **args):
    state = read_state(root)
    base = dict(mode=None, llm=None, platform=None, plugin=None, name=None, option=None)
    draft, errors = from_args(state, **{**base, **args})
    assert errors == [], errors
    fill_from_manifest(draft, state)
    return build_plan(draft, state, version="test")


class PlannerTests(unittest.TestCase):
    def _plan(self, root: Path, **args):
        return plan_for(root, **args)

    def test_missing_lists_everything(self) -> None:
        with TemporaryDirectory() as tmp:
            state = read_state(Path(tmp))
            draft, _ = from_args(state, mode=None, llm=None, platform=["backend"], plugin=None, name=None, option=None)
            gaps = " ".join(missing(draft, state))
            for flag in ("--llm", "--plugin", "--name backend="):
                self.assertIn(flag, gaps)

    def test_no_plugins_still_gets_env_values(self) -> None:
        with TemporaryDirectory() as tmp:
            plan = self._plan(Path(tmp), llm=["claude"], name=["backend=a1"], plugin=["none"])
            paths = {a.path for a in plan.actions}
            self.assertIn("backend/a1/.env.examples", paths)
            self.assertIn("tools/secrets/backend/a1/.env.local-dev", paths)
            tooling = [p for p in paths if p.startswith("tools/") and not p.startswith("tools/secrets/")]
            self.assertEqual(tooling, [])
            self.assertNotIn("Makefile", paths)

    def test_secrets_seed_only_for_new_services(self) -> None:
        from yjcli.core import executor

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            executor.apply(self._plan(root, llm=["claude"], name=["backend=a1"], plugin=["none"]), root)
            (root / "tools/secrets/backend/a1/.env.production").unlink()
            plan = self._plan(root, name=["backend=a2"])
            created = {a.path for a in plan.actions if a.kind == "create"}
            self.assertIn("tools/secrets/backend/a2/.env.production", created)
            self.assertNotIn("tools/secrets/backend/a1/.env.production", created)  # deleted on purpose

    def test_deployer_without_builder_is_an_error(self) -> None:
        with TemporaryDirectory() as tmp:
            state = read_state(Path(tmp))
            _, errors = from_args(state, mode=None, llm=["claude"], platform=None, plugin=["deployer"],
                                  name=["backend=a1"], option=None)
            self.assertTrue(any("builder" in e for e in errors), errors)

    def test_platform_scripts_render_proto_only_where_possible(self) -> None:
        with TemporaryDirectory() as tmp:
            plan = self._plan(Path(tmp), llm=["claude"], name=["backend-msa=u", "frontend=f"], plugin=["all"])
            files = {a.path: a.content.decode() for a in plan.actions if a.content is not None}
            for tool in ("runner", "builder", "deployer"):
                for p in ("backend-msa", "frontend"):
                    for ext in ("sh", "ps1"):
                        self.assertNotIn("{{", files[f"tools/{tool}/{p}/{tool}.{ext}"])
                self.assertIn("`u`", files[f"tools/{tool}/GUIDE.md"])
            self.assertIn("build_proto", files["tools/builder/backend-msa/builder.sh"])
            self.assertNotIn("build_proto", files["tools/builder/frontend/builder.sh"])
            self.assertIn("Invoke-BuildProto", files["tools/builder/backend-msa/builder.ps1"])
            self.assertIn("DEPLOY_TARGETS", files["Makefile"])
            self.assertIn('-match "^(.+)-deploy-(development|production)$"', files["make.ps1"])


class UpdateTests(unittest.TestCase):
    def _plan(self, root: Path, **args):
        return plan_for(root, **args)

    def test_skill_additions_are_appended(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            extra = root / ".yjcli/skills/yj-backend.md"
            extra.parent.mkdir(parents=True)
            extra.write_text("- local rule\n")
            plan = self._plan(root, llm=["claude"], name=["backend=a1"], plugin=["none"])
            skill = next(a for a in plan.actions if a.path == ".claude/skills/yj-backend/SKILL.md")
            self.assertTrue(skill.content.decode().endswith("- local rule\n"))
            core = next(a for a in plan.actions if a.path == ".claude/skills/yj-arch-core/SKILL.md")
            self.assertNotIn(b"Project-specific additions", core.content)

    def test_agents_md_has_rules_block(self) -> None:
        with TemporaryDirectory() as tmp:
            plan = self._plan(Path(tmp), llm=["claude"], name=["backend=a1"], plugin=["none"])
            agents = next(a for a in plan.actions if a.path == "AGENTS.md").content.decode()
            for name in ("rules", "skills", "layout"):
                self.assertIn(f"<!-- yjcli:{name} -->", agents)
            self.assertIn("### Output & docs", agents)

    def test_version_guard_comparison(self) -> None:
        self.assertTrue(is_older("0.3.0", "0.4.0"))
        self.assertTrue(is_older("0.3.0", "0.3.1rc1"))
        self.assertFalse(is_older("0.4.0", "0.3.0"))
        self.assertFalse(is_older("0.3.0", "0.3"))
        self.assertFalse(is_older("0.0.0+local", "1.0.0"))  # unknown dev build never blocks


class ManifestTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        m = Manifest(
            yjcli_version="1.0",
            llms=["claude"],
            plugins=["secrets"],
            platforms={"backend": ["a1", "a2"]},
            files={'a "b".md': FileRecord("seed", "x", "y")},
        )
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / ".yjcli" / "manifest.toml"
            path.parent.mkdir()
            path.write_text(dumps(m))
            self.assertEqual(load(Path(tmp)), m)


if __name__ == "__main__":
    unittest.main()

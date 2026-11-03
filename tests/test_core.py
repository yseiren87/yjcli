from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from yjcli.catalog import data_root
from yjcli.catalog.platforms import PLATFORMS
from yjcli.catalog.plugins import PLUGINS, drop_dependents, resolve_requires
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
    def test_requires_are_added(self) -> None:
        self.assertEqual(resolve_requires(["runner"]), (["runner", "secrets"], ["secrets"]))
        self.assertEqual(resolve_requires(["builder"])[0], ["secrets", "builder"])

    def test_dropping_a_requirement_drops_dependents(self) -> None:
        kept, dropped = drop_dependents(["runner", "builder"])
        self.assertEqual(kept, [])
        self.assertCountEqual(dropped, ["runner", "builder"])


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

    def test_code_only_plan_has_no_tooling(self) -> None:
        with TemporaryDirectory() as tmp:
            plan = self._plan(Path(tmp), llm=["claude"], name=["backend=a1"], plugin=["none"])
            paths = {a.path for a in plan.actions}
            self.assertIn("backend/a1/.env.examples", paths)
            self.assertFalse(any(p.startswith("tools/") or p == "Makefile" for p in paths))

    def test_plugin_seed_only_for_new_owners(self) -> None:
        from yjcli.core import executor

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            executor.apply(self._plan(root, llm=["claude"], name=["backend=a1"], plugin=["builder"]), root)
            (root / "backend/a1/Dockerfile").unlink()
            plan = self._plan(root, name=["backend=a2"])
            created = {a.path for a in plan.actions if a.kind == "create"}
            self.assertIn("backend/a2/Dockerfile", created)
            self.assertNotIn("backend/a1/Dockerfile", created)  # deleted on purpose = opted out


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

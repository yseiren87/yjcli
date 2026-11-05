"""Template language, catalog, selection parsing/resolving, manifest and versions."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from yjcli import template as t
from yjcli.catalog import DATA, PLATFORMS, PLUGINS, SKILLS, drop_dependents, plugins_lacking, routes_for, skills_for
from yjcli.repo import Manifest, Record, dump_manifest, is_older, load_manifest, read_repo, unsupported
from yjcli.selection import Request, check_units, fill_defaults, gaps, parse_assignments, parse_ids, resolve


class TemplateTests(unittest.TestCase):
    def test_values_conditions_and_standalone_lines(self) -> None:
        text = "a {{x}}\n{{#if on}}\nyes\n{{else}}\nno\n{{/if}}\nend {{#if off}}hidden{{/if}}\n"
        self.assertEqual(t.render(text, {"x": 1, "on": True, "off": False}), "a 1\nyes\nend \n")
        self.assertEqual(t.render(text, {"x": 1, "on": False, "off": False}), "a 1\nno\nend \n")

    def test_nested_and_include(self) -> None:
        with TemporaryDirectory() as tmp:
            Path(tmp, "f.md").write_text("frag {{x}}\n")
            text = "{{#if a}}A{{#if b}}B{{/if}}{{/if}}\n{{include:f.md}}\nz\n"
            self.assertEqual(t.render(text, {"a": True, "b": False, "x": 2}, Path(tmp)), "A\nfrag 2\nz\n")

    def test_errors(self) -> None:
        for bad in ("{{nope}}", "{{#if a}}x", "{{/if}}", "{{else}}"):
            with self.assertRaises(t.TemplateError, msg=bad):
                t.render(bad, {"a": True})

    def test_blocks(self) -> None:
        text = "top\n" + t.block("s", "old") + "bottom\n"
        self.assertEqual(t.replace_block(text, "s", "new"), "top\n<!-- yjcli:s -->\nnew\n<!-- /yjcli:s -->\nbottom\n")
        self.assertIsNone(t.replace_block("nothing", "s", "x"))
        self.assertIn("# >>> yjcli:managed\nx\n# <<< yjcli:managed", t.block("managed", "x", "hash"))
        self.assertEqual(t.strip_blocks(text).count("\n"), text.count("\n"))

    def test_substitute_only_named_tokens(self) -> None:
        self.assertEqual(t.substitute("__NAME__ __PORT__ __APP_NAME__", {"__NAME__": "a", "__PORT__": "1"}),
                         "a 1 __APP_NAME__")


class CatalogTests(unittest.TestCase):
    def test_every_skill_and_fragment_exists(self) -> None:
        for s in SKILLS:
            self.assertTrue((DATA / "skills" / s.id / "SKILL.md").is_file(), s.id)
        for p in PLATFORMS:
            for s in p.skills:
                self.assertIn(s, [x.id for x in SKILLS])
        for plugin in PLUGINS:
            self.assertTrue((DATA / "skills" / "_shared" / f"plugin-{plugin.id}.md").is_file(), plugin.id)
            for f in plugin.files:
                self.assertTrue((DATA / "plugins" / f.template).is_file(), f.template)

    def test_routes(self) -> None:
        rows = routes_for(["browser-extension"])
        self.assertIn("native_*", rows[0][0])
        self.assertEqual(skills_for(["frontend"]), ["yj-arch-core", "yj-frontend"])

    def test_plugin_requirements(self) -> None:
        self.assertEqual(plugins_lacking(["deployer"]), {"deployer": ["builder"]})
        self.assertEqual(drop_dependents(["runner", "deployer"]), (["runner"], ["deployer"]))

    def test_powershell_templates_are_ascii(self) -> None:
        # Windows PowerShell 5.1 reads BOM-less .ps1 as ANSI: non-ASCII bytes break parsing.
        for f in (DATA / "plugins").rglob("*.ps1"):
            self.assertTrue(f.read_bytes().isascii(), f.name)


class SelectionTests(unittest.TestCase):
    def test_parsing(self) -> None:
        errors: list[str] = []
        self.assertEqual(parse_ids(["claude,cursor"], ["cursor", "claude", "codex"], "LLM", errors), ["cursor", "claude"])
        self.assertEqual(parse_ids(["all"], ["a", "b"], "x", errors), ["a", "b"])
        self.assertEqual(parse_ids(["none"], ["a"], "x", errors), [])
        self.assertIsNone(parse_ids(None, ["a"], "x", errors))
        self.assertEqual(errors, [])
        parse_ids(["gpt"], ["a"], "LLM", errors)
        self.assertEqual(len(errors), 1)
        errors = []
        self.assertEqual(parse_assignments(["backend=a1", "backend=a2"], "--name", errors), {"backend": "a1 a2"})
        parse_assignments(["proto=go", "nope=x", "bad"], "--name", errors)
        self.assertEqual(len(errors), 3)

    def test_unit_names(self) -> None:
        names, errors, notes = check_units("backend", "a1, a1 -bad a2", existing=["a2"])
        self.assertEqual((names, len(errors), len(notes)), (["a1"], 1, 1))
        names, errors, _ = check_units("proto", "go rust", existing=[])
        self.assertEqual((names, len(errors)), (["go"], 1))

    def test_new_repository_needs_everything(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = read_repo(Path(tmp))
            req = Request(platforms=["backend-msa"])
            fill_defaults(req, repo)
            self.assertIn("proto", req.platforms)
            self.assertIn("backend-msa 는 proto 가 필요해 함께 선택했습니다", req.notes)
            missing = " ".join(gaps(req, repo))
            for flag in ("--llm", "--plugin", "--name backend-msa=", "--proto-lang"):
                self.assertIn(flag, missing)

    def test_resolve_rules(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = read_repo(Path(tmp))
            _, errors = resolve(Request(llms=[], platforms=["backend"], plugins=["deployer"]), repo)
            joined = " ".join(errors)
            for part in ("LLM", "builder", "backend: 새 플랫폼"):
                self.assertIn(part, joined)
            cfg, errors = resolve(Request(llms=["claude"], platforms=["backend"], plugins=[], add={"backend": ["a"]}), repo)
            self.assertEqual(errors, [])
            self.assertEqual((cfg.units, cfg.secrets), ({"backend": ["a"]}, ["backend"]))


class ManifestTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        m = Manifest("1.0", ["claude"], ["runner"], {"backend": ["a1"], "frontend": ["f"], "proto": ["go"]}, ["frontend"],
                     {'a "b".md': Record("seed", "x", "y"), "m": Record("managed", "z")})
        with TemporaryDirectory() as tmp:
            Path(tmp, ".yjcli").mkdir()
            Path(tmp, ".yjcli/manifest.toml").write_text(dump_manifest(m))
            self.assertEqual(load_manifest(Path(tmp)), m)
            self.assertIn('languages = ["go"]', dump_manifest(m))

    def test_old_left_over_records_are_dropped(self) -> None:
        with TemporaryDirectory() as tmp:
            Path(tmp, ".yjcli").mkdir()
            Path(tmp, ".yjcli/manifest.toml").write_text(
                'schema = 1\nyjcli_version = "0.5.1"\nllms = ["claude"]\nplugins = []\n'
                '[files]\n"a" = { policy = "seed", sha256 = "x", orphan = true }\n"b" = { policy = "managed", sha256 = "y" }\n')
            self.assertEqual(list(load_manifest(Path(tmp)).files), ["b"])

    def test_versions(self) -> None:
        self.assertTrue(is_older("0.4.0", "0.5.0"))
        self.assertTrue(is_older("0.5.0", "0.5.1rc1"))
        self.assertFalse(is_older("0.5.0", "0.5"))
        self.assertFalse(is_older("0.0.0+local", "1.0.0"))
        self.assertTrue(unsupported("0.4.3"))
        self.assertFalse(unsupported("0.5.0"))
        self.assertFalse(unsupported("0.4.3", installed="0.4.3"))


if __name__ == "__main__":
    unittest.main()

"""Copy packaged Cursor/Claude skills & rules into a target repo."""

from __future__ import annotations

from pathlib import Path

import typer

from djcli.modules import paths
from djcli.modules.fsutil import copy_file, copy_tree, ensure_real_dir


def ensure_agent_wiring(root: Path, *, force: bool = False) -> None:
    """Install AGENTS/CLAUDE docs, skills, rules, and Claude settings."""
    templates = paths.templates_dir()
    agents_src = templates / "AGENTS.md"
    settings_src = templates / "settings.json"
    if not agents_src.is_file():
        raise FileNotFoundError(f"missing template: {agents_src}")
    if not settings_src.is_file():
        raise FileNotFoundError(f"missing template: {settings_src}")

    copy_file(agents_src, root / "AGENTS.md", force=force)
    copy_file(agents_src, root / "CLAUDE.md", force=force)

    cursor_skills = root / ".cursor" / "skills"
    claude_skills = root / ".claude" / "skills"
    cursor_rules = root / ".cursor" / "rules"
    claude_rules = root / ".claude" / "rules"
    ensure_real_dir(cursor_skills)
    ensure_real_dir(claude_skills)
    ensure_real_dir(cursor_rules)
    ensure_real_dir(claude_rules)

    skills_root = paths.skills_dir()
    if skills_root.is_dir():
        for skill_dir in sorted(p for p in skills_root.iterdir() if p.is_dir()):
            name = skill_dir.name
            copy_tree(skill_dir, cursor_skills / name, force=force)
            copy_tree(skill_dir, claude_skills / name, force=force)

    for rule_file in sorted(paths.cursor_rules_dir().glob("*")):
        if rule_file.is_file():
            copy_file(rule_file, cursor_rules / rule_file.name, force=force)

    for rule_file in sorted(paths.claude_rules_dir().glob("*")):
        if rule_file.is_file():
            copy_file(rule_file, claude_rules / rule_file.name, force=force)

    copy_file(settings_src, root / ".claude" / "settings.json", force=force)


def ensure_root_from_templates(root: Path, *, force: bool = False) -> None:
    """Copy root Makefile / .gitignore / make.bat from packaged templates."""
    templates = paths.templates_dir()
    for name in (".gitignore", "Makefile", "make.bat"):
        src = templates / name
        if not src.is_file():
            typer.echo(f"warn: missing template: {src}", err=True)
            continue
        copy_file(src, root / name, force=force)

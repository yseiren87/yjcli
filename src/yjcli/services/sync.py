"""Sync agent docs / skills / rules / make scripts into a target repo."""

from __future__ import annotations

from pathlib import Path

import typer

from yjcli.modules import paths
from yjcli.modules.constants import PLATFORMS
from yjcli.modules.fsutil import copy_file, copy_tree, ensure_real_dir
from yjcli.modules.prompt import abort


def sync_agents(root: Path) -> None:
    """Overwrite CLAUDE.md from AGENTS.md (AGENTS.md is the source of truth)."""
    agents = root / "AGENTS.md"
    claude = root / "CLAUDE.md"
    if not agents.is_file():
        abort(f"missing {agents} (edit AGENTS.md first)")
    copy_file(agents, claude, force=True)
    typer.echo("synced: AGENTS.md -> CLAUDE.md")


def sync_skills(root: Path, *, force: bool = True) -> None:
    """Copy packaged skills into .cursor/skills and .claude/skills."""
    cursor_skills = root / ".cursor" / "skills"
    claude_skills = root / ".claude" / "skills"
    ensure_real_dir(cursor_skills)
    ensure_real_dir(claude_skills)

    skills_root = paths.skills_dir()
    if not skills_root.is_dir():
        abort(f"missing packaged skills: {skills_root}")

    for skill_dir in sorted(p for p in skills_root.iterdir() if p.is_dir()):
        name = skill_dir.name
        copy_tree(skill_dir, cursor_skills / name, force=force)
        copy_tree(skill_dir, claude_skills / name, force=force)
    typer.echo("synced: packaged skills -> .cursor/skills, .claude/skills")


def sync_rules(root: Path, *, force: bool = True) -> None:
    """Copy packaged rules into .cursor/rules and .claude/rules."""
    cursor_rules = root / ".cursor" / "rules"
    claude_rules = root / ".claude" / "rules"
    ensure_real_dir(cursor_rules)
    ensure_real_dir(claude_rules)

    cursor_src = paths.cursor_rules_dir()
    claude_src = paths.claude_rules_dir()
    if not cursor_src.is_dir() and not claude_src.is_dir():
        abort("missing packaged cursor/claude rules")

    for rule_file in sorted(cursor_src.glob("*")):
        if rule_file.is_file():
            copy_file(rule_file, cursor_rules / rule_file.name, force=force)

    for rule_file in sorted(claude_src.glob("*")):
        if rule_file.is_file():
            copy_file(rule_file, claude_rules / rule_file.name, force=force)
    typer.echo("synced: packaged rules -> .cursor/rules, .claude/rules")


def sync_make(root: Path, *, force: bool = True) -> None:
    """Overwrite root Makefile/make.bat and each installed platform's run scripts."""
    templates = paths.templates_dir()
    for name in ("Makefile", "make.bat"):
        src = templates / name
        if not src.is_file():
            abort(f"missing packaged template: {src}")
        copy_file(src, root / name, force=force)
    typer.echo("synced: packaged Makefile, make.bat -> repo root")

    run_sh = templates / "platform" / "scripts" / "run.sh"
    run_bat = templates / "platform" / "scripts" / "run.bat"
    if not run_sh.is_file() or not run_bat.is_file():
        abort(f"missing packaged platform scripts under {run_sh.parent}")

    installed = [p for p in PLATFORMS if (root / p).is_dir()]
    if not installed:
        typer.echo("synced: platform run scripts (none installed)")
        return

    for platform in installed:
        scripts_dir = root / platform / "scripts"
        ensure_real_dir(scripts_dir)
        dest_sh = scripts_dir / "run.sh"
        dest_bat = scripts_dir / "run.bat"
        copy_file(run_sh, dest_sh, force=force)
        copy_file(run_bat, dest_bat, force=force)
        if dest_sh.is_file():
            dest_sh.chmod(dest_sh.stat().st_mode | 0o111)
        typer.echo(f"synced: {platform}/scripts/run.sh, run.bat")


def sync_all(root: Path, *, force: bool = True) -> None:
    """Sync AGENTS.md mirror, skills, rules, make files, and platform run scripts."""
    sync_agents(root)
    sync_skills(root, force=force)
    sync_rules(root, force=force)
    sync_make(root, force=force)

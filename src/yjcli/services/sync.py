"""Sync agent docs / skills / make scripts into a target repo."""

from __future__ import annotations

import shutil
from pathlib import Path

import typer

from yjcli.modules import paths
from yjcli.modules.constants import PLATFORMS
from yjcli.modules.fsutil import copy_file, copy_tree, ensure_real_dir
from yjcli.modules.prompt import abort

_SKILL_DEST_RELS = (
    Path(".cursor") / "skills",
    Path(".claude") / "skills",
    Path(".agents") / "skills",
)


def sync_agents(root: Path) -> None:
    """Overwrite CLAUDE.md from AGENTS.md (AGENTS.md is the source of truth)."""
    agents = root / "AGENTS.md"
    claude = root / "CLAUDE.md"
    if not agents.is_file():
        abort(f"missing {agents} (edit AGENTS.md first)")
    copy_file(agents, claude, force=True)
    typer.echo("synced: AGENTS.md -> CLAUDE.md")


def _remove_legacy_rules_dirs(root: Path) -> None:
    """Drop obsolete Cursor/Claude rules dirs (guidance lives in AGENTS.md)."""
    for rel in (Path(".cursor") / "rules", Path(".claude") / "rules"):
        target = root / rel
        if target.is_dir():
            shutil.rmtree(target)
            typer.echo(f"removed legacy: {rel}/")


def _remove_path(root: Path, rel: Path, *, label: str) -> None:
    target = root / rel
    if target.is_symlink() or target.is_file():
        target.unlink()
        typer.echo(f"removed {label}: {rel}")
    elif target.is_dir():
        shutil.rmtree(target)
        typer.echo(f"removed {label}: {rel}/")


def _wipe_skill_dirs(root: Path) -> None:
    """Delete skill destinations so stale skill folders cannot linger."""
    for rel in _SKILL_DEST_RELS:
        _remove_path(root, rel, label="skills dir")


def sync_skills(root: Path, *, force: bool = True) -> None:
    """Copy packaged skills into .cursor, .claude, and .agents (Codex) skills."""
    _remove_legacy_rules_dirs(root)

    destinations = tuple(root / rel for rel in _SKILL_DEST_RELS)
    for dest in destinations:
        ensure_real_dir(dest)

    skills_root = paths.skills_dir()
    if not skills_root.is_dir():
        abort(f"missing packaged skills: {skills_root}")

    for skill_dir in sorted(p for p in skills_root.iterdir() if p.is_dir()):
        name = skill_dir.name
        for dest in destinations:
            copy_tree(skill_dir, dest / name, force=force)
    typer.echo(
        "synced: packaged skills -> .cursor/skills, .claude/skills, .agents/skills"
    )


def sync_make(root: Path, *, force: bool = True) -> None:
    """Refresh managed make/run files and install missing deploy templates."""
    templates = paths.templates_dir()
    for name in ("Makefile", "make.bat"):
        src = templates / name
        if not src.is_file():
            abort(f"missing packaged template: {src}")
        copy_file(src, root / name, force=force)
    typer.echo("synced: packaged Makefile, make.bat -> repo root")

    scripts_src = templates / "platform" / "scripts"
    managed_names = ("run.sh", "run.bat", "run.ps1")
    owned_names = (
        "build-common.sh",
        "build-development.sh",
        "build-production.sh",
        "deploy-common.sh",
        "deploy-development.sh",
        "deploy-production.sh",
        "plugin-build-proto.sh",
        "plugin-build-ssr.sh",
        "plugin-build-docker.sh",
    )
    missing = [
        name
        for name in (*managed_names, *owned_names)
        if not (scripts_src / name).is_file()
    ]
    if missing:
        abort(f"missing packaged platform scripts under {scripts_src}: {', '.join(missing)}")

    installed = [p for p in PLATFORMS if (root / p).is_dir()]
    if not installed:
        typer.echo("synced: platform run scripts (none installed)")
        return

    for platform in installed:
        scripts_dir = root / platform / "scripts"
        ensure_real_dir(scripts_dir)
        for name in managed_names:
            copy_file(scripts_src / name, scripts_dir / name, force=force)
        for name in owned_names:
            copy_file(scripts_src / name, scripts_dir / name, skip_existing=True)
        executable_names = ("run.sh", *owned_names)
        for name in executable_names:
            target = scripts_dir / name
            if target.is_file():
                target.chmod(target.stat().st_mode | 0o111)
        typer.echo(f"synced: {platform}/scripts (run refreshed; build/deploy preserved)")


def sync_all(root: Path, *, force: bool = True) -> None:
    """Sync AGENTS.md mirror, skills, make files, and platform run scripts."""
    sync_agents(root)
    sync_skills(root, force=force)
    sync_make(root, force=force)


def sync_migrate(root: Path) -> None:
    """Force-replace agent wiring + root templates from the package (destructive).

    Unlike `sync all`, this overwrites `AGENTS.md` from the package template,
    wipes skill directories (drops stale skills), removes legacy rules / `.agent`,
    and refreshes Claude settings + TOOLS.md / .gitignore / make scripts.
    """
    typer.echo("== migrate: strip legacy ==")
    _remove_legacy_rules_dirs(root)
    _remove_path(root, Path(".agent"), label="legacy")
    _wipe_skill_dirs(root)

    templates = paths.templates_dir()
    agents_src = templates / "AGENTS.md"
    settings_src = templates / "settings.json"
    if not agents_src.is_file():
        abort(f"missing packaged template: {agents_src}")
    if not settings_src.is_file():
        abort(f"missing packaged template: {settings_src}")

    typer.echo("== migrate: AGENTS.md + CLAUDE.md ==")
    copy_file(agents_src, root / "AGENTS.md", force=True)
    sync_agents(root)

    typer.echo("== migrate: skills ==")
    sync_skills(root, force=True)

    typer.echo("== migrate: settings + root templates ==")
    copy_file(settings_src, root / ".claude" / "settings.json", force=True)
    for name in (".gitignore", "TOOLS.md"):
        src = templates / name
        if not src.is_file():
            typer.echo(f"warn: missing template: {src}", err=True)
            continue
        copy_file(src, root / name, force=True)

    typer.echo("== migrate: make ==")
    sync_make(root, force=True)
    typer.echo("migrate done.")

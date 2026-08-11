"""Copy packaged Cursor/Claude/Codex skills into a target repo."""

from __future__ import annotations

from pathlib import Path

import typer

from yjcli.modules import paths
from yjcli.modules.fsutil import copy_file
from yjcli.services import sync as sync_svc


def ensure_agent_wiring(root: Path, *, force: bool = False) -> None:
    """Install AGENTS docs, skills, and Claude settings; mirror CLAUDE.md."""
    templates = paths.templates_dir()
    agents_src = templates / "AGENTS.md"
    settings_src = templates / "settings.json"
    if not agents_src.is_file():
        raise FileNotFoundError(f"missing template: {agents_src}")
    if not settings_src.is_file():
        raise FileNotFoundError(f"missing template: {settings_src}")

    copy_file(agents_src, root / "AGENTS.md", force=force)
    # CLAUDE.md is always a mechanical mirror of AGENTS.md (never edited by hand).
    if (root / "AGENTS.md").is_file():
        sync_svc.sync_agents(root)

    sync_svc.sync_skills(root, force=force)
    copy_file(settings_src, root / ".claude" / "settings.json", force=force)


def ensure_root_from_templates(root: Path, *, force: bool = False) -> None:
    """Copy managed root templates and create the user-owned Diff.md once."""
    templates = paths.templates_dir()
    for name in (".gitignore", "Makefile", "make.bat", "TOOLS.md"):
        src = templates / name
        if not src.is_file():
            typer.echo(f"warn: missing template: {src}", err=True)
            continue
        copy_file(src, root / name, force=force)

    diff_src = templates / "Diff.md"
    if not diff_src.is_file():
        typer.echo(f"warn: missing template: {diff_src}", err=True)
    else:
        copy_file(diff_src, root / "Diff.md", skip_existing=True)

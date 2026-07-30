"""yjcli sync <what> — refresh agent docs / skills / make."""

from __future__ import annotations

from pathlib import Path

import typer

from yjcli.services import sync as sync_svc

app = typer.Typer(
    help=(
        "Sync AGENTS.md mirror, skills, Makefile, or force-migrate wiring "
        "from the package."
    ),
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.command("agents")
def sync_agents(
    path: Path = typer.Option(
        Path("."),
        "--path",
        help="Target repository root (default: cwd).",
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
) -> None:
    """Overwrite CLAUDE.md from AGENTS.md (edit AGENTS.md only)."""
    sync_svc.sync_agents(path)


@app.command("skills")
def sync_skills(
    path: Path = typer.Option(
        Path("."),
        "--path",
        help="Target repository root (default: cwd).",
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
) -> None:
    """Overwrite .cursor/.claude/.agents skills from the yjcli package."""
    sync_svc.sync_skills(path, force=True)


@app.command("make")
def sync_make(
    path: Path = typer.Option(
        Path("."),
        "--path",
        help="Target repository root (default: cwd).",
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
) -> None:
    """Overwrite root Makefile/make.bat and installed platforms' run.sh/run.bat."""
    sync_svc.sync_make(path, force=True)


@app.command("all")
def sync_all(
    path: Path = typer.Option(
        Path("."),
        "--path",
        help="Target repository root (default: cwd).",
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
) -> None:
    """Sync AGENTS.md → CLAUDE.md, skills, make files, and platform run scripts.

    Does not overwrite AGENTS.md from the package (use `sync migrate` for that).
    """
    sync_svc.sync_all(path, force=True)


@app.command("migrate")
def sync_migrate(
    path: Path = typer.Option(
        Path("."),
        "--path",
        help="Target repository root (default: cwd).",
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation (required when stdin is not a TTY).",
    ),
) -> None:
    """Force-replace agent wiring from the package (destructive upgrade).

    Overwrites AGENTS.md (template), CLAUDE.md, skills (wipes stale folders),
    Makefile/make.bat, platform run scripts, TOOLS.md, .gitignore,
    .claude/settings.json. Removes legacy .cursor/rules, .claude/rules, .agent.
    """
    sync_svc.sync_migrate(path, yes=yes)

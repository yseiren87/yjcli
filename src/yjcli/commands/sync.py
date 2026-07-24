"""yjcli sync <what> — refresh agent docs / skills / rules."""

from __future__ import annotations

from pathlib import Path

import typer

from yjcli.services import sync as sync_svc

app = typer.Typer(
    help="Sync AGENTS.md mirror, skills, or rules into the target repo.",
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
    """Overwrite .cursor/.claude skills from the yjcli package."""
    sync_svc.sync_skills(path, force=True)


@app.command("rules")
def sync_rules(
    path: Path = typer.Option(
        Path("."),
        "--path",
        help="Target repository root (default: cwd).",
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
) -> None:
    """Overwrite .cursor/.claude rules from the yjcli package."""
    sync_svc.sync_rules(path, force=True)


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
    """Sync AGENTS.md → CLAUDE.md, skills, and rules together."""
    sync_svc.sync_all(path, force=True)

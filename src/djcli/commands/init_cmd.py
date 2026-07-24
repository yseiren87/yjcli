"""djcli init — bootstrap the current repo."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from djcli.modules.constants import PLATFORMS
from djcli.services import scaffold


def init_cmd(
    platform: Optional[list[str]] = typer.Option(
        None,
        "--platform",
        "-p",
        help="Platform to create (repeatable). Interactive if omitted.",
    ),
    all_platforms: bool = typer.Option(
        False,
        "--all",
        help="Create all known platforms.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing root/agent files without prompting.",
    ),
    path: Path = typer.Option(
        Path("."),
        "--path",
        help="Target repository root (default: cwd).",
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
) -> None:
    """Bootstrap root templates, agent wiring, and selected platforms."""
    if all_platforms and platform:
        typer.echo("error: use either --all or --platform, not both", err=True)
        raise typer.Exit(code=1)
    if platform:
        unknown = [p for p in platform if p not in PLATFORMS]
        if unknown:
            typer.echo(
                f"error: unknown platform(s): {', '.join(unknown)}",
                err=True,
            )
            typer.echo(f"known: {', '.join(PLATFORMS)}", err=True)
            raise typer.Exit(code=1)

    scaffold.bootstrap(
        path,
        platforms=platform,
        all_platforms=all_platforms,
        force=force,
        mode="init",
    )

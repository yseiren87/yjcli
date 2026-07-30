"""yjcli init — bootstrap the current repo."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from yjcli.modules.constants import PLATFORMS
from yjcli.services import scaffold


def init_cmd(
    type_: Optional[list[str]] = typer.Option(
        None,
        "--type",
        "-t",
        help=(
            "Platform type to create (repeatable). "
            f"One of: {', '.join(PLATFORMS)}. Interactive if omitted."
        ),
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
    if all_platforms and type_:
        typer.echo("error: use either --all or --type, not both", err=True)
        raise typer.Exit(code=1)
    if type_:
        unknown = [p for p in type_ if p not in PLATFORMS]
        if unknown:
            typer.echo(
                f"error: unknown platform type(s): {', '.join(unknown)}",
                err=True,
            )
            typer.echo(f"known: {', '.join(PLATFORMS)}", err=True)
            raise typer.Exit(code=1)

    scaffold.bootstrap(
        path,
        platforms=type_,

        all_platforms=all_platforms,
        force=force,
        mode="init",
    )

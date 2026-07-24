"""yjcli platform <verb> — manage platform roots."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from yjcli.modules.constants import PLATFORMS
from yjcli.services import scaffold

app = typer.Typer(
    help="Manage platform roots (no services).",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.command("add")
def platform_add(
    type_: Optional[list[str]] = typer.Option(
        None,
        "--type",
        "-t",
        help="Platform type to add (repeatable). Interactive if omitted.",
    ),
    all_platforms: bool = typer.Option(
        False,
        "--all",
        help="Add all missing platforms.",
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
    """Add platform roots only (no services, no skills/rules overwrite — use sync)."""
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
            raise typer.Exit(code=1)

    scaffold.bootstrap(
        path,
        platforms=type_,
        all_platforms=all_platforms,
        mode="add",
    )

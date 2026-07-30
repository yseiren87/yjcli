"""yjcli service <verb> — manage services under a platform."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from yjcli.modules.constants import PLATFORMS
from yjcli.services import scaffold

app = typer.Typer(
    help="Manage services/apps under an existing platform.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.command("add")
def service_add(
    platform: Optional[str] = typer.Option(
        None,
        "--platform",
        "-p",
        help=(
            "Existing platform type/root. "
            f"One of: {', '.join(PLATFORMS)}. Interactive if omitted."
        ),
    ),
    name: Optional[str] = typer.Option(
        None,
        "--name",
        "-n",
        help="Service/app name. Interactive if omitted.",
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
    """Add a service/app under an existing platform."""
    if platform and platform not in PLATFORMS:
        typer.echo(f"error: unknown platform: {platform}", err=True)
        typer.echo(f"known: {', '.join(PLATFORMS)}", err=True)
        raise typer.Exit(code=1)

    scaffold.add_service_flow(path, platform=platform, name=name)

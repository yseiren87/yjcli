"""djcli add <resource> — extend an existing repo."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from djcli.modules.constants import PLATFORMS
from djcli.services import scaffold

app = typer.Typer(help="Add a platform or service to the current repo.")


@app.command("platform")
def add_platform(
    platform: Optional[list[str]] = typer.Option(
        None,
        "--platform",
        "-p",
        help="Platform to add (repeatable). Interactive if omitted.",
    ),
    all_platforms: bool = typer.Option(
        False,
        "--all",
        help="Add all missing platforms.",
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
    """Add one or more platform roots from packaged templates."""
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
            raise typer.Exit(code=1)

    scaffold.bootstrap(
        path,
        platforms=platform,
        all_platforms=all_platforms,
        force=force,
        mode="add",
    )


@app.command("service")
def add_service(
    platform: Optional[str] = typer.Option(
        None,
        "--platform",
        "-p",
        help="Existing platform root. Interactive if omitted.",
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

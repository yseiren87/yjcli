"""Entry: register subcommands (Typer)."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Optional

import typer

from yjcli.commands import add
from yjcli.commands.init_cmd import init_cmd
from yjcli.services import status


def package_version() -> str:
    """Installed package version from pyproject metadata (single source)."""
    try:
        return version("yjcli")
    except PackageNotFoundError:
        return "0.0.0+local"


app = typer.Typer(
    name="yjcli",
    help="Scaffold YJ platforms/services and Cursor/Claude agent wiring.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(package_version())
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-V",
        help="Print version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """yjcli root options."""


app.command("init")(init_cmd)
app.add_typer(add.app, name="add")


@app.command("doctor")
def doctor() -> None:
    """Show packaged template/skill/rule counts."""
    assets = status.asset_summary()
    typer.echo("yjcli packaged data:")
    for key, n in assets.items():
        typer.echo(f"  {key}: {n} files")

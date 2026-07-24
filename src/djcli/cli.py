"""Entry: register subcommands (Typer)."""

from __future__ import annotations

from typing import Optional

import typer

from djcli import __version__
from djcli.commands import add
from djcli.commands.init_cmd import init_cmd
from djcli.services import status

app = typer.Typer(
    name="djcli",
    help="Scaffold DJ platforms/services and Cursor/Claude agent wiring.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
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
    """djcli root options."""


app.command("init")(init_cmd)
app.add_typer(add.app, name="add")


@app.command("doctor")
def doctor() -> None:
    """Show packaged template/skill/rule counts."""
    assets = status.asset_summary()
    typer.echo("djcli packaged data:")
    for key, n in assets.items():
        typer.echo(f"  {key}: {n} files")

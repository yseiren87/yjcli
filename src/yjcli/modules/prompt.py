"""Interactive selection helpers."""

from __future__ import annotations

import typer

from yjcli.modules.constants import PLATFORMS
from yjcli.modules.fsutil import is_interactive


def abort(message: str, code: int = 1) -> None:
    typer.echo(f"error: {message}", err=True)
    raise typer.Exit(code=code)


def select_platforms(*, mode: str, root_exists: set[str]) -> list[str]:
    """
    Prompt for one or more platforms.

    mode='init' — all platforms are candidates
    mode='add'  — only platforms that do not exist yet
    """
    candidates = [p for p in PLATFORMS if mode != "add" or p not in root_exists]
    if not candidates:
        abort("no platforms available to create")

    typer.echo("Select platform(s):", err=True)
    for i, name in enumerate(candidates, start=1):
        typer.echo(f"  {i}) {name}", err=True)
    typer.echo("  a) all listed", err=True)

    if not is_interactive():
        abort("non-interactive stdin; pass --platform / --all")

    line = typer.prompt("Enter numbers (e.g. 1 3) or a").strip()
    if line.lower() in {"a", "all"}:
        return list(candidates)

    selected: list[str] = []
    for token in line.split():
        if not token.isdigit():
            abort(f"invalid selection: {token}")
        idx = int(token) - 1
        if idx < 0 or idx >= len(candidates):
            abort(f"out of range: {token}")
        selected.append(candidates[idx])

    if not selected:
        abort("nothing selected")
    return selected


def select_existing_platform(existing: list[str]) -> str:
    if not existing:
        abort("no platforms exist yet; run: yjcli init")

    typer.echo("Select platform:", err=True)
    for i, name in enumerate(existing, start=1):
        typer.echo(f"  {i}) {name}", err=True)

    if not is_interactive():
        abort("non-interactive stdin; pass --platform")

    token = typer.prompt("Enter number").strip()
    if not token.isdigit():
        abort("invalid selection")
    idx = int(token) - 1
    if idx < 0 or idx >= len(existing):
        abort("out of range")
    return existing[idx]

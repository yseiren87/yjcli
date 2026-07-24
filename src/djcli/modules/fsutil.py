"""Filesystem helpers for scaffold copy/overwrite behavior."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import typer


def is_interactive() -> bool:
    return sys.stdin.isatty()


def ensure_real_dir(path: Path) -> None:
    """Ensure path is a real directory (replace a directory symlink if needed)."""
    if path.is_symlink():
        typer.echo(f"replacing directory symlink with real dir: {path}")
        path.unlink()
    path.mkdir(parents=True, exist_ok=True)


def _ask_overwrite(dest: Path, source_label: str) -> bool:
    if not is_interactive():
        typer.echo(f"skip (exists, non-interactive): {dest}")
        return False
    answer = typer.prompt(f"overwrite {dest} with {source_label}? [y/N]", default="N")
    return answer.strip().lower() in {"y", "yes"}


def copy_file(
    source: Path,
    dest: Path,
    *,
    replace: dict[str, str] | None = None,
    force: bool = False,
    skip_existing: bool = False,
) -> None:
    """Copy a single file, optionally substituting placeholders."""
    if not source.is_file():
        raise FileNotFoundError(f"missing template: {source}")

    if dest.is_symlink():
        dest.unlink()

    if dest.exists():
        if skip_existing:
            typer.echo(f"skip (exists): {dest}")
            return
        if not force and not _ask_overwrite(dest, str(source)):
            typer.echo(f"skip: {dest}")
            return

    dest.parent.mkdir(parents=True, exist_ok=True)
    if replace:
        text = source.read_text(encoding="utf-8")
        for old, new in replace.items():
            text = text.replace(old, new)
        dest.write_text(text, encoding="utf-8")
    else:
        shutil.copy2(source, dest)
    typer.echo(f"copied: {source.name} -> {dest}")


def copy_tree(
    source: Path,
    dest: Path,
    *,
    force: bool = False,
    skip_existing: bool = False,
) -> None:
    """Copy a directory tree (used for skill folders)."""
    if not source.is_dir():
        raise FileNotFoundError(f"missing template dir: {source}")

    if dest.is_symlink():
        dest.unlink()

    if dest.exists():
        if skip_existing:
            typer.echo(f"skip (exists): {dest}")
            return
        if not force and not _ask_overwrite(dest, str(source)):
            typer.echo(f"skip: {dest}")
            return
        if dest.is_dir():
            shutil.rmtree(dest)
        else:
            dest.unlink()

    shutil.copytree(source, dest)
    typer.echo(f"copied: {source.name} -> {dest}")


def write_if_missing(path: Path, content: str) -> None:
    if path.exists():
        typer.echo(f"skip (exists): {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    typer.echo(f"created: {path}")

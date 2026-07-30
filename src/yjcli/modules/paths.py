"""Resolve packaged data directories (templates, skills)."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path


def data_root() -> Path:
    return Path(str(files("yjcli.data")))


def templates_dir() -> Path:
    return data_root() / "templates"


def skills_dir() -> Path:
    return data_root() / "skills"

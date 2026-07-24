"""Resolve packaged data directories (templates, skills, rules)."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path


def data_root() -> Path:
    return Path(str(files("djcli.data")))


def templates_dir() -> Path:
    return data_root() / "templates"


def skills_dir() -> Path:
    return data_root() / "skills"


def cursor_rules_dir() -> Path:
    return data_root() / "cursor-rules"


def claude_rules_dir() -> Path:
    return data_root() / "claude-rules"

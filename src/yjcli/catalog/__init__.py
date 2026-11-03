"""Declarative catalog: LLM adapters, platforms, plugins, skills.

Everything the user can pick (and everything derived from a pick) is data here.
Planner logic reads the catalog; it never branches on a platform/plugin name.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path


def data_root() -> Path:
    return Path(str(files("yjcli.data")))

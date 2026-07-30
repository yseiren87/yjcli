"""Report packaged asset availability."""

from __future__ import annotations

from yjcli.modules import paths


def asset_summary() -> dict[str, int]:
    def count_files(root) -> int:
        p = root()
        if not p.is_dir():
            return 0
        return sum(1 for f in p.rglob("*") if f.is_file())

    return {
        "templates": count_files(paths.templates_dir),
        "skills": count_files(paths.skills_dir),
    }

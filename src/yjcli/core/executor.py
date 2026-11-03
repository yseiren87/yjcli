"""Apply a Plan to disk. The only module that writes files."""

from __future__ import annotations

import shutil
from pathlib import Path

from yjcli.core.manifest import MANIFEST_PATH
from yjcli.core.planner import Plan


class ApplyError(RuntimeError):
    def __init__(self, message: str, written: list[str]):
        super().__init__(message)
        self.written = written


def apply(plan: Plan, root: Path) -> list[str]:
    """Apply actions in order; the manifest is written last, only on success."""
    written: list[str] = []
    manifest_action = None
    deleted_parents: set[Path] = set()
    try:
        for action in plan.actions:
            if action.path == str(MANIFEST_PATH):
                manifest_action = action
                continue
            path = root / action.path
            if action.kind == "mkdir":
                path.mkdir(parents=True, exist_ok=True)
            elif action.kind in ("create", "overwrite", "merge"):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(action.content or b"")
                if action.executable:
                    path.chmod(path.stat().st_mode | 0o111)
            elif action.kind == "chmod":
                path.chmod(path.stat().st_mode | 0o111)
            elif action.kind == "delete":
                path.unlink(missing_ok=True)
                deleted_parents.add(path.parent)
            elif action.kind == "rmtree":
                shutil.rmtree(path, ignore_errors=True)
            else:
                raise ValueError(f"unknown action: {action.kind}")
            written.append(f"{action.kind} {action.path}")
        _prune_empty(deleted_parents, root)
        if manifest_action is not None:
            path = root / manifest_action.path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(manifest_action.content or b"")
    except OSError as exc:
        raise ApplyError(str(exc), written) from exc
    return written


def _prune_empty(dirs: set[Path], root: Path) -> None:
    """Remove directories emptied by deletes (e.g. a dropped skill folder)."""
    root = root.resolve()
    for start in sorted(dirs, key=lambda p: len(p.parts), reverse=True):
        current = start.resolve()
        while current != root and root in current.parents:
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent

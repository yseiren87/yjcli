"""Write a plan to disk — all or nothing.

Every change is recorded before it is made. Folders being removed are moved
aside under `.yjcli/` instead of deleted, and only dropped once the whole plan
(the manifest included) succeeded. Any failure replays the record backwards,
leaving the repository as it was.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from yjcli.plan import Plan
from yjcli.repo import MANIFEST


class ApplyError(RuntimeError):
    def __init__(self, message: str, unrestored: list[str]):
        super().__init__(message)
        self.unrestored = unrestored


class _Undo:
    def __init__(self, root: Path):
        self.root = root
        self.steps: list[tuple[str, Path, object]] = []
        self.parking: Path | None = None

    def before_write(self, path: Path) -> None:
        self._new_dirs(path.parent)
        saved = (path.read_bytes(), path.stat().st_mode) if path.is_file() else None
        self.steps.append(("file", path, saved))

    def before_mkdir(self, path: Path) -> None:
        self._new_dirs(path)

    def _new_dirs(self, path: Path) -> None:
        missing = []
        while path != self.root and not path.exists():
            missing.append(path)
            path = path.parent
        self.steps += [("dir", d, None) for d in reversed(missing)]

    def park(self, path: Path) -> None:
        """Move a folder (or file) aside; it is restored on failure, dropped on success."""
        if not path.exists():
            return
        if self.parking is None:
            home = self.root / ".yjcli"
            self.before_mkdir(home)
            home.mkdir(parents=True, exist_ok=True)
            self.parking = Path(tempfile.mkdtemp(prefix="removing-", dir=home))
        spot = self.parking / str(len(self.steps))
        shutil.move(str(path), str(spot))
        self.steps.append(("parked", path, spot))

    def rollback(self) -> list[str]:
        failed = []
        for kind, path, saved in reversed(self.steps):
            try:
                if kind == "file":
                    if saved is None:
                        if path.is_file():  # the write may have failed before creating it
                            path.unlink()
                    else:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(saved[0])
                        path.chmod(saved[1])
                elif kind == "dir":
                    if path.is_dir() and not any(path.iterdir()):
                        path.rmdir()
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(saved), str(path))
            except OSError:
                failed.append(path.relative_to(self.root).as_posix())
        self.finish()
        return failed

    def finish(self) -> None:
        if self.parking is not None:
            shutil.rmtree(self.parking, ignore_errors=True)
            self.parking = None


def apply(plan: Plan, root: Path) -> None:
    root = root.resolve()
    undo = _Undo(root)
    emptied: set[Path] = set()
    manifest = next((c for c in plan.changes if c.path == MANIFEST), None)
    try:
        for c in plan.changes:
            if c is manifest:
                continue
            path = root / c.path
            if c.kind == "mkdir":
                undo.before_mkdir(path)
                path.mkdir(parents=True, exist_ok=True)
            elif c.kind in ("create", "overwrite", "merge"):
                undo.before_write(path)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(c.content or b"")
                if c.executable:
                    path.chmod(path.stat().st_mode | 0o111)
            elif c.kind == "chmod":
                undo.before_write(path)
                path.chmod(path.stat().st_mode | 0o111)
            elif c.kind in ("delete", "rmtree"):
                undo.park(path)
                emptied.add(path.parent)
            else:
                raise ValueError(f"unknown change: {c.kind}")
        _prune(emptied, root)
        if manifest is not None:
            path = root / manifest.path
            undo.before_write(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(manifest.content or b"")
    except OSError as exc:
        raise ApplyError(str(exc), undo.rollback()) from exc
    undo.finish()


def _prune(dirs: set[Path], root: Path) -> None:
    """Remove folders left empty by removals (restoring a parked path recreates them)."""
    for start in sorted(dirs, key=lambda p: len(p.parts), reverse=True):
        path = start
        while path != root and root in path.parents:
            try:
                path.rmdir()
            except OSError:
                break
            path = path.parent

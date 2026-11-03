"""Read-only view of the target repository: manifest + services on disk."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from yjcli.catalog.platforms import NON_SERVICE_DIRS, PLATFORMS
from yjcli.core import manifest as manifest_mod
from yjcli.core.manifest import Manifest


@dataclass
class RepoState:
    root: Path
    manifest: Manifest | None
    services: dict[str, list[str]] = field(default_factory=dict)  # platform -> on disk

    @property
    def mode(self) -> str:
        return "update" if self.manifest else "new"

    def existing(self, platform: str) -> list[str]:
        return self.services.get(platform, [])


def list_services(platform_dir: Path) -> list[str]:
    if not platform_dir.is_dir():
        return []
    return sorted(
        d.name
        for d in platform_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".") and d.name not in NON_SERVICE_DIRS
    )


def read_state(root: Path) -> RepoState:
    services = {p.id: list_services(root / p.id) for p in PLATFORMS if (root / p.id).is_dir()}
    return RepoState(root=root, manifest=manifest_mod.load(root), services=services)

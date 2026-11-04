"""Read-only view of the target repository: manifest + services on disk."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from yjcli.catalog.platforms import LANGUAGE_BY_ID, PLATFORMS
from yjcli.core import manifest as manifest_mod
from yjcli.core.manifest import Manifest


@dataclass
class RepoState:
    root: Path
    manifest: Manifest | None
    # platform -> services on disk (for the contract platform: generated languages)
    services: dict[str, list[str]] = field(default_factory=dict)

    @property
    def mode(self) -> str:
        return "update" if self.manifest else "new"

    def existing(self, platform: str) -> list[str]:
        return self.services.get(platform, [])


def list_services(platform_dir: Path) -> list[str]:
    if not platform_dir.is_dir():
        return []
    return sorted(d.name for d in platform_dir.iterdir() if d.is_dir() and not d.name.startswith("."))


def list_languages(contract_dir: Path) -> list[str]:
    dist = contract_dir / "dist"
    if not dist.is_dir():
        return []
    return sorted(d.name for d in dist.iterdir() if d.is_dir() and d.name in LANGUAGE_BY_ID)


def read_state(root: Path) -> RepoState:
    services = {
        p.id: (list_languages if p.is_contract else list_services)(root / p.id)
        for p in PLATFORMS
        if (root / p.id).is_dir()
    }
    return RepoState(root=root, manifest=manifest_mod.load(root), services=services)

"""The target repository as yjcli sees it: `.yjcli/manifest.toml` plus units on disk."""

from __future__ import annotations

import hashlib
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from yjcli.catalog import LANGUAGE, PLATFORM, PLATFORMS

MANIFEST = ".yjcli/manifest.toml"
SCHEMA = 1
# Oldest manifest this yjcli updates; never above the installed version (an unreleased
# build whose version was not bumped yet still works on the repositories it writes).
MIN_SUPPORTED = "0.5.0"


@dataclass(frozen=True)
class Record:
    policy: str
    sha256: str  # content yjcli last wrote (or found, for a seed it adopted)
    template: str | None = None  # hash of the rendered template (seeds): detects template changes


@dataclass
class Manifest:
    version: str
    llms: list[str] = field(default_factory=list)
    plugins: list[str] = field(default_factory=list)
    units: dict[str, list[str]] = field(default_factory=dict)  # platform -> services / languages
    secrets_off: list[str] = field(default_factory=list)
    files: dict[str, Record] = field(default_factory=dict)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_manifest(root: Path) -> Manifest | None:
    path = root / MANIFEST
    if not path.is_file():
        return None
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        raise ValueError(f"{MANIFEST}: 지원하지 않는 schema {data.get('schema')!r}")
    platforms = data.get("platforms", {})
    return Manifest(
        version=data.get("yjcli_version", ""),
        llms=list(data.get("llms", [])),
        plugins=list(data.get("plugins", [])),
        units={p: list(v.get("languages" if PLATFORM.get(p) and PLATFORM[p].contract else "services", []))
               for p, v in platforms.items() if p in PLATFORM},
        secrets_off=[p for p, v in platforms.items() if v.get("secrets") is False],
        files={k: Record(v["policy"], v["sha256"], v.get("template"))
               for k, v in data.get("files", {}).items() if not v.get("orphan")},
    )


def _q(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _list(values) -> str:
    return "[" + ", ".join(_q(v) for v in values) + "]"


def dump_manifest(m: Manifest) -> str:
    lines = [
        "# Managed by yjcli — do not edit by hand.",
        f"schema = {SCHEMA}",
        f"yjcli_version = {_q(m.version)}",
        "",
        f"llms = {_list(m.llms)}",
        f"plugins = {_list(m.plugins)}",
    ]
    for p in [x.id for x in PLATFORMS if x.id in m.units]:
        key = "languages" if PLATFORM[p].contract else "services"
        lines += ["", f"[platforms.{_q(p)}]", f"{key} = {_list(m.units[p])}"]
        if p in m.secrets_off:
            lines.append("secrets = false")
    lines += ["", "[files]"]
    for path in sorted(m.files):
        r = m.files[path]
        fields = [f"policy = {_q(r.policy)}", f"sha256 = {_q(r.sha256)}"]
        if r.template:
            fields.append(f"template = {_q(r.template)}")
        lines.append(f"{_q(path)} = {{ {', '.join(fields)} }}")
    return "\n".join(lines) + "\n"


@dataclass
class Repo:
    root: Path
    manifest: Manifest | None
    units: dict[str, list[str]]  # platform -> services / languages found on disk

    @property
    def configured(self) -> bool:
        return self.manifest is not None

    def existing(self, platform: str) -> list[str]:
        return self.units.get(platform, [])

    def platforms(self) -> list[str]:
        """Platforms the repository has now: in the manifest or with units on disk."""
        stored = self.manifest.units if self.manifest else {}
        return [p.id for p in PLATFORMS if p.id in stored or self.units.get(p.id)]


def read_repo(root: Path) -> Repo:
    units: dict[str, list[str]] = {}
    for p in PLATFORMS:
        base = root / p.id
        if p.contract:
            dist = base / "dist"
            found = sorted(d.name for d in dist.iterdir() if d.is_dir() and d.name in LANGUAGE) if dist.is_dir() else []
        else:
            found = sorted(d.name for d in base.iterdir() if d.is_dir() and not d.name.startswith(".")) if base.is_dir() else []
        if found:
            units[p.id] = found
    return Repo(root, load_manifest(root), units)


# --------------------------------------------------------------------- versions


def version_key(version: str) -> tuple[int, ...]:
    """Numeric release part ("0.5.1rc1" -> (0, 5, 1)); trailing zeros dropped; unknown -> ()."""
    m = re.match(r"\d+(?:\.\d+)*", version or "")
    parts = [int(x) for x in m.group(0).split(".")] if m else []
    while parts and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def is_older(a: str, b: str) -> bool:
    """a < b, ignoring versions that cannot be read."""
    ka, kb = version_key(a), version_key(b)
    return bool(ka) and bool(kb) and ka < kb


def unsupported(recorded: str, installed: str | None = None) -> bool:
    minimum = MIN_SUPPORTED
    if installed and is_older(installed, MIN_SUPPORTED):
        minimum = installed
    return is_older(recorded, minimum)

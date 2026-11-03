"""`.yjcli/manifest.toml` — selection state + hashes of files yjcli wrote."""

from __future__ import annotations

import hashlib
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

MANIFEST_PATH = Path(".yjcli") / "manifest.toml"
SCHEMA = 1


@dataclass
class FileRecord:
    policy: str
    sha256: str  # content yjcli last wrote (or found, for adopted seeds)
    template: str | None = None  # sha256 of the rendered template (seed files)


@dataclass
class Manifest:
    yjcli_version: str
    llms: list[str] = field(default_factory=list)
    plugins: list[str] = field(default_factory=list)
    platforms: dict[str, list[str]] = field(default_factory=dict)  # platform -> services
    files: dict[str, FileRecord] = field(default_factory=dict)


def version_key(version: str) -> tuple[int, ...]:
    """Numeric release part of a version ("0.3.1rc1" -> (0, 3, 1)); unknown -> ()."""
    m = re.match(r"(\d+(?:\.\d+)*)", version or "")
    if not m:
        return ()
    parts = [int(x) for x in m.group(1).split(".")]
    while parts and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def is_older(installed: str, recorded: str) -> bool:
    """True when the installed yjcli is older than the one that wrote the manifest."""
    a, b = version_key(installed), version_key(recorded)
    return bool(a) and bool(b) and a < b


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(root: Path) -> Manifest | None:
    path = root / MANIFEST_PATH
    if not path.is_file():
        return None
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        raise ValueError(f"unsupported manifest schema in {path}: {data.get('schema')!r}")
    return Manifest(
        yjcli_version=data.get("yjcli_version", ""),
        llms=list(data.get("llms", [])),
        plugins=list(data.get("plugins", [])),
        platforms={k: list(v.get("services", [])) for k, v in data.get("platforms", {}).items()},
        files={
            k: FileRecord(policy=v["policy"], sha256=v["sha256"], template=v.get("template"))
            for k, v in data.get("files", {}).items()
        },
    )


def _q(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _list(values: list[str]) -> str:
    return "[" + ", ".join(_q(v) for v in values) + "]"


def dumps(manifest: Manifest) -> str:
    lines = [
        "# Managed by yjcli — do not edit by hand.",
        "# Skills and platform options are derived (platforms / disk state), not stored.",
        f"schema = {SCHEMA}",
        f"yjcli_version = {_q(manifest.yjcli_version)}",
        "",
        f"llms = {_list(manifest.llms)}",
        f"plugins = {_list(manifest.plugins)}",
    ]
    for platform, services in manifest.platforms.items():
        lines += ["", f"[platforms.{_q(platform)}]", f"services = {_list(services)}"]
    lines += ["", "[files]"]
    for path in sorted(manifest.files):
        rec = manifest.files[path]
        fields = [f"policy = {_q(rec.policy)}", f"sha256 = {_q(rec.sha256)}"]
        if rec.template:
            fields.append(f"template = {_q(rec.template)}")
        lines.append(f"{_q(path)} = {{ {', '.join(fields)} }}")
    return "\n".join(lines) + "\n"

"""Find user-written references to yjcli paths that are not set up (any more).

yjcli regenerates only its own blocks, so text the project wrote outside them
(AGENTS.md notes, CLAUDE.md, .yjcli/skills/*.md) can keep pointing at a removed
plugin, LLM, platform or service. This only reports them; it never edits.
"""

from __future__ import annotations

import re
from pathlib import Path

from yjcli.catalog.llms import LLMS
from yjcli.catalog.platforms import PLATFORMS
from yjcli.catalog.plugins import PLUGINS

_BLOCK = re.compile(r"<!-- yjcli:(\w+) -->.*?<!-- /yjcli:\1 -->", re.S)
_PATH_START = r"(?<![\w./-])"  # not inside another path or word
MAX_REPORTED = 20


def _patterns(llms: list[str], plugins: list[str], platforms: list[str],
              removed_services: dict[str, list[str]]) -> list[tuple[re.Pattern, str]]:
    out: list[tuple[str, str]] = []
    for p in PLUGINS:
        if p.id not in plugins:
            out.append((_PATH_START + rf"tools/{p.id}\b", f"{p.id} 플러그인이 설치되어 있지 않음"))
    if "builder" not in plugins:
        out.append((r"\b[\w-]+-build-(?:development|production)\b", "builder 플러그인이 설치되어 있지 않음"))
    if "deployer" not in plugins:
        out.append((r"\b[\w-]+-deploy-(?:development|production)\b", "deployer 플러그인이 설치되어 있지 않음"))
    if "runner" not in plugins and platforms:
        names = "|".join(re.escape(p) for p in platforms)
        out.append((rf"\bmake (?:{names})(?![\w-])", "runner 플러그인이 설치되어 있지 않음"))
    for llm in LLMS:
        if llm.id not in llms:
            out.append((_PATH_START + re.escape(llm.skills_dir), f"{llm.label} 이(가) 선택되어 있지 않음"))
    for p in PLATFORMS:
        if p.id not in platforms:
            out.append((_PATH_START + re.escape(p.id) + "/", f"플랫폼 {p.id} 이(가) 구성되어 있지 않음"))
    for pid, names in removed_services.items():
        for s in names:
            out.append((_PATH_START + re.escape(f"{pid}/{s}") + r"(?![\w-])", f"서비스 {pid}/{s} 이(가) 없어짐"))
    return [(re.compile(rx), why) for rx, why in out]


def _sources(root: Path, planned: dict[str, str | None]) -> list[tuple[str, str]]:
    """(relative path, text with yjcli blocks blanked out but line numbers kept).

    `planned` holds contents a plan is about to write (None = about to be
    deleted), so line numbers match the files as they will be after the run.
    """
    files = [root / "AGENTS.md", root / "CLAUDE.md", *sorted((root / ".yjcli" / "skills").glob("*.md"))]
    out = []
    for f in files:
        rel = f.relative_to(root).as_posix()
        if rel in planned:
            if planned[rel] is None:
                continue
            text = planned[rel]
        elif f.is_file():
            text = f.read_text(encoding="utf-8", errors="replace")
        else:
            continue
        out.append((rel, _BLOCK.sub(lambda m: "\n" * m.group(0).count("\n"), text)))
    return out


def stale_references(root: Path, *, llms: list[str], plugins: list[str], platforms: list[str],
                     removed_services: dict[str, list[str]] | None = None,
                     planned: dict[str, str | None] | None = None) -> list[str]:
    patterns = _patterns(llms, plugins, platforms, removed_services or {})
    found: list[str] = []
    for rel, text in _sources(root, planned or {}):
        for number, line in enumerate(text.splitlines(), 1):
            for rx, why in patterns:
                m = rx.search(line)
                if m:
                    found.append(f"! {rel}:{number} — `{m.group(0)}` ({why})")
                    break
    if len(found) > MAX_REPORTED:
        found = found[:MAX_REPORTED] + [f"  … 외 {len(found) - MAX_REPORTED}곳"]
    return found

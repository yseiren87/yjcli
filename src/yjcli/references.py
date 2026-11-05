"""Text the project wrote that still points at things that are not set up.

yjcli rewrites only its own blocks, so notes outside them — AGENTS.md, CLAUDE.md,
`.yjcli/skills/*.md` — can keep naming a removed plugin, LLM, platform or service.
These are reported with file and line; never edited.
"""

from __future__ import annotations

import re
from pathlib import Path

from yjcli.catalog import LLMS, PLATFORMS, PLUGINS
from yjcli.template import strip_blocks

LIMIT = 20
_START = r"(?<![\w./-])"  # not in the middle of another path or word


def _patterns(llms, plugins, platforms, gone: dict[str, list[str]]) -> list[tuple[re.Pattern, str]]:
    rules: list[tuple[str, str]] = []
    rules += [(_START + rf"tools/{p.id}\b", f"{p.id} 플러그인이 없음") for p in PLUGINS if p.id not in plugins]
    if "builder" not in plugins:
        rules.append((r"\b[\w-]+-build-(?:development|production)\b", "builder 플러그인이 없음"))
    if "deployer" not in plugins:
        rules.append((r"\b[\w-]+-deploy-(?:development|production)\b", "deployer 플러그인이 없음"))
    if "runner" not in plugins and platforms:
        rules.append((rf"\bmake (?:{'|'.join(map(re.escape, platforms))})(?![\w-])", "runner 플러그인이 없음"))
    rules += [(_START + re.escape(l.skills_dir), f"{l.label} 이(가) 선택되어 있지 않음") for l in LLMS if l.id not in llms]
    rules += [(_START + re.escape(p.id) + "/", f"플랫폼 {p.id} 이(가) 없음") for p in PLATFORMS if p.id not in platforms]
    rules += [(_START + re.escape(f"{p}/{u}") + r"(?![\w-])", f"{p}/{u} 이(가) 없어짐")
              for p, units in gone.items() for u in units]
    return [(re.compile(rx), why) for rx, why in rules]


def stale_references(root: Path, llms, plugins, platforms, gone: dict[str, list[str]] | None = None,
                     upcoming: dict[str, str | None] | None = None) -> list[str]:
    """`upcoming`: contents a plan is about to write (None = about to be deleted), so lines match the result."""
    upcoming = upcoming or {}
    patterns = _patterns(llms, plugins, platforms, gone or {})
    sources = [root / "AGENTS.md", root / "CLAUDE.md", *sorted((root / ".yjcli" / "skills").glob("*.md"))]
    found: list[str] = []
    for f in sources:
        rel = f.relative_to(root).as_posix()
        text = upcoming[rel] if rel in upcoming else (f.read_text(encoding="utf-8") if f.is_file() else None)
        if text is None:
            continue
        for n, line in enumerate(strip_blocks(text).splitlines(), 1):
            for rx, why in patterns:
                if m := rx.search(line):
                    found.append(f"  {rel}:{n} — `{m.group(0)}` ({why})")
                    break
    if len(found) > LIMIT:
        found = found[:LIMIT] + [f"  … 외 {len(found) - LIMIT}건"]
    return found

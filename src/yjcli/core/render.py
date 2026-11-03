"""Tiny template renderer for skills, AGENTS.md, Makefile and make.bat.

Syntax (no external dependency):
  {{name}}                     variable from the context (unknown name -> error)
  {{include:file.md}}          fragment from data/skills/_shared (rendered too)
  {{#if flag}} … {{else}} … {{/if}}   truthy context value; may nest

A tag that is alone on its line removes the whole line, so block tags do not
leave blank lines behind. Code templates also use the legacy __NAME__ style
placeholders, handled by `substitute`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_TAG = re.compile(r"\{\{\s*([^}]*?)\s*\}\}")


class RenderError(ValueError):
    pass


def substitute(text: str, values: dict[str, str]) -> str:
    for old, new in values.items():
        text = text.replace(old, new)
    return text


def _strip_standalone(text: str) -> str:
    """Drop lines that hold only a block tag ({{#if}}, {{else}}, {{/if}})."""
    out: list[str] = []
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        m = _TAG.fullmatch(stripped)
        if m and (m.group(1).startswith(("#if ", "/if")) or m.group(1) == "else"):
            out.append(stripped)
            continue
        out.append(line)
    return "".join(out)


def render(text: str, context: dict[str, Any], *, shared_dir: Path | None = None) -> str:
    text = _strip_standalone(text)
    pos = 0
    out: list[str] = []
    # stack of (active_before_block, condition_value, in_else)
    stack: list[tuple[bool, bool, bool]] = []
    active = True
    for m in _TAG.finditer(text):
        if active:
            out.append(text[pos : m.start()])
        pos = m.end()
        tag = m.group(1)
        if tag.startswith("#if "):
            name = tag[4:].strip()
            value = bool(context.get(name)) if name in context else _missing(name)
            stack.append((active, value, False))
            active = active and value
        elif tag == "else":
            if not stack:
                raise RenderError("{{else}} without {{#if}}")
            parent, value, in_else = stack[-1]
            if in_else:
                raise RenderError("duplicate {{else}}")
            stack[-1] = (parent, value, True)
            active = parent and not value
        elif tag == "/if":
            if not stack:
                raise RenderError("{{/if}} without {{#if}}")
            active = stack.pop()[0]
        elif tag.startswith("include:"):
            if active:
                if shared_dir is None:
                    raise RenderError(f"include without shared dir: {tag}")
                path = shared_dir / tag[len("include:") :].strip()
                if not path.is_file():
                    raise RenderError(f"missing include: {path}")
                fragment = render(path.read_text(encoding="utf-8"), context, shared_dir=shared_dir)
                out.append(fragment.rstrip("\n"))
        else:
            if active:
                if tag not in context:
                    _missing(tag)
                out.append(str(context[tag]))
    if stack:
        raise RenderError("unclosed {{#if}}")
    if active:
        out.append(text[pos:])
    return "".join(out)


def _missing(name: str) -> bool:
    raise RenderError(f"unknown template variable: {name}")


def leftover_tags(text: str) -> list[str]:
    return [m.group(0) for m in _TAG.finditer(text)]


def markdown_table(header: tuple[str, str], rows: list[tuple[str, str]]) -> str:
    lines = [f"| {header[0]} | {header[1]} |", "|------|------|"]
    lines += [f"| {a} | {b} |" for a, b in rows]
    return "\n".join(lines)


def replace_block(text: str, name: str, body: str, *, style: str = "html") -> str | None:
    """Replace the content between yjcli block markers; None if markers are missing."""
    if style == "html":
        start, end = f"<!-- yjcli:{name} -->", f"<!-- /yjcli:{name} -->"
    else:  # hash comments (.gitignore)
        start, end = f"# >>> yjcli:{name}", f"# <<< yjcli:{name}"
    i = text.find(start)
    j = text.find(end, i + len(start)) if i >= 0 else -1
    if i < 0 or j < 0:
        return None
    return text[: i + len(start)] + "\n" + body.rstrip("\n") + "\n" + text[j:]


def hash_block(name: str, body: str) -> str:
    return f"# >>> yjcli:{name}\n{body.rstrip(chr(10))}\n# <<< yjcli:{name}\n"

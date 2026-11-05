"""The template language of data/ and the yjcli blocks inside user files.

    {{name}}                 value from the context (missing name = error)
    {{#if name}} … {{else}} … {{/if}}   nested conditions on context values
    {{include:file.md}}      fragment from the include folder, rendered with the same context

A line holding nothing but a block tag disappears with its line break, so
templates can put tags on their own lines without leaving blank lines.
"""

from __future__ import annotations

import re
from pathlib import Path

TAG = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
_ALONE = re.compile(r"^[ \t]*(\{\{\s*(?:#if [^{}]+|else|/if|include:[^{}]+)\s*\}\})[ \t]*\n", re.M)


class TemplateError(ValueError):
    pass


def render(text: str, ctx: dict, include_dir: Path | None = None) -> str:
    text = _ALONE.sub(lambda m: m.group(1) + ("\n" if "include:" in m.group(1) else ""), text)
    out: list[str] = []
    stack: list[tuple[bool, bool]] = []  # (parent emitting, condition)
    emitting = True
    pos = 0
    for m in TAG.finditer(text):
        if emitting:
            out.append(text[pos:m.start()])
        pos = m.end()
        tag = m.group(1)
        if tag.startswith("#if "):
            value = bool(_value(ctx, tag[4:].strip()))
            stack.append((emitting, value))
            emitting = emitting and value
        elif tag == "else":
            if not stack:
                raise TemplateError("{{else}} without {{#if}}")
            parent, value = stack[-1]
            emitting = parent and not value
        elif tag == "/if":
            if not stack:
                raise TemplateError("{{/if}} without {{#if}}")
            emitting = stack.pop()[0]
        elif tag.startswith("include:"):
            if emitting:
                if include_dir is None:
                    raise TemplateError(f"include without a folder: {tag}")
                path = include_dir / tag[len("include:"):].strip()
                if not path.is_file():
                    raise TemplateError(f"missing include: {path}")
                out.append(render(path.read_text(encoding="utf-8"), ctx, include_dir).rstrip("\n"))
        elif emitting:
            out.append(str(_value(ctx, tag)))
    if stack:
        raise TemplateError("{{#if}} without {{/if}}")
    if emitting:
        out.append(text[pos:])
    return "".join(out)


def _value(ctx: dict, name: str):
    if name not in ctx:
        raise TemplateError(f"unknown template value: {name}")
    return ctx[name]


def substitute(text: str, values: dict[str, str]) -> str:
    """Plain token replacement for stack files (`__NAME__`, `__PORT__`)."""
    for token, value in values.items():
        text = text.replace(token, value)
    return text


def markers(name: str, style: str) -> tuple[str, str]:
    if style == "html":
        return f"<!-- yjcli:{name} -->", f"<!-- /yjcli:{name} -->"
    return f"# >>> yjcli:{name}", f"# <<< yjcli:{name}"


def block(name: str, body: str, style: str = "html") -> str:
    start, end = markers(name, style)
    return f"{start}\n{body.rstrip(chr(10))}\n{end}\n"


def replace_block(text: str, name: str, body: str, style: str = "html") -> str | None:
    """Text with the block body replaced, or None when its markers are missing."""
    start, end = markers(name, style)
    i = text.find(start)
    j = text.find(end, i + len(start)) if i >= 0 else -1
    if i < 0 or j < 0:
        return None
    return text[:i + len(start)] + "\n" + body.rstrip("\n") + "\n" + text[j:]


def strip_blocks(text: str) -> str:
    """Blank out every yjcli html block but keep line numbers."""
    return re.sub(r"<!-- yjcli:(\w+) -->.*?<!-- /yjcli:\1 -->",
                  lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)


def table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)

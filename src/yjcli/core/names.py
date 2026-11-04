"""Service-name list parsing and validation (wizard input and --name share it)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from yjcli.catalog.platforms import RESERVED_SERVICE_NAMES

NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_-]*$")
_SPLIT_RE = re.compile(r"[\s,]+")


@dataclass
class ParsedNames:
    names: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def parse_names(raw: str, *, existing: set[str] | frozenset[str] = frozenset()) -> ParsedNames:
    """Split on whitespace and/or commas; validate each name.

    `existing` holds service names already on disk for the platform; naming one
    of them is a no-op with a note.
    """
    result = ParsedNames()
    seen: set[str] = set()
    for token in _SPLIT_RE.split(raw.strip()):
        if not token:
            continue
        if token in seen:
            result.notes.append(f"중복된 이름은 한 번만 사용합니다: {token}")
            continue
        seen.add(token)
        if not NAME_RE.match(token):
            result.errors.append(f"'{token}': 영문/숫자/_/- 만 사용할 수 있고 - 로 시작할 수 없습니다")
        elif token in RESERVED_SERVICE_NAMES:
            result.errors.append(f"'{token}': 예약된 이름입니다")
        elif token in existing:
            # Declarative: naming an existing service means "keep it", not an error.
            result.notes.append(f"{token}: 이미 있음 (변경 없음)")
        else:
            result.names.append(token)
    return result

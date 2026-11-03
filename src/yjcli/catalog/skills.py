"""Skills: rendered (not copied) into every selected LLM's skills directory."""

from __future__ import annotations

from dataclasses import dataclass

from yjcli.catalog.platforms import PLATFORM_BY_ID, PLATFORMS


@dataclass(frozen=True)
class Skill:
    id: str
    kind: str  # core | platform
    # (path pattern, note) rows for the routing table; note is "" or e.g. "(other)".
    routes: tuple[tuple[str, str], ...] = ()


SKILLS: tuple[Skill, ...] = (
    Skill("yj-arch-core", "core"),
    Skill("yj-backend", "platform", (("backend/**", ""), ("browser-extension/native_*/**", ""))),
    Skill("yj-backend-msa", "platform", (("backend-msa/**", ""),)),
    Skill("yj-backend-ssr", "platform", (("backend-ssr/**", ""),)),
    Skill("yj-frontend", "platform", (("frontend/**", ""),)),
    Skill("yj-mobile-app", "platform", (("mobile-app/**", ""),)),
    Skill("yj-pc-app", "platform", (("pc-app/**", ""),)),
    Skill("yj-cli", "platform", (("cli/**", ""),)),
    Skill("yj-browser-extension", "platform", (("browser-extension/**", "(other than `native_*`)"),)),
    Skill("yj-scheduler", "platform", (("scheduler/**", ""),)),
)

SKILL_BY_ID: dict[str, Skill] = {s.id: s for s in SKILLS}
CORE_SKILL = "yj-arch-core"


def skills_for(platforms: list[str]) -> list[str]:
    """Installed skills = core ∪ each selected platform's skills (catalog order)."""
    wanted = {CORE_SKILL}
    for pid in platforms:
        wanted.update(PLATFORM_BY_ID[pid].skills)
    return [s.id for s in SKILLS if s.id in wanted]


def routing_rows(platforms: list[str], skills: list[str]) -> list[tuple[str, str]]:
    """(path, skill) rows for selected platforms, in platform-catalog order.

    Within one platform, more specific patterns (e.g. `native_*`) come first so
    the first matching row is the right skill.
    """
    rows: list[tuple[str, str]] = []
    selected = set(platforms)
    for platform in PLATFORMS:
        if platform.id not in selected:
            continue
        platform_rows = [
            (pattern, note, skill_id)
            for skill_id in skills
            for pattern, note in SKILL_BY_ID[skill_id].routes
            if pattern.split("/", 1)[0] == platform.id
        ]
        platform_rows.sort(key=lambda r: "*" not in r[0].removesuffix("/**").split("/", 1)[-1])
        for pattern, note, skill_id in platform_rows:
            path = f"`{pattern}`" + (f" {note}" if note else "")
            rows.append((path, f"`{skill_id}`"))
    return rows

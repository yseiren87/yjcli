"""From what the user asked for to the configuration the repository should have.

A `Request` collects answers from arguments and the wizard (any may be missing).
`resolve()` turns it into a complete target `Config` — LLMs, plugins, every
platform's units (services, or languages for proto) and the secrets option —
or returns every rule it breaks at once.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from yjcli.catalog import (
    LANGUAGE, LLM, PLATFORM, PLATFORMS, PLUGIN, SERVICE_PLATFORMS, catalog_order, plugins_lacking, with_required,
)
from yjcli.repo import Repo

NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_-]*$")


@dataclass
class Request:
    llms: list[str] | None = None
    platforms: list[str] | None = None
    plugins: list[str] | None = None
    add: dict[str, list[str]] = field(default_factory=dict)  # platform -> units to add
    remove: dict[str, list[str]] = field(default_factory=dict)  # platform -> units to remove
    secrets: dict[str, bool] = field(default_factory=dict)  # chosen now; others keep the stored value
    answered: set[str] = field(default_factory=set)  # steps given as arguments: llms, platforms, plugins, secrets, units:<p>
    code_removal_ok: bool = False  # set by remove commands and the wizard's confirmation
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Config:
    llms: list[str]
    plugins: list[str]
    units: dict[str, list[str]]  # selected platform -> units, catalog order
    secrets: list[str]  # platforms whose services get tools/secrets/

    @property
    def platforms(self) -> list[str]:
        return list(self.units)


# ---------------------------------------------------------------------- parsing


def split(values) -> list[str] | None:
    if values is None:
        return None
    return [v for value in values for v in re.split(r"[\s,]+", value.strip()) if v]


def parse_ids(values, known, what: str, errors: list[str]) -> list[str] | None:
    """`all` / `none` / ids -> ids in catalog order; None when not given."""
    items = split(values)
    if items is None:
        return None
    if items == ["all"]:
        return list(known)
    if items == ["none"]:
        return []
    unknown = [v for v in items if v not in known]
    if unknown:
        errors.append(f"알 수 없는 {what}: {', '.join(unknown)} (사용 가능: {', '.join(known)})")
    return [k for k in known if k in items]


def parse_assignments(values, flag: str, errors: list[str]) -> dict[str, str]:
    """`<platform>=<names>` (repeatable) -> {platform: names}."""
    out: dict[str, str] = {}
    for item in values or []:
        if "=" not in item:
            errors.append(f"{flag} 형식은 <platform>=<이름들> 입니다: {item}")
            continue
        pid, names = (x.strip() for x in item.split("=", 1))
        if pid not in PLATFORM:
            errors.append(f"{flag}: 알 수 없는 플랫폼: {pid}")
        elif PLATFORM[pid].contract:
            errors.append(f"{flag} {pid}: proto 는 서비스가 아니라 언어를 고릅니다 — --proto-lang go,dart,python")
        else:
            out[pid] = f"{out.get(pid, '')} {names}".strip()
    return out


def check_units(pid: str, text: str, existing) -> tuple[list[str], list[str], list[str]]:
    """New unit names in `text` -> (names, errors, notes). Existing names are kept with a note."""
    names, errors, notes = [], [], []
    for token in dict.fromkeys(split([text]) or []):
        if PLATFORM[pid].contract and token not in LANGUAGE:
            errors.append(f"'{token}': 지원하지 않는 언어입니다 (사용 가능: {', '.join(LANGUAGE)})")
        elif not PLATFORM[pid].contract and not NAME.match(token):
            errors.append(f"'{token}': 영문/숫자/_/- 만 쓸 수 있고 - 로 시작할 수 없습니다")
        elif token in existing:
            notes.append(f"{pid}: {token}: 이미 있음 (변경 없음)")
        else:
            names.append(token)
    return names, errors, notes


def add_units(req: Request, repo: Repo, pid: str, text: str, errors: list[str], flag: str) -> None:
    names, errs, notes = check_units(pid, text, repo.existing(pid))
    errors += [f"{flag}: {e}" for e in errs]
    req.notes += notes
    if names:
        req.add[pid] = list(dict.fromkeys([*req.add.get(pid, []), *names]))


def remove_units(req: Request, repo: Repo, pid: str, text: str, errors: list[str], flag: str) -> None:
    unit = "언어" if PLATFORM[pid].contract else "서비스"
    for token in dict.fromkeys(split([text]) or []):
        if token not in repo.existing(pid):
            errors.append(f"{flag}: {pid} 에 없는 {unit}입니다: {token}")
        elif token not in req.remove.setdefault(pid, []):
            req.remove[pid].append(token)
    if not req.remove.get(pid):
        req.remove.pop(pid, None)


# --------------------------------------------------------------------- defaults


def stored_secrets(repo: Repo, pid: str) -> bool:
    m = repo.manifest
    return not PLATFORM[pid].contract and not (m and pid in m.units and pid in m.secrets_off)


def secrets_wanted(req: Request, repo: Repo, pid: str) -> bool:
    if PLATFORM[pid].contract:
        return False
    return req.secrets.get(pid, stored_secrets(repo, pid))


def stored_config(repo: Repo) -> Config | None:
    m = repo.manifest
    if not m:
        return None
    units = {p: repo.existing(p) or list(m.units.get(p, [])) for p in repo.platforms()}
    return Config(list(m.llms), list(m.plugins), units, [p for p in units if stored_secrets(repo, p)])


def fill_defaults(req: Request, repo: Repo) -> None:
    """Unanswered steps keep the stored configuration; required platforms come along."""
    m = repo.manifest
    if m:
        req.llms = list(m.llms) if req.llms is None else req.llms
        req.plugins = list(m.plugins) if req.plugins is None else req.plugins
        req.platforms = repo.platforms() if req.platforms is None else req.platforms
    if req.platforms is not None:
        req.platforms, added = with_required(req.platforms)
        for pid in added:
            users = [p for p in req.platforms if pid in PLATFORM[p].requires]
            req.notes.append(f"{', '.join(users)} 는 {pid} 가 필요해 함께 선택했습니다")


# ---------------------------------------------------------------------- resolve


def gaps(req: Request, repo: Repo) -> list[str]:
    """Answers still missing, phrased as the argument that would supply them."""
    out = []
    if req.llms is None:
        out.append("--llm (예: --llm claude,cursor)")
    if req.platforms is None:
        out.append("--platform 또는 --name (예: -n backend=a1,a2)")
    if req.plugins is None:
        out.append("--plugin (예: --plugin runner,builder · all · none)")
    have = set(repo.platforms())
    for pid in req.platforms or []:
        if pid not in have and not req.add.get(pid):
            if PLATFORM[pid].contract:
                out.append(f"--proto-lang <언어들> (예: --proto-lang go,dart · 사용 가능: {', '.join(LANGUAGE)})")
            else:
                out.append(f"--name {pid}=<이름들> (새 플랫폼은 서비스가 최소 1개 필요)")
    return out


def resolve(req: Request, repo: Repo) -> tuple[Config | None, list[str]]:
    errors: list[str] = []
    llms = catalog_order(req.llms or [], LLM)
    plugins = catalog_order(req.plugins or [], PLUGIN)
    chosen = catalog_order(req.platforms or [])
    if not llms:
        errors.append("LLM 대상은 최소 1개가 필요합니다")
    errors += [f"{p} 는 {', '.join(r)} 가 필요합니다" for p, r in plugins_lacking(plugins).items()]
    errors += [f"--name {p}: 선택하지 않은 플랫폼입니다" for p in req.add if p not in chosen]

    have = set(repo.platforms())
    units: dict[str, list[str]] = {}
    for pid in chosen:
        kept = [u for u in repo.existing(pid) if u not in req.remove.get(pid, [])]
        target = sorted({*kept, *req.add.get(pid, [])})
        if target:
            units[pid] = target
        elif pid not in have:
            what = "언어가" if PLATFORM[pid].contract else "서비스가"
            errors.append(f"{pid}: 새 플랫폼은 {what} 최소 1개 필요합니다")
        # an existing platform left without units is removed with its last unit
    for pid in units:
        for need in PLATFORM[pid].requires:
            if need not in units:
                errors.append(f"{pid} 가 {need} 를 사용하므로 {need} 를 비우거나 뺄 수 없습니다" if need in have
                              else f"{pid} 는 {need} 플랫폼이 필요합니다")
    if not units and not errors:
        errors.append("플랫폼은 최소 1개가 필요합니다")
    if errors:
        return None, list(dict.fromkeys(errors))
    return Config(llms, plugins, units, [p for p in units if secrets_wanted(req, repo, p)]), []


def service_platforms() -> list[str]:
    return list(SERVICE_PLATFORMS)


def all_platforms() -> list[str]:
    return [p.id for p in PLATFORMS]

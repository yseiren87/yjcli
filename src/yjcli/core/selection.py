"""Selection model: what the user picked, from CLI arguments and/or the wizard.

A `Draft` holds answers that may still be missing; the wizard fills the gaps
interactively, and `missing()` lists them for non-interactive runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from yjcli.catalog.llms import LLM_BY_ID, LLMS
from yjcli.catalog.platforms import LANGUAGE_BY_ID, PLATFORM_BY_ID, PLATFORMS, PROTO, with_required
from yjcli.catalog.plugins import PLUGIN_BY_ID, PLUGINS, missing_requires
from yjcli.core.names import parse_languages, parse_names
from yjcli.core.state import RepoState


@dataclass
class Draft:
    mode: str  # new | update
    llms: list[str] | None = None
    platforms: list[str] | None = None
    plugins: list[str] | None = None
    # platform -> new services (for the contract platform: new languages)
    names: dict[str, list[str]] = field(default_factory=dict)
    # Steps answered on the command line (the wizard skips them).
    given: set[str] = field(default_factory=set)
    # Also delete changed seeds whose owner is gone (env value files excepted).
    purge: bool = False
    notes: list[str] = field(default_factory=list)

    def new_platforms(self, state: RepoState) -> list[str]:
        known = set(state.manifest.platforms) if state.manifest else set()
        known |= {p for p, s in state.services.items() if s}
        return [p for p in (self.platforms or []) if p not in known]


def _split(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    out: list[str] = []
    for value in values:
        out += [v.strip() for v in value.split(",") if v.strip()]
    return out


def _pick(values: list[str] | None, known: list[str], kind: str, errors: list[str]) -> list[str] | None:
    items = _split(values)
    if items is None:
        return None
    if items == ["all"]:
        return list(known)
    if items == ["none"]:
        return []
    unknown = [v for v in items if v not in known]
    if unknown:
        errors.append(f"알 수 없는 {kind}: {', '.join(unknown)} (사용 가능: {', '.join(known)})")
    return [k for k in known if k in items]


def _split_assignment(raw: str, flag: str, errors: list[str]) -> tuple[str, str] | None:
    if "=" not in raw:
        errors.append(f"{flag} 형식은 <platform>=<값> 입니다: {raw}")
        return None
    key, value = raw.split("=", 1)
    key = key.strip()
    if key not in PLATFORM_BY_ID:
        errors.append(f"{flag}: 알 수 없는 플랫폼: {key}")
        return None
    return key, value


def from_args(
    state: RepoState,
    *,
    mode: str | None,
    llm: list[str] | None,
    platform: list[str] | None,
    plugin: list[str] | None,
    name: list[str] | None,
    proto_lang: list[str] | None = None,
) -> tuple[Draft, list[str]]:
    errors: list[str] = []
    draft = Draft(mode=mode or state.mode)
    if draft.mode == "new" and state.manifest:
        errors.append("이미 yjcli 로 구성된 저장소입니다 (.yjcli/manifest.toml). --mode update 로 실행하세요")
    if draft.mode == "update" and not state.manifest:
        errors.append(".yjcli/manifest.toml 이 없습니다. 신규 설치로 실행하세요 (--mode new)")

    draft.llms = _pick(llm, [l.id for l in LLMS], "LLM", errors)
    draft.platforms = _pick(platform, [p.id for p in PLATFORMS], "플랫폼", errors)
    draft.plugins = _pick(plugin, [p.id for p in PLUGINS], "플러그인", errors)
    if draft.plugins:
        errors += [f"{m} (--plugin 에 함께 지정하세요)" for m in missing_requires(draft.plugins)]

    for raw in name or []:
        parsed = _split_assignment(raw, "--name", errors)
        if not parsed:
            continue
        pid, value = parsed
        if PLATFORM_BY_ID[pid].is_contract:
            errors.append(f"--name {pid}: {pid} 는 서비스가 아니라 언어를 고릅니다 — --proto-lang go,dart,python")
            continue
        result = parse_names(value, existing=set(state.existing(pid)))
        errors += [f"--name {pid}: {e}" for e in result.errors]
        draft.notes += [f"{pid}: {n}" for n in result.notes]
        draft.names.setdefault(pid, [])
        draft.names[pid] += [n for n in result.names if n not in draft.names[pid]]
        draft.given.add(f"names:{pid}")

    if proto_lang is not None:
        result = parse_languages(" ".join(proto_lang), existing=set(state.existing(PROTO)))
        errors += [f"--proto-lang: {e}" for e in result.errors]
        draft.notes += [f"{PROTO}: {n}" for n in result.notes]
        draft.names[PROTO] = result.names
        draft.given.add(f"names:{PROTO}")

    # --name / --proto-lang imply their platform.
    if draft.names:
        base = draft.platforms
        if base is None and draft.mode == "update" and state.manifest:
            base = list(state.manifest.platforms)
        merged = set(base or []) | set(draft.names)
        draft.platforms = [p.id for p in PLATFORMS if p.id in merged]
        if platform is None:
            platform = []  # mark the step as given
    add_required_platforms(draft)

    if llm is not None:
        draft.given.add("llms")
    if platform is not None:
        draft.given.add("platforms")
    if plugin is not None:
        draft.given.add("plugins")
    return draft, errors


def fill_from_manifest(draft: Draft, state: RepoState) -> None:
    """Update mode: unanswered steps default to the stored selection."""
    if not state.manifest:
        return
    if draft.llms is None:
        draft.llms = list(state.manifest.llms)
    if draft.platforms is None:
        draft.platforms = list(state.manifest.platforms)
    if draft.plugins is None:
        draft.plugins = list(state.manifest.plugins)


def add_required_platforms(draft: Draft) -> None:
    """e.g. backend-msa brings the shared proto contract along."""
    if draft.platforms is None:
        return
    draft.platforms, added = with_required(draft.platforms)
    for pid in added:
        needers = [p for p in draft.platforms if pid in PLATFORM_BY_ID[p].requires]
        draft.notes.append(f"{', '.join(needers)} 는 {pid} 가 필요해 함께 선택했습니다")


def missing(draft: Draft, state: RepoState) -> list[str]:
    """Answers still needed, phrased as the CLI flag that would supply them."""
    out: list[str] = []
    if draft.llms is None:
        out.append("--llm (예: --llm claude,cursor)")
    elif not draft.llms:
        out.append("--llm: 최소 1개를 선택해야 합니다")
    if draft.platforms is None:
        out.append("--platform 또는 --name (예: -n backend=a1,a2)")
    elif not draft.platforms:
        out.append("--platform: 최소 1개를 선택해야 합니다")
    if draft.plugins is None:
        out.append("--plugin (예: --plugin runner,builder · --plugin all · --plugin none)")
    for pid in draft.new_platforms(state):
        if not draft.names.get(pid):
            if PLATFORM_BY_ID[pid].is_contract:
                out.append(f"--proto-lang <언어들> (예: --proto-lang go,dart · 사용 가능: {', '.join(LANGUAGE_BY_ID)})")
            else:
                out.append(f"--name {pid}=<이름들> (새 플랫폼은 서비스 이름이 최소 1개 필요)")
    return out


def validate(draft: Draft, state: RepoState) -> list[str]:
    """Rules that hold for both CLI and wizard answers."""
    errors: list[str] = []
    for pid in draft.names:
        if pid not in (draft.platforms or []):
            errors.append(f"--name {pid}: 선택하지 않은 플랫폼입니다")
    if state.manifest:
        for pid in state.manifest.platforms:
            if pid not in (draft.platforms or []) and state.existing(pid):
                errors.append(
                    f"{pid}: 서비스가 있는 플랫폼은 해제할 수 없습니다 ({', '.join(state.existing(pid))})"
                )
    for pid in draft.platforms or []:
        for req in PLATFORM_BY_ID[pid].requires:
            if req not in (draft.platforms or []):
                errors.append(f"{pid} 는 {req} 플랫폼이 필요합니다")
    errors += missing_requires([p for p in draft.plugins or [] if p in PLUGIN_BY_ID])
    unknown_llm = [l for l in draft.llms or [] if l not in LLM_BY_ID]
    if unknown_llm:
        errors.append(f"알 수 없는 LLM: {', '.join(unknown_llm)}")
    return errors

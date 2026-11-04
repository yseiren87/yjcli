"""Step-by-step wizard. Asks only what the command line left open.

Steps: 1 LLM → 2 platforms → 3 plugins → 4 service names (one screen per
platform; the proto contract asks for languages instead) → 5 summary + confirm.
← goes back one screen; nothing is written until the user confirms.
"""

from __future__ import annotations

from typing import Callable

from rich.console import Console

from yjcli.catalog.llms import LLMS
from yjcli.catalog.platforms import LANGUAGES, PLATFORM_BY_ID, PLATFORMS, with_required
from yjcli.catalog.plugins import PLUGINS, disabled_reasons, drop_dependents
from yjcli.core.names import parse_names
from yjcli.core.planner import Plan, is_env_value
from yjcli.core.selection import Draft, validate
from yjcli.core.state import RepoState
from yjcli.ui.prompts import BACK, Item, Prompter
from yjcli.ui.summary import print_summary

STEP_TITLES = ("LLM 대상", "플랫폼", "플러그인", "서비스 이름", "확인 및 실행")


class Cancelled(Exception):
    pass


def _header(console: Console, draft: Draft, state: RepoState, current: int, sub: str = "") -> None:
    mode = "신규 설치" if draft.mode == "new" else "업데이트"
    console.print()
    console.print(f"[bold]yjcli[/bold] · {state.root} · {mode}")
    values = (
        ", ".join(draft.llms or []),
        ", ".join(draft.platforms or []),
        ", ".join(draft.plugins or []) or ("없음" if draft.plugins is not None else ""),
        ", ".join(f"{p}/dist/{n}" if PLATFORM_BY_ID[p].is_contract else f"{p}/{n}"
                  for p, ns in draft.names.items() for n in ns),
        "",
    )
    keys = ("llms", "platforms", "plugins", None, None)
    for i, title in enumerate(STEP_TITLES):
        if i < current:
            mark = "✔"
        elif i == current:
            mark = "▸"
        else:
            mark = "○"
        given = " (인자)" if keys[i] and keys[i] in draft.given else ""
        value = values[i] if i < current else (sub if i == current else "")
        console.print(f"  {mark} {i + 1}. {title:<10} {value}{given}", markup=False)
    console.print()


def _plugin_toggle(current: list[str], value: str, now: bool) -> tuple[list[str], str | None]:
    if now:
        return [p.id for p in PLUGINS if p.id in current], None
    updated, dropped = drop_dependents(current)
    msg = f"{value} 가 없으면 {', '.join(dropped)} 를 쓸 수 없어 함께 해제했습니다" if dropped else None
    return updated, msg


def _platform_rules(state: RepoState):
    """Toggle + lock rules of the platform step: platforms with services and
    platforms another selected one requires (proto for backend-msa) stay checked."""
    with_services = {p for p in (state.manifest.platforms if state.manifest else {}) if state.existing(p)}

    def reasons(selected: list[str]) -> dict[str, str | None]:
        out: dict[str, str | None] = {}
        for p in PLATFORMS:
            needers = [q for q in selected if p.id in PLATFORM_BY_ID[q].requires]
            if p.id in with_services:
                unit = "언어" if p.is_contract else "서비스"
                out[p.id] = f"{unit} {len(state.existing(p.id))}개"
            elif needers:
                out[p.id] = f"{', '.join(needers)} 가 사용"
            else:
                out[p.id] = None
        return out

    def toggle(current: list[str], value: str, now: bool) -> tuple[list[str], str | None]:
        updated, added = with_required(list(dict.fromkeys([*current, *with_services])))
        msg = f"{value} 는 {', '.join(added)} 가 필요해 함께 선택했습니다" if now and added else None
        return updated, msg

    return with_services, reasons, toggle


def run_wizard(
    draft: Draft,
    state: RepoState,
    prompter: Prompter,
    console: Console,
    make_plan: Callable[[Draft], Plan],
    *,
    dry_run: bool = False,
    diff_root=None,
) -> tuple[Draft, Plan]:
    """Fill the draft interactively and return it with the confirmed plan.

    With dry_run the plan is printed in full and returned without asking.
    """
    step = 0
    # Per-platform position inside step 3 when coming back from step 4.
    name_index: int | None = None

    def skip(i: int) -> bool:
        return {0: "llms", 1: "platforms", 2: "plugins"}.get(i) in draft.given

    direction = 1
    while True:
        if step < 0:
            step = 0
            direction = 1
        if step in (0, 1, 2) and skip(step):
            step += direction
            continue

        if step == 0:
            _header(console, draft, state, 0)
            selected = set(draft.llms or [])
            answer = prompter.checkbox(
                "LLM 대상을 선택하세요",
                [Item(l.id, l.label, l.id in selected) for l in LLMS],
                minimum=1,
            )
            if answer is BACK:
                direction = -1
                step -= 1
                continue
            draft.llms = answer
        elif step == 1:
            _header(console, draft, state, 1)
            with_services, reasons, toggle = _platform_rules(state)
            selected, _ = with_required(list(dict.fromkeys([*(draft.platforms or []), *with_services])))
            why = reasons(selected)
            items = [Item(p.id, f"{p.id:<18} {p.hint}", p.id in selected, disabled=why[p.id]) for p in PLATFORMS]
            answer = prompter.checkbox("플랫폼을 선택하세요", items, minimum=1, on_toggle=toggle,
                                       disabled_for=reasons)
            if answer is BACK:
                direction = -1
                step -= 1
                continue
            draft.platforms, _ = with_required([p.id for p in PLATFORMS if p.id in answer])
            for pid in list(draft.names):
                if pid not in draft.platforms:
                    del draft.names[pid]
        elif step == 2:
            _header(console, draft, state, 2)
            if draft.plugins is None:
                selected = {p.id for p in PLUGINS if p.default}
            else:
                selected = set(draft.plugins)
            selected, _ = drop_dependents(list(selected))
            reasons = disabled_reasons(selected)
            items = [
                Item(
                    p.id,
                    f"{p.id:<9} {p.label:<30} {p.location}",
                    p.id in selected,
                    disabled=reasons[p.id],
                )
                for p in PLUGINS
            ]
            answer = prompter.checkbox("플러그인을 선택하세요", items, on_toggle=_plugin_toggle,
                                       disabled_for=disabled_reasons,
                                       instruction="(space: 선택/해제, enter: 다음, ←: 이전)")
            if answer is BACK:
                direction = -1
                step -= 1
                continue
            draft.plugins = [p.id for p in PLUGINS if p.id in answer]
        elif step == 3:
            result = _names_step(draft, state, prompter, console, start=name_index)
            name_index = None
            if result is BACK:
                direction = -1
                step -= 1
                continue
        elif step == 4:
            errors = validate(draft, state)
            if errors:
                for e in errors:
                    console.print(f"[red]error:[/red] {e}")
                direction = -1
                step = 1
                continue
            _header(console, draft, state, 4)
            plan = make_plan(draft)
            print_summary(console, plan, draft, details=dry_run, diff_root=diff_root)
            if dry_run:
                return draft, plan
            choices = [("apply", "적용"), ("details", "자세히 보기"), ("back", "이전 단계"), ("cancel", "취소")]
            if not draft.purge and any(not is_env_value(rel) for rel in plan.orphans):
                choices.insert(1, ("purge", "적용 + 남겨 둔 파일도 삭제 (--purge, env 값 파일 제외)"))
            while True:
                choice = prompter.select("적용할까요?", choices)
                if choice == "details":
                    print_summary(console, plan, draft, details=True, diff_root=state.root)
                    continue
                break
            if choice == "purge":
                draft.purge = True
                plan = make_plan(draft)
                print_summary(console, plan, draft, details=True)
                return draft, plan
            if choice == "apply":
                return draft, plan
            if choice == "cancel":
                raise Cancelled
            direction = -1
            step = 3
            name_index = -1
            continue
        direction = 1
        step += 1


def _names_step(draft: Draft, state: RepoState, prompter: Prompter, console: Console, *, start: int | None):
    platforms = [p for p in (draft.platforms or []) if f"names:{p}" not in draft.given]
    if not platforms:
        return None if start is None else BACK
    new_platforms = set(draft.new_platforms(state))
    i = 0 if start is None else (len(platforms) - 1 if start < 0 else start)
    while 0 <= i < len(platforms):
        pid = platforms[i]
        platform = PLATFORM_BY_ID[pid]
        existing = set(state.existing(pid))
        is_new = pid in new_platforms
        _header(console, draft, state, 3, f"({i + 1}/{len(platforms)}) {pid}")
        if platform.is_contract:
            chosen = set(draft.names.get(pid, []))
            answer = prompter.checkbox(
                f"{pid}: 코드를 생성할 언어를 선택하세요 (proto/dist/<언어>/)",
                [Item(l.id, f"{l.id:<8} {l.label}", l.id in existing or l.id in chosen,
                      disabled="이미 있음" if l.id in existing else None) for l in LANGUAGES],
                minimum=1 if is_new else 0,
                instruction="(space: 선택/해제, enter: 다음, ←: 이전)",
            )
            if answer is BACK:
                i -= 1
                continue
            new = [l for l in answer if l not in existing]
            if new:
                draft.names[pid] = new
                console.print("  → " + ", ".join(f"{pid}/dist/{l}" for l in new), markup=False)
            else:
                draft.names.pop(pid, None)
            i += 1
            continue

        def check(raw: str, existing=existing, is_new=is_new) -> str | None:
            parsed = parse_names(raw, existing=existing)
            if parsed.errors:
                return "; ".join(parsed.errors)
            if is_new and not parsed.names:
                return "새 플랫폼은 서비스 이름이 최소 1개 필요합니다"
            return None

        hint = f" — 기존: {', '.join(sorted(existing))}" if existing else ""
        answer = prompter.text(
            f"{pid} 서비스 이름 (공백 또는 , 로 구분){hint}:",
            default=", ".join(draft.names.get(pid, [])),
            validate=check,
        )
        if answer is BACK:
            i -= 1
            continue
        parsed = parse_names(answer, existing=existing)
        for note in parsed.notes:
            console.print(f"  · {note}", markup=False)
        if parsed.names:
            draft.names[pid] = parsed.names
            console.print("  → " + ", ".join(f"{pid}/{n}" for n in parsed.names), markup=False)
        else:
            draft.names.pop(pid, None)

        i += 1
    return BACK if i < 0 else None

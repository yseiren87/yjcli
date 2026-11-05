"""`yjcli wizard`.

Screens: LLM → platforms → plugins → per platform (existing services, new names,
options; languages for proto) → confirm. The list is rebuilt after every answer,
so the per-platform screens follow the platform choice. ← goes to the previous
screen. On a configured repository every screen starts from the stored
configuration and marks what is installed: checking adds, unchecking removes.
Nothing is written before the confirmation.
"""

from __future__ import annotations

from typing import Callable

from rich.console import Console

from yjcli.catalog import LANGUAGES, LLMS, PLATFORM, PLATFORMS, PLUGINS, drop_dependents, plugins_lacking, with_required
from yjcli.plan import Plan
from yjcli.repo import Repo
from yjcli.selection import Request, check_units, secrets_wanted
from yjcli.ui import report
from yjcli.ui.prompts import BACK, Item, Prompter

STEPS = ("LLM 대상", "플랫폼", "플러그인", "플랫폼 설정", "확인 및 실행")
MakePlan = Callable[[Request], tuple[Plan | None, list[str]]]


class Cancelled(Exception):
    pass


def installed_label(repo: Repo, pid: str) -> str:
    units = repo.existing(pid)
    if not units and not (repo.manifest and pid in repo.manifest.units):
        return ""
    return "  설치됨" + (f" · {', '.join(units)}" if units else "")


def _header(console: Console, repo: Repo, req: Request, step: int, sub: str = "") -> None:
    console.print()
    console.print(f"[bold]yjcli[/bold] · {repo.root} · {'업데이트' if repo.configured else '신규 설치'}")
    done = (", ".join(req.llms or []), ", ".join(req.platforms or []),
            ", ".join(req.plugins or []) or ("없음" if req.plugins is not None else ""), "", "")
    answered = ("llms", "platforms", "plugins", None, None)
    for i, title in enumerate(STEPS):
        mark = "✔" if i < step else "▸" if i == step else "○"
        value = done[i] if i < step else sub if i == step else ""
        tag = " (인자)" if answered[i] in req.answered else ""
        console.print(f"  {mark} {i + 1}. {title:<10} {value}{tag}", markup=False)
    console.print()


def _screens(req: Request, repo: Repo) -> list[tuple[str, str | None]]:
    out: list[tuple[str, str | None]] = [(s, None) for s in ("llms", "platforms", "plugins") if s not in req.answered]
    for pid in req.platforms or []:
        if PLATFORM[pid].contract:
            if f"units:{pid}" not in req.answered:
                out.append(("languages", pid))
            continue
        if f"units:{pid}" not in req.answered:
            if repo.existing(pid):
                out.append(("services", pid))
            out.append(("names", pid))
        if "secrets" not in req.answered:
            out.append(("options", pid))
    return out + [("confirm", None)]


def _platform_locks(selected: list[str]) -> dict[str, str | None]:
    return {p.id: (", ".join(q for q in selected if p.id in PLATFORM[q].requires) + " 가 사용")
            if any(p.id in PLATFORM[q].requires for q in selected) else None for p in PLATFORMS}


def _platform_toggle(selected: list[str], value: str, now: bool) -> tuple[list[str], str | None]:
    full, added = with_required(selected)
    return full, (f"{value} 는 {', '.join(added)} 가 필요해 함께 선택했습니다" if now and added else None)


def _plugin_locks(selected: list[str]) -> dict[str, str | None]:
    lacking = {p.id: [r for r in p.requires if r not in selected] for p in PLUGINS}
    return {p: (f"{', '.join(r)} 먼저 선택" if r else None) for p, r in lacking.items()}


def _plugin_toggle(selected: list[str], value: str, now: bool) -> tuple[list[str], str | None]:
    kept, dropped = drop_dependents(selected)
    return kept, (f"{value} 가 없으면 {', '.join(dropped)} 를 쓸 수 없어 함께 해제했습니다" if dropped else None)


def _set(req: Request, pid: str, *, add: list[str] | None = None, remove: list[str] | None = None) -> None:
    for units, values in ((req.add, add), (req.remove, remove)):
        if values is None:
            continue
        if values:
            units[pid] = list(values)
        else:
            units.pop(pid, None)


def run_wizard(req: Request, repo: Repo, prompter: Prompter, console: Console, make_plan: MakePlan, *,
               dry_run: bool = False, diff_root=None) -> Plan:
    """Fill the request interactively; returns the confirmed plan (raises Cancelled)."""
    stored_llms = set(repo.manifest.llms) if repo.manifest else set()
    stored_plugins = set(repo.manifest.plugins) if repo.manifest else set()
    have = set(repo.platforms())
    i = 0
    while True:
        screens = _screens(req, repo)
        i = max(0, min(i, len(screens) - 1))
        kind, pid = screens[i]
        per_platform = [s for s in screens if s[1]]
        answer = None

        if kind == "llms":
            _header(console, repo, req, 0)
            chosen = set(req.llms or [])
            answer = prompter.checkbox("LLM 대상을 선택하세요", [
                Item(l.id, l.label + ("  설치됨" if l.id in stored_llms else ""), l.id in chosen) for l in LLMS
            ], minimum=1)
            if answer is not BACK:
                req.llms = answer
        elif kind == "platforms":
            _header(console, repo, req, 1)
            chosen, _ = with_required(req.platforms or [])
            locks = _platform_locks(chosen)
            answer = prompter.checkbox("플랫폼을 선택하세요 (해제하면 그 플랫폼의 코드까지 삭제)", [
                Item(p.id, f"{p.id:<18} {p.hint}{installed_label(repo, p.id)}", p.id in chosen, locks[p.id])
                for p in PLATFORMS
            ], minimum=1, toggle=_platform_toggle, locks=_platform_locks)
            if answer is not BACK:
                req.platforms, _ = with_required(answer)
                for units in (req.add, req.remove):
                    for p in [p for p in units if p not in req.platforms]:
                        del units[p]
        elif kind == "plugins":
            _header(console, repo, req, 2)
            chosen = req.plugins if req.plugins is not None else [p.id for p in PLUGINS if p.default]
            chosen, _ = drop_dependents(chosen)
            locks = _plugin_locks(chosen)
            answer = prompter.checkbox("플러그인을 선택하세요", [
                Item(p.id, f"{p.id:<9} {p.label}" + ("  설치됨" if p.id in stored_plugins else ""), p.id in chosen,
                     locks[p.id]) for p in PLUGINS
            ], toggle=_plugin_toggle, locks=_plugin_locks)
            if answer is not BACK:
                req.plugins = [p.id for p in PLUGINS if p.id in answer and not plugins_lacking(answer).get(p.id)]
        elif kind == "confirm":
            _header(console, repo, req, 4)
            plan, errors = make_plan(req)
            if errors:
                for e in errors:
                    console.print(f"[red]error:[/red] {e}", highlight=False)
                i = 0
                continue
            report.summary(console, plan, details=dry_run, diff_root=diff_root)
            if dry_run:
                return plan
            if plan.removals:
                question = "삭제가 포함되어 있습니다. 적용할까요?"
                choices = [("cancel", "취소"), ("apply", "적용"), ("details", "자세히 보기"), ("back", "이전 단계")]
            else:
                question = "적용할까요?"
                choices = [("apply", "적용"), ("details", "자세히 보기"), ("back", "이전 단계"), ("cancel", "취소")]
            choice = prompter.select(question, choices)
            while choice == "details":
                report.summary(console, plan, details=True, diff_root=repo.root)
                choice = prompter.select(question, choices)
            if choice == "apply":
                req.code_removal_ok = True  # the confirmation listed every removal
                return plan
            if choice == "cancel":
                raise Cancelled
            answer = BACK
        else:
            platforms = list(dict.fromkeys(p for _, p in per_platform))
            _header(console, repo, req, 3, f"({platforms.index(pid) + 1}/{len(platforms)}) {pid}")
            existing = repo.existing(pid)
            if kind == "languages":
                chosen = (set(existing) - set(req.remove.get(pid, []))) | set(req.add.get(pid, []))
                needed = pid not in have or any(pid in PLATFORM[q].requires for q in req.platforms or [])
                answer = prompter.checkbox(f"{pid}: 코드를 생성할 언어 (proto/dist/<언어>/, 해제하면 삭제)", [
                    Item(l.id, f"{l.id:<8} {l.label}" + ("  설치됨" if l.id in existing else ""), l.id in chosen)
                    for l in LANGUAGES
                ], minimum=1 if needed else 0)
                if answer is not BACK:
                    _set(req, pid, add=[l for l in answer if l not in existing],
                         remove=[l for l in existing if l not in answer])
            elif kind == "services":
                keep = [s for s in existing if s not in req.remove.get(pid, [])]
                answer = prompter.checkbox(f"{pid} 서비스 (해제하면 폴더까지 삭제)",
                                           [Item(s, s, s in keep) for s in existing])
                if answer is not BACK:
                    _set(req, pid, remove=[s for s in existing if s not in answer])
            elif kind == "names":
                def check(raw: str, pid=pid, existing=existing) -> str | None:
                    names, errors, _ = check_units(pid, raw, existing)
                    if errors:
                        return "; ".join(errors)
                    if pid not in have and not names:
                        return "새 플랫폼은 서비스가 최소 1개 필요합니다"
                    return None

                answer = prompter.text(f"{pid} 새 서비스 이름 (공백 또는 , 로 구분, 없으면 enter):",
                                       default=", ".join(req.add.get(pid, [])), check=check)
                if answer is not BACK:
                    names, _, notes = check_units(pid, answer, existing)
                    for note in notes:
                        console.print(f"  · {note}", markup=False)
                    _set(req, pid, add=names)
                    if names:
                        console.print("  → " + ", ".join(f"{pid}/{n}" for n in names), markup=False)
                    if pid in have and not names and not [s for s in existing if s not in req.remove.get(pid, [])]:
                        console.print(f"  → {pid} 에 서비스가 남지 않아 플랫폼이 삭제됩니다", markup=False)
            else:  # options
                answer = prompter.checkbox(f"{pid}: 옵션", [Item(
                    "secrets", f"secrets   tools/secrets/{pid}/<service>/.env.* (끄면 그 폴더 삭제)",
                    secrets_wanted(req, repo, pid))])
                if answer is not BACK:
                    req.secrets[pid] = "secrets" in answer
        i = i - 1 if answer is BACK else i + 1

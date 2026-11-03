"""Plan summary (rich): selection table, action counts, warnings, details."""

from __future__ import annotations

import difflib
from pathlib import Path

from rich.console import Console
from rich.table import Table

from yjcli.core.planner import Plan
from yjcli.core.selection import Draft, option_values

_KIND_LABEL = {
    "create": "+ 생성",
    "mkdir": "+ 폴더",
    "overwrite": "~ 덮어쓰기",
    "merge": "~ 블록 갱신",
    "chmod": "~ 실행 권한",
    "delete": "- 삭제",
    "rmtree": "- 폴더 삭제",
}


def _services_text(plan: Plan) -> str:
    parts = []
    for pid, names in plan.services.items():
        fresh = set(plan.new_services.get(pid, []))
        parts += [f"{pid}/{n}" + (" (+)" if n in fresh else "") for n in names]
    return ", ".join(parts) or "—"


def _platforms_text(plan: Plan, draft: Draft) -> str:
    out = []
    for pid in plan.platforms:
        on = [o for o, v in option_values(draft, pid).items() if v] if pid in plan.new_platforms else []
        out.append(pid + (f" ({', '.join(on)})" if on else ""))
    return ", ".join(out) or "—"


def print_summary(
    console: Console, plan: Plan, draft: Draft, *, details: bool = False, diff_root: Path | None = None
) -> None:
    title = "계획 요약 — " + ("신규 설치" if plan.mode == "new" else "업데이트")
    table = Table(title=title, show_header=False, title_justify="left")
    table.add_column(style="bold")
    table.add_column()
    if plan.from_version is not None:
        same = plan.from_version == plan.to_version
        table.add_row("yjcli", plan.to_version if same else f"{plan.from_version} → {plan.to_version}")
    table.add_row("LLM", ", ".join(plan.llms) or "—")
    table.add_row("플랫폼", _platforms_text(plan, draft))
    table.add_row("플러그인", ", ".join(plan.plugins) or "없음 (코드만)")
    table.add_row("서비스", _services_text(plan))
    table.add_row("스킬(자동)", ", ".join(plan.skills))
    console.print(table)

    counts = [
        ("+ 생성", plan.count("create", "mkdir")),
        ("~ 변경", plan.count("overwrite", "merge", "chmod")),
        ("= 보존", len(plan.kept)),
        ("- 삭제", plan.count("delete", "rmtree")),
    ]
    console.print("  " + "   ".join(f"{label} {n}개" for label, n in counts))

    if details or plan.mode == "update":
        shown = [a for a in plan.actions if details or a.kind not in ("create", "mkdir")]
        for action in shown:
            label = _KIND_LABEL.get(action.kind, action.kind)
            extra = f" ({action.reason})" if action.reason else ""
            console.print(f"    {label:<10} {action.path}{extra}", markup=False)

    if diff_root is not None:
        print_diffs(console, plan, diff_root)

    for note in plan.notes:
        console.print(f"  · {note}", markup=False)
    for warning in plan.warnings:
        console.print(f"  [yellow]{warning}[/yellow]")


def print_diffs(console: Console, plan: Plan, root: Path) -> None:
    """Unified diff of every file the plan changes in place (manifest excluded)."""
    for action in plan.actions:
        if action.kind not in ("overwrite", "merge") or action.path.startswith(".yjcli/"):
            continue
        old = (root / action.path).read_text(encoding="utf-8", errors="replace").splitlines()
        new = (action.content or b"").decode("utf-8", errors="replace").splitlines()
        lines = list(difflib.unified_diff(old, new, f"a/{action.path}", f"b/{action.path}", lineterm=""))
        if not lines:
            continue
        console.print()
        for line in lines:
            style = "green" if line.startswith("+") else "red" if line.startswith("-") else "cyan" if line.startswith("@@") else None
            console.print(line, style=style, markup=False, highlight=False)


def print_next_steps(console: Console, plan: Plan) -> None:
    console.print("[green]완료.[/green]")
    first = next(((p, s[0]) for p, s in plan.services.items() if s), None)
    if "runner" in plan.plugins and first:
        p, s = first
        console.print(f"  실행 명령 설정: tools/secrets/{p}/{s}/.env.local-dev 의 RUN_COMMAND", markup=False)
        console.print(f"  실행: make {p}            (플랫폼 전체)", markup=False)
        console.print(f"        make {p} NAME={s}   (서비스 하나)", markup=False)
    if "builder" in plan.plugins and first:
        p, s = first
        console.print(f"  빌드: make {p}-build-development NAME={s}  (tools/builder/{p}/ 구현 필요)", markup=False)
    if not plan.plugins:
        console.print("  플러그인 없이 코드만 만들었습니다. 나중에 `yjcli` 를 다시 실행해 추가할 수 있습니다.", markup=False)
    console.print("  서비스 추가: yjcli service add -n <platform>=<이름들>", markup=False)

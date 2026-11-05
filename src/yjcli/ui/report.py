"""What a plan will do (before) and what a run did (after)"""

from __future__ import annotations

import difflib
from pathlib import Path

from rich.console import Console
from rich.table import Table

from yjcli.catalog import PLATFORM
from yjcli.plan import Plan
from yjcli.selection import Config

LABEL = {
    "create": "+ 생성",
    "mkdir": "+ 폴더",
    "overwrite": "~ 덮어쓰기",
    "merge": "~ 블록 갱신",
    "chmod": "~ 실행 권한",
    "delete": "- 삭제",
    "rmtree": "- 폴더 삭제",
}


def _with_diff(now: list[str], before: list[str] | None) -> str:
    text = ", ".join(now) or "—"
    if before is not None:
        if added := [x for x in now if x not in before]:
            text += "  (+ " + ", ".join(added) + ")"
        if removed := [x for x in before if x not in now]:
            text += "  (- " + ", ".join(removed) + ")"
    return text


def _units(cfg: Config | None) -> list[str] | None:
    if cfg is None:
        return None
    return [f"{p}/dist/{u}" if PLATFORM[p].contract else f"{p}/{u}" for p, us in cfg.units.items() for u in us]


def summary(console: Console, plan: Plan, *, details: bool = False, diff_root: Path | None = None,
            table_only: bool = False) -> None:
    cfg, before = plan.config, plan.before
    table = Table(title="계획 요약 — " + ("신규 설치" if plan.new else "업데이트"), show_header=False,
                  title_justify="left")
    table.add_column(style="bold")
    table.add_column()
    if plan.previous is not None:
        table.add_row("yjcli", plan.version if plan.previous == plan.version else f"{plan.previous} → {plan.version}")
    table.add_row("LLM", _with_diff(cfg.llms, before.llms if before else None))
    table.add_row("플랫폼", _with_diff(cfg.platforms, before.platforms if before else None))
    table.add_row("플러그인", _with_diff(cfg.plugins, before.plugins if before else None)
                  if cfg.plugins or (before and before.plugins) else "없음 (코드만)")
    table.add_row("서비스", _with_diff(_units(cfg), _units(before)))
    if services := [p for p in cfg.platforms if not PLATFORM[p].contract]:
        table.add_row("secrets", ", ".join(f"{p} {'켬' if p in cfg.secrets else '끔'}" for p in services))
    table.add_row("스킬(자동)", ", ".join(plan.skills))
    console.print(table)
    if table_only:
        return
    removals(console, plan)
    _changes(console, plan, details)
    if diff_root is not None:
        diffs(console, plan, diff_root)
    _attention(console, plan)


def removals(console: Console, plan: Plan) -> None:
    if not plan.removals:
        return
    console.print("  삭제:", style="red", markup=False)
    width = max(len(r.path) for r in plan.removals) + 2
    for r in plan.removals:
        console.print(f"    - {r.path:<{width}} 파일 {r.files}개 · {r.why}", markup=False)


def result(console: Console, plan: Plan) -> None:
    console.print()
    console.print("[green]완료 — 적용 결과[/green]")
    _changes(console, plan, details=False)
    _attention(console, plan)


def _changes(console: Console, plan: Plan, details: bool) -> None:
    counts = (("+ 생성", plan.count("create", "mkdir")), ("~ 변경", plan.count("overwrite", "merge", "chmod")),
              ("= 보존", len(plan.kept)), ("- 삭제", plan.count("delete", "rmtree")))
    console.print("  " + "   ".join(f"{label} {n}개" for label, n in counts))
    # a new repository creates many files: list them only on request; every other run lists all changes
    for c in plan.file_changes:
        if details or not plan.new or c.kind not in ("create", "mkdir"):
            note = f" ({c.note})" if c.note and c.kind != "rmtree" else ""
            console.print(f"    {LABEL[c.kind]:<8} {c.path}{note}", markup=False)
    if not plan.new and not plan.file_changes:
        console.print("    바뀐 파일 없음", markup=False)


def _attention(console: Console, plan: Plan) -> None:
    for note in plan.notes:
        console.print(f"  · {note}", markup=False)
    if not plan.review and not plan.warnings:
        return
    console.print(f"  확인할 것 {len(plan.review) + len(plan.warnings)}개:", style="yellow", markup=False)
    for item in plan.review:
        console.print(f"    · {item}", markup=False)
    for item in plan.warnings:
        console.print(f"    {item}", style="yellow", markup=False)


def diffs(console: Console, plan: Plan, root: Path) -> None:
    for c in plan.file_changes:
        if c.kind not in ("overwrite", "merge"):
            continue
        old = (root / c.path).read_text(encoding="utf-8", errors="replace").splitlines()
        new = (c.content or b"").decode("utf-8", "replace").splitlines()
        lines = list(difflib.unified_diff(old, new, f"a/{c.path}", f"b/{c.path}", lineterm=""))
        if lines:
            console.print()
        for line in lines:
            style = {"+": "green", "-": "red", "@": "cyan"}.get(line[:1])
            console.print(line, style=style, markup=False, highlight=False)


def next_steps(console: Console, plan: Plan) -> None:
    cfg = plan.config
    console.print()
    if cfg.secrets:
        p = cfg.secrets[0]
        console.print(f"  환경 값: tools/secrets/{p}/{cfg.units[p][0]}/.env.*", markup=False)
    first = next(((p, us[0]) for p, us in cfg.units.items() if not PLATFORM[p].contract), None)
    if cfg.plugins and first:
        p, s = first
        console.print("  각 도구는 tools/<도구>/GUIDE.md 를 따라 tools/<도구>/<platform>/ 스크립트를 구현하세요.", markup=False)
        if "runner" in cfg.plugins:
            console.print(f"  실행: make {p} [NAME={s}]", markup=False)
        if "builder" in cfg.plugins:
            console.print(f"  빌드: make {p}-build-development [NAME={s}]   → dist/{p}/{s}/", markup=False)
        if "deployer" in cfg.plugins:
            console.print(f"  배포: make {p}-deploy-development [NAME={s}]", markup=False)
        console.print("  Windows: powershell -ExecutionPolicy Bypass -File make.ps1 <target> [NAME=<service>]", markup=False)
    elif not cfg.plugins:
        console.print("  도구 플러그인 없이 코드만 만들었습니다. 필요하면 yjcli plugin add 로 추가하세요.", markup=False)
    console.print("  변경: yjcli wizard · 도움말: yjcli help", markup=False)

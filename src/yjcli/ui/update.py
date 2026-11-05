"""`yjcli update` interactively: status → changes → confirm.

The selection does not change and every yjcli-owned file is refreshed together,
so nothing is picked here: the screens only show and confirm.
"""

from __future__ import annotations

from rich.console import Console

from yjcli.plan import Plan
from yjcli.repo import Repo
from yjcli.ui import report
from yjcli.ui.prompts import BACK, Prompter
from yjcli.ui.wizard import Cancelled

STEPS = ("현황", "바뀌는 내용", "확인 및 실행")
OVERWRITTEN = "로컬 수정 덮어씀"


def _header(console: Console, repo: Repo, plan: Plan, step: int) -> None:
    console.print()
    console.print(f"[bold]yjcli[/bold] · {repo.root} · 업데이트 {plan.previous} → {plan.version}")
    for i, title in enumerate(STEPS):
        console.print(f"  {'✔' if i < step else '▸' if i == step else '○'} {i + 1}. {title}", markup=False)
    console.print()


def _move_hint(path: str) -> str:
    if path.endswith("/SKILL.md"):
        return f".yjcli/skills/{path.rsplit('/', 2)[-2]}.md 로"
    if path.endswith("/GUIDE.md"):
        return "프로젝트 메모는 AGENTS.md 로"
    return "필요한 내용은 다른 곳으로"


def change_groups(plan: Plan) -> list[tuple[str, str]]:
    written = [c for c in plan.file_changes if c.kind in ("create", "overwrite", "merge", "chmod")]
    paths = {c.path for c in written}
    skills = [p for p in paths if p.endswith("/SKILL.md")]
    guides = sorted(p.split("/")[1] for p in paths if p.startswith("tools/") and p.endswith("/GUIDE.md"))
    singles = (("AGENTS.md", "블록 갱신"), (".gitignore", "블록 갱신"), ("CLAUDE.md", "갱신"), ("Makefile", "갱신"),
               ("make.ps1", "갱신"))
    grouped = set(skills) | {f"tools/{g}/GUIDE.md" for g in guides} | {name for name, _ in singles}
    rows = [("스킬", f"{len(skills)}개 갱신" if skills else "변경 없음"),
            ("가이드", ", ".join(f"tools/{g}" for g in guides) or "변경 없음")]
    rows += [(name, what if name in paths else "변경 없음") for name, what in singles]
    rows.append(("새 파일", ", ".join(c.path for c in written if c.kind == "create" and c.path not in grouped) or "없음"))
    rows += [("확인 필요", item) for item in plan.review if "시작 템플릿" in item]
    return rows


def run_update(repo: Repo, plan: Plan, prompter: Prompter, console: Console) -> None:
    """Returns when the user confirms; raises Cancelled otherwise."""
    step = 0
    while True:
        _header(console, repo, plan, step)
        if step == 0:
            console.print(f"  설치된 yjcli {plan.version} · 저장소 {plan.previous}", markup=False)
            edited = [c.path for c in plan.file_changes if c.note == OVERWRITTEN]
            if not edited:
                console.print("  로컬에서 수정한 관리 파일 없음", markup=False)
                step = 1
                continue
            console.print("  로컬에서 수정한 관리 파일 (덮어써집니다):", style="yellow", markup=False)
            width = max(map(len, edited)) + 2
            for path in edited:
                console.print(f"    ! {path:<{width}} → {_move_hint(path)}", markup=False)
            choice = prompter.select("계속할까요?", [("go", "계속 (덮어씀)"), ("diff", "diff 보기"), ("stop", "중단 (먼저 옮기기)")])
            if choice == "diff":
                report.diffs(console, plan, repo.root)
            elif choice in ("stop", BACK):
                raise Cancelled
            else:
                step = 1
        elif step == 1:
            for name, what in change_groups(plan):
                console.print(f"  {name:<10} {what}", markup=False)
            choice = prompter.select("다음", [("next", "다음"), ("diff", "자세히 보기 (파일별 diff)"), ("back", "이전")])
            if choice == "diff":
                report.diffs(console, plan, repo.root)
            elif choice in ("back", BACK):
                step = 0
            else:
                step = 2
        else:
            choice = prompter.select("적용할까요?", [("apply", "적용"), ("back", "이전 단계"), ("cancel", "취소")])
            if choice == "apply":
                return
            if choice in ("back", BACK):
                step = 1
                continue
            raise Cancelled

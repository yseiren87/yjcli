"""Entry: `yjcli` runs the wizard; arguments answer its steps in advance."""

from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

from yjcli.catalog import data_root
from yjcli.catalog.llms import LLMS
from yjcli.catalog.platforms import PLATFORMS
from yjcli.catalog.plugins import PLUGINS
from yjcli.core import executor, manifest as manifest_mod
from yjcli.catalog.plugins import MANAGED
from yjcli.core.planner import PlanError, build_plan
from yjcli.core.selection import Draft, fill_from_manifest, from_args, missing, validate
from yjcli.core.state import read_state
from yjcli.ui.summary import print_next_steps, print_summary

console = Console(soft_wrap=True)
err_console = Console(stderr=True, soft_wrap=True)


def package_version() -> str:
    """Installed package version from pyproject metadata (single source)."""
    try:
        return version("yjcli")
    except PackageNotFoundError:
        return "0.0.0+local"


_IDS = {
    "llm": ", ".join(l.id for l in LLMS),
    "platform": ", ".join(p.id for p in PLATFORMS),
    "plugin": ", ".join(p.id for p in PLUGINS),
}

LlmOpt = Annotated[Optional[list[str]], typer.Option("--llm", "-l", help=f"LLM 대상 (반복/쉼표, all). {_IDS['llm']}")]
PlatformOpt = Annotated[Optional[list[str]], typer.Option("--platform", "-p", help=f"플랫폼 (반복/쉼표, all). {_IDS['platform']}")]
PluginOpt = Annotated[Optional[list[str]], typer.Option("--plugin", help=f"플러그인 (반복/쉼표, all, none). {_IDS['plugin']}")]
NameOpt = Annotated[Optional[list[str]], typer.Option("--name", "-n", help="서비스 이름: <platform>=a1,a2 (반복)")]
OptionOpt = Annotated[Optional[list[str]], typer.Option("--option", "-o", help="플랫폼 옵션: <platform>=proto 또는 no-proto")]
ModeOpt = Annotated[Optional[str], typer.Option("--mode", help="new | update (기본: 자동 감지)")]
YesOpt = Annotated[bool, typer.Option("--yes", "-y", help="확인 없이 실행")]
DryRunOpt = Annotated[bool, typer.Option("--dry-run", help="계획만 출력하고 종료")]
ForceOpt = Annotated[bool, typer.Option("--force", help="사용자가 수정한 관리 파일도 덮어씀, 버전 가드 무시")]
DiffOpt = Annotated[bool, typer.Option("--diff", help="바뀌는 파일의 내용 차이(diff)도 출력")]
PathOpt = Annotated[
    Path,
    typer.Option("--path", help="대상 저장소 루트 (기본: 현재 폴더)", file_okay=False, dir_okay=True, resolve_path=True),
]

app = typer.Typer(
    name="yjcli",
    help="YJ 아키텍처 저장소 구성 도구. 인자 없이 실행하면 단계별 위저드가 열립니다.",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
)
service_app = typer.Typer(help="서비스 관리", no_args_is_help=True)
app.add_typer(service_app, name="service")


def _fail(messages: list[str], title: str = "error") -> None:
    for message in messages:
        err_console.print(f"[red]{title}:[/red] {message}", highlight=False)
    raise typer.Exit(code=1)


def _interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def run(
    root: Path,
    *,
    mode: str | None,
    llm, platform, plugin, name, option,
    yes: bool,
    dry_run: bool,
    force: bool,
    diff: bool = False,
    prepare=None,
) -> None:
    if mode not in (None, "new", "update"):
        _fail([f"--mode 는 new 또는 update 입니다: {mode}"])
    root.mkdir(parents=True, exist_ok=True)
    try:
        state = read_state(root)
    except ValueError as exc:
        _fail([str(exc)])
    if state.manifest and manifest_mod.is_older(package_version(), state.manifest.yjcli_version) and not force:
        _fail([
            f"설치된 yjcli({package_version()})가 이 저장소를 마지막으로 구성한 버전"
            f"({state.manifest.yjcli_version})보다 낮습니다. 옛 내용으로 덮어쓰지 않도록 중단합니다.",
            "`uv tool upgrade yjcli` 후 다시 실행하세요 (그래도 진행하려면 --force).",
        ])
    draft, errors = from_args(state, mode=mode, llm=llm, platform=platform, plugin=plugin, name=name, option=option)
    if errors:
        _fail(errors)
    if prepare:
        prepare(draft, state)
    if draft.mode == "update":
        fill_from_manifest(draft, state)

    def make_plan(d: Draft):
        try:
            return build_plan(d, state, version=package_version(), force=force)
        except PlanError as exc:
            _fail(exc.errors)

    interactive = _interactive() and not yes
    if interactive:
        from yjcli.ui.prompts import QuestionaryPrompter
        from yjcli.ui.wizard import Cancelled, run_wizard

        try:
            draft, plan = run_wizard(draft, state, QuestionaryPrompter(), console, make_plan,
                                     dry_run=dry_run, diff_root=root if diff else None)
        except (Cancelled, KeyboardInterrupt):
            console.print("취소했습니다. 아무 파일도 바꾸지 않았습니다.")
            raise typer.Exit(code=0)
        if dry_run:
            return
    else:
        gaps = missing(draft, state)
        if not yes and not dry_run:
            gaps.append("--yes (비대화형 실행은 확인 대신 --yes 또는 --dry-run 이 필요합니다)")
        if gaps:
            _fail(gaps, title="missing")
        errors = validate(draft, state)
        if errors:
            _fail(errors)
        plan = make_plan(draft)
        print_summary(console, plan, draft, details=dry_run, diff_root=root if diff else None)
        if dry_run:
            return

    try:
        executor.apply(plan, root)
    except executor.ApplyError as exc:
        _fail([f"적용 중 실패: {exc}", *[f"이미 적용됨: {w}" for w in exc.written], "매니페스트는 저장하지 않았습니다."])
    print_next_steps(console, plan)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(package_version())
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    llm: LlmOpt = None,
    platform: PlatformOpt = None,
    plugin: PluginOpt = None,
    name: NameOpt = None,
    option: OptionOpt = None,
    mode: ModeOpt = None,
    yes: YesOpt = False,
    dry_run: DryRunOpt = False,
    force: ForceOpt = False,
    diff: DiffOpt = False,
    path: PathOpt = Path("."),
    version_: Annotated[
        Optional[bool],
        typer.Option("--version", "-V", help="버전 출력", callback=_version_callback, is_eager=True),
    ] = None,
) -> None:
    """새 저장소 구성 또는 기존 구성 업데이트 (위저드)."""
    if ctx.invoked_subcommand is not None:
        return
    run(path, mode=mode, llm=llm, platform=platform, plugin=plugin, name=name, option=option,
        yes=yes, dry_run=dry_run, force=force, diff=diff)


@app.command("update")
def update(
    yes: YesOpt = False,
    dry_run: DryRunOpt = False,
    force: ForceOpt = False,
    diff: DiffOpt = False,
    path: PathOpt = Path("."),
) -> None:
    """선택은 그대로 두고, 설치된 yjcli 의 최신 스킬·AGENTS.md 블록·관리 파일을 반영."""

    def prepare(draft: Draft, state) -> None:
        if not state.manifest:
            _fail([".yjcli/manifest.toml 이 없습니다. 먼저 `yjcli` 로 구성하세요"])
        draft.given |= {"llms", "platforms", "plugins"}
        draft.given |= {f"names:{p}" for p in state.manifest.platforms}

    run(path, mode="update", llm=None, platform=None, plugin=None, name=None, option=None,
        yes=yes, dry_run=dry_run, force=force, diff=diff, prepare=prepare)


@app.command("plan")
def plan_cmd(
    llm: LlmOpt = None,
    platform: PlatformOpt = None,
    plugin: PluginOpt = None,
    name: NameOpt = None,
    option: OptionOpt = None,
    mode: ModeOpt = None,
    force: ForceOpt = False,
    diff: DiffOpt = False,
    path: PathOpt = Path("."),
) -> None:
    """실행하지 않고 계획만 출력 (--dry-run 과 같음)."""
    run(path, mode=mode, llm=llm, platform=platform, plugin=plugin, name=name, option=option,
        yes=True, dry_run=True, force=force, diff=diff)


@service_app.command("add")
def service_add(
    name: NameOpt = None,
    yes: YesOpt = False,
    dry_run: DryRunOpt = False,
    path: PathOpt = Path("."),
) -> None:
    """기존 플랫폼에 서비스 추가 (업데이트 모드의 서비스 이름 단계만 실행)."""

    def prepare(draft: Draft, state) -> None:
        if not state.manifest:
            _fail([".yjcli/manifest.toml 이 없습니다. 먼저 `yjcli` 로 구성하세요"])
        unknown = [p for p in draft.names if p not in state.manifest.platforms]
        if unknown:
            _fail([f"구성되지 않은 플랫폼: {', '.join(unknown)} (플랫폼 추가는 `yjcli`)"])
        draft.platforms = list(state.manifest.platforms)
        draft.given |= {"llms", "platforms", "plugins"}
        if not _interactive() and not any(draft.names.values()):
            _fail(["--name <platform>=<이름들> 이 필요합니다"], title="missing")

    run(path, mode="update", llm=None, platform=None, plugin=None, name=name, option=None,
        yes=yes, dry_run=dry_run, force=False, prepare=prepare)


@app.command("status")
def status(path: PathOpt = Path(".")) -> None:
    """매니페스트 내용, 버전 차이, 사용자가 수정한 관리 파일."""
    state = read_state(path)
    m = state.manifest
    if not m:
        console.print("yjcli 로 구성되지 않은 폴더입니다 (.yjcli/manifest.toml 없음).")
        raise typer.Exit(code=1)
    console.print(f"yjcli {m.yjcli_version} 로 구성됨 (설치된 버전 {package_version()})", markup=False)
    if manifest_mod.is_older(package_version(), m.yjcli_version):
        console.print("[yellow]  설치된 yjcli 가 더 낮습니다 — `uv tool upgrade yjcli` 필요[/yellow]")
    elif manifest_mod.version_key(package_version()) != manifest_mod.version_key(m.yjcli_version):
        console.print("  새 버전이 설치되어 있습니다 — `yjcli update` 로 반영하세요", markup=False)
    console.print(f"  LLM: {', '.join(m.llms)}", markup=False)
    console.print(f"  플러그인: {', '.join(m.plugins) or '없음'}", markup=False)
    for pid, services in m.platforms.items():
        console.print(f"  {pid}: {', '.join(services)}", markup=False)
    changed = []
    for rel, rec in sorted(m.files.items()):
        target = path / rel
        if rec.policy == MANAGED and target.is_file() and manifest_mod.sha256(target.read_bytes()) != rec.sha256:
            changed.append(rel)
    if changed:
        console.print("[yellow]사용자가 수정한 관리 파일 (업데이트 때 건너뜀):[/yellow]")
        for rel in changed:
            console.print(f"  ! {rel}", markup=False)


@app.command("doctor")
def doctor() -> None:
    """패키지에 포함된 자산 점검."""
    root = data_root()
    console.print("yjcli packaged data:")
    for sub in ("templates", "plugins", "skills"):
        n = sum(1 for f in (root / sub).rglob("*") if f.is_file())
        console.print(f"  {sub}: {n} files")

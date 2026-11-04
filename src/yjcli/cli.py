"""Entry: `yjcli` shows help; `yjcli start` runs the wizard (arguments answer its steps)."""

from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

from yjcli.catalog import data_root
from yjcli.catalog.llms import LLM_BY_ID, LLMS
from yjcli.catalog.platforms import PLATFORMS
from yjcli.catalog.plugins import PLUGIN_BY_ID, PLUGINS
from yjcli.core import executor, manifest as manifest_mod
from yjcli.catalog.plugins import MANAGED
from yjcli.core.planner import PlanError, build_plan, is_env_value
from yjcli.core.references import stale_references
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
PurgeOpt = Annotated[bool, typer.Option(
    "--purge", help="주인(플러그인·LLM·서비스)이 없어진 파일은 수정했더라도 삭제 (tools/secrets 의 env 값 파일 제외)")]
PathOpt = Annotated[
    Path,
    typer.Option("--path", help="대상 저장소 루트 (기본: 현재 폴더)", file_okay=False, dir_okay=True, resolve_path=True),
]

app = typer.Typer(
    name="yjcli",
    help="YJ 아키텍처 저장소 구성 도구. `yjcli start` 로 단계별 위저드를 시작합니다.",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
)
service_app = typer.Typer(help="서비스 관리", no_args_is_help=True)
app.add_typer(service_app, name="service")
plugin_app = typer.Typer(help="플러그인만 추가/제거 (나머지 선택은 manifest 그대로)", no_args_is_help=True)
app.add_typer(plugin_app, name="plugin")
llm_app = typer.Typer(help="LLM 대상만 추가/제거 (나머지 선택은 manifest 그대로)", no_args_is_help=True)
app.add_typer(llm_app, name="llm")


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
    purge: bool = False,
    prepare=None,
) -> None:
    if mode not in (None, "new", "update"):
        _fail([f"--mode 는 new 또는 update 입니다: {mode}"])
    root.mkdir(parents=True, exist_ok=True)
    try:
        state = read_state(root)
    except ValueError as exc:
        _fail([str(exc)])
    if state.manifest and manifest_mod.unsupported(state.manifest.yjcli_version):
        _fail([
            f"yjcli {state.manifest.yjcli_version} 로 구성된 저장소는 지원하지 않습니다 "
            f"({manifest_mod.MIN_SUPPORTED} 이상만, 하위 호환 없음).",
            "이전 산출물을 지우고 다시 구성하세요 — README 'Rebuilding a repo made with an older yjcli'.",
        ])
    if state.manifest and manifest_mod.is_older(package_version(), state.manifest.yjcli_version) and not force:
        _fail([
            f"설치된 yjcli({package_version()})가 이 저장소를 마지막으로 구성한 버전"
            f"({state.manifest.yjcli_version})보다 낮습니다. 옛 내용으로 덮어쓰지 않도록 중단합니다.",
            "`uv tool upgrade yjcli` 후 다시 실행하세요 (그래도 진행하려면 --force).",
        ])
    draft, errors = from_args(state, mode=mode, llm=llm, platform=platform, plugin=plugin, name=name, option=option)
    if errors:
        _fail(errors)
    draft.purge = purge
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
    version_: Annotated[
        Optional[bool],
        typer.Option("--version", "-V", help="버전 출력", callback=_version_callback, is_eager=True),
    ] = None,
) -> None:
    """YJ 아키텍처 저장소 구성 도구."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


@app.command("start")
def start(
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
    purge: PurgeOpt = False,
    path: PathOpt = Path("."),
) -> None:
    """위저드 시작: 새 저장소 구성 또는 기존 구성 변경 (인자로 단계를 미리 답할 수 있음).

    기존 저장소에서는 지정하지 않은 단계가 manifest 값을 그대로 씁니다.
    """
    run(path, mode=mode, llm=llm, platform=platform, plugin=plugin, name=name, option=option,
        yes=yes, dry_run=dry_run, force=force, diff=diff, purge=purge)


@app.command("update")
def update(
    yes: YesOpt = False,
    dry_run: DryRunOpt = False,
    force: ForceOpt = False,
    diff: DiffOpt = False,
    purge: PurgeOpt = False,
    path: PathOpt = Path("."),
) -> None:
    """선택은 그대로 두고, 설치된 yjcli 의 최신 스킬·AGENTS.md 블록·관리 파일을 반영."""

    def prepare(draft: Draft, state) -> None:
        if not state.manifest:
            _fail([".yjcli/manifest.toml 이 없습니다. 먼저 `yjcli start` 로 구성하세요"])
        draft.given |= {"llms", "platforms", "plugins"}
        draft.given |= {f"names:{p}" for p in state.manifest.platforms}

    run(path, mode="update", llm=None, platform=None, plugin=None, name=None, option=None,
        yes=yes, dry_run=dry_run, force=force, diff=diff, purge=purge, prepare=prepare)


def _require_manifest(state) -> None:
    if not state.manifest:
        _fail([".yjcli/manifest.toml 이 없습니다. 먼저 `yjcli start` 로 구성하세요"])


def _keep_rest(draft: Draft, state) -> None:
    """Every step except the one being changed comes from the manifest."""
    draft.llms = list(state.manifest.llms) if draft.llms is None else draft.llms
    draft.platforms = list(state.manifest.platforms)
    draft.plugins = list(state.manifest.plugins) if draft.plugins is None else draft.plugins
    draft.given |= {"llms", "platforms", "plugins"} | {f"names:{p}" for p in state.manifest.platforms}


def _ids(values: list[str], known: dict, kind: str) -> list[str]:
    items = [v.strip() for value in values for v in value.split(",") if v.strip()]
    unknown = [v for v in items if v not in known]
    if unknown:
        _fail([f"알 수 없는 {kind}: {', '.join(unknown)} (사용 가능: {', '.join(known)})"])
    return items


def _change_plugins(ids: list[str], *, add: bool, yes: bool, dry_run: bool, purge: bool, path: Path) -> None:
    wanted = _ids(ids, PLUGIN_BY_ID, "플러그인")

    def prepare(draft: Draft, state) -> None:
        _require_manifest(state)
        current = list(state.manifest.plugins)
        if add:
            already = [p for p in wanted if p in current]
            selected = current + [p for p in wanted if p not in current]
            lacking = [r for p in wanted for r in PLUGIN_BY_ID[p].requires if r not in selected]
            if lacking:
                _fail([f"{', '.join(wanted)} 는 {', '.join(dict.fromkeys(lacking))} 가 필요합니다 — "
                       f"함께 지정하세요: yjcli plugin add {' '.join(dict.fromkeys([*lacking, *wanted]))}"])
        else:
            already = [p for p in wanted if p not in current]
            selected = [p for p in current if p not in wanted]
            dependents = [p for p in selected if any(r in wanted for r in PLUGIN_BY_ID[p].requires)]
            if dependents:
                _fail([f"{', '.join(dependents)} 가 {', '.join(wanted)} 를 필요로 합니다 — "
                       f"함께 지정하세요: yjcli plugin remove {' '.join([*wanted, *dependents])}"])
        for p in already:
            draft.notes.append(f"{p}: 이미 {'설치되어' if add else '빠져'} 있음 (변경 없음)")
        draft.plugins = [p.id for p in PLUGINS if p.id in selected]
        _keep_rest(draft, state)

    run(path, mode="update", llm=None, platform=None, plugin=None, name=None, option=None,
        yes=yes, dry_run=dry_run, force=False, purge=purge, prepare=prepare)


def _change_llms(ids: list[str], *, add: bool, yes: bool, dry_run: bool, purge: bool, path: Path) -> None:
    wanted = _ids(ids, LLM_BY_ID, "LLM")

    def prepare(draft: Draft, state) -> None:
        _require_manifest(state)
        current = list(state.manifest.llms)
        if add:
            already = [l for l in wanted if l in current]
            selected = current + [l for l in wanted if l not in current]
        else:
            already = [l for l in wanted if l not in current]
            selected = [l for l in current if l not in wanted]
            if not selected:
                _fail(["LLM 대상은 최소 1개가 남아야 합니다"])
        for l in already:
            draft.notes.append(f"{l}: 이미 {'선택되어' if add else '빠져'} 있음 (변경 없음)")
        draft.llms = [l.id for l in LLMS if l.id in selected]
        _keep_rest(draft, state)

    run(path, mode="update", llm=None, platform=None, plugin=None, name=None, option=None,
        yes=yes, dry_run=dry_run, force=False, purge=purge, prepare=prepare)


IdsArg = Annotated[list[str], typer.Argument(help="대상 id (공백/쉼표 구분)")]


@plugin_app.command("add")
def plugin_add(plugin: IdsArg, yes: YesOpt = False, dry_run: DryRunOpt = False, path: PathOpt = Path(".")) -> None:
    """플러그인 추가 (예: yjcli plugin add builder deployer)."""
    _change_plugins(plugin, add=True, yes=yes, dry_run=dry_run, purge=False, path=path)


@plugin_app.command("remove")
def plugin_remove(plugin: IdsArg, yes: YesOpt = False, dry_run: DryRunOpt = False, purge: PurgeOpt = False,
                  path: PathOpt = Path(".")) -> None:
    """플러그인 제거 (구현한 스크립트는 남김, --purge 면 함께 삭제)."""
    _change_plugins(plugin, add=False, yes=yes, dry_run=dry_run, purge=purge, path=path)


@llm_app.command("add")
def llm_add(llm: IdsArg, yes: YesOpt = False, dry_run: DryRunOpt = False, path: PathOpt = Path(".")) -> None:
    """LLM 대상 추가."""
    _change_llms(llm, add=True, yes=yes, dry_run=dry_run, purge=False, path=path)


@llm_app.command("remove")
def llm_remove(llm: IdsArg, yes: YesOpt = False, dry_run: DryRunOpt = False, purge: PurgeOpt = False,
               path: PathOpt = Path(".")) -> None:
    """LLM 대상 제거 (yj 스킬 삭제, 수정한 설정 파일은 남김 — --purge 면 함께 삭제)."""
    _change_llms(llm, add=False, yes=yes, dry_run=dry_run, purge=purge, path=path)


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
    purge: PurgeOpt = False,
    path: PathOpt = Path("."),
) -> None:
    """실행하지 않고 계획만 출력 (--dry-run 과 같음)."""
    run(path, mode=mode, llm=llm, platform=platform, plugin=plugin, name=name, option=option,
        yes=True, dry_run=True, force=force, diff=diff, purge=purge)


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
            _fail([".yjcli/manifest.toml 이 없습니다. 먼저 `yjcli start` 로 구성하세요"])
        unknown = [p for p in draft.names if p not in state.manifest.platforms]
        if unknown:
            _fail([f"구성되지 않은 플랫폼: {', '.join(unknown)} (플랫폼 추가는 `yjcli start`)"])
        draft.platforms = list(state.manifest.platforms)
        draft.given |= {"llms", "platforms", "plugins"}
        if not _interactive() and not any(g.startswith("names:") for g in draft.given):
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
    if manifest_mod.unsupported(m.yjcli_version):
        console.print(f"[yellow]  {manifest_mod.MIN_SUPPORTED} 이전 버전으로 구성된 저장소라 지원하지 않습니다 — 다시 구성하세요 (README)[/yellow]")
    elif manifest_mod.is_older(package_version(), m.yjcli_version):
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
    orphans = [rel for rel, rec in sorted(m.files.items()) if rec.orphan and (path / rel).is_file()]
    if orphans:
        console.print("[yellow]남겨 둔 파일 (주인이 없어졌지만 수정되어 있음):[/yellow]")
        for rel in orphans:
            console.print(f"  {rel}", markup=False)
        if any(not is_env_value(rel) for rel in orphans):
            console.print("  `yjcli update --purge` 로 지울 수 있습니다 (tools/secrets 의 env 값 파일 제외)", markup=False)
    stale = stale_references(path, llms=m.llms, plugins=m.plugins, platforms=list(m.platforms))
    if stale:
        console.print("[yellow]블록 밖에 남은 참조 (지금 구성에 없는 경로):[/yellow]")
        for line in stale:
            console.print(f"  {line}", markup=False)


@app.command("doctor")
def doctor() -> None:
    """패키지에 포함된 자산 점검."""
    root = data_root()
    console.print("yjcli packaged data:")
    for sub in ("templates", "plugins", "skills"):
        n = sum(1 for f in (root / sub).rglob("*") if f.is_file())
        console.print(f"  {sub}: {n} files")

"""Command line. `yjcli` alone prints help.

Every changing command runs one flow: checks → collect → validate → plan →
confirm → apply → result.
"""

from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated, Callable, Optional

import typer
from rich.console import Console

from yjcli import repo as repomod
from yjcli.apply import ApplyError, apply
from yjcli.catalog import DATA, LLM, LLMS, MANAGED, PLATFORM, PLUGIN, PLUGINS, PROTO, plugins_lacking
from yjcli.plan import Plan, build_plan
from yjcli.references import stale_references
from yjcli.repo import Repo, read_repo
from yjcli.selection import (
    Request, add_units, all_platforms, fill_defaults, gaps, parse_assignments, parse_ids, remove_units, resolve,
    service_platforms, split,
)
from yjcli.ui import report

console = Console(soft_wrap=True)
errors_out = Console(stderr=True, soft_wrap=True)


def installed_version() -> str:
    try:
        return version("yjcli")
    except PackageNotFoundError:
        return "0.0.0+local"


IDS = {"llm": ", ".join(LLM), "platform": ", ".join(PLATFORM), "plugin": ", ".join(PLUGIN)}
Llms = Annotated[Optional[list[str]], typer.Option("--llm", "-l", help=f"LLM 대상 목록 (쉼표, all). {IDS['llm']}")]
Platforms = Annotated[Optional[list[str]], typer.Option(
    "--platform", "-p", help=f"플랫폼 목록 (쉼표, all). 목록에서 빠진 플랫폼은 삭제 대상. {IDS['platform']}")]
Plugins = Annotated[Optional[list[str]], typer.Option("--plugin", help=f"플러그인 목록 (쉼표, all, none). {IDS['plugin']}")]
Names = Annotated[Optional[list[str]], typer.Option("--name", "-n", help="서비스: <platform>=a1,a2 (반복 가능)")]
ProtoLangs = Annotated[Optional[list[str]], typer.Option("--proto-lang", help="proto 언어 추가: go, dart, python (쉼표)")]
Secrets = Annotated[Optional[list[str]], typer.Option(
    "--secrets", help="tools/secrets/ 를 켤 플랫폼 목록 (쉼표, all, none). 빠진 플랫폼은 끔")]
Mode = Annotated[Optional[str], typer.Option("--mode", help="new | update (기본: 자동 감지)")]
Yes = Annotated[bool, typer.Option("--yes", "-y", help="묻지 않고 적용")]
DryRun = Annotated[bool, typer.Option("--dry-run", help="계획만 출력")]
Force = Annotated[bool, typer.Option("--force", help="yjcli 가 만들지 않은 같은 이름의 파일도 덮어씀, 낮은 버전 가드 무시")]
Diff = Annotated[bool, typer.Option("--diff", help="바뀌는 파일의 diff 도 출력")]
PathOpt = Annotated[Path, typer.Option("--path", help="저장소 루트 (기본: 현재 폴더)", file_okay=False, resolve_path=True)]
Ids = Annotated[list[str], typer.Argument(help="대상 (공백/쉼표 구분)")]

app = typer.Typer(name="yjcli", help="YJ 아키텍처 저장소를 만들고 유지합니다. 처음이면 `yjcli wizard` 로 시작하세요.",
                  context_settings={"help_option_names": ["-h", "--help"]}, add_completion=False)


def fail(messages: list[str], title: str = "error") -> None:
    for message in messages:
        errors_out.print(f"[red]{title}:[/red] {message}", highlight=False)
    raise typer.Exit(1)


def interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


# -------------------------------------------------------------------- the flow

Collect = Callable[[Request, Repo, list[str]], None]


def checks(root: Path, force: bool) -> Repo:
    root.mkdir(parents=True, exist_ok=True)
    try:
        repo = read_repo(root)
    except ValueError as exc:
        fail([str(exc)])
    m, now = repo.manifest, installed_version()
    if m and repomod.unsupported(m.version, now):
        fail([f"yjcli {m.version} 로 구성된 저장소는 지원하지 않습니다 ({repomod.MIN_SUPPORTED} 이상만, 하위 호환 없음).",
              "이전 산출물을 지우고 다시 구성하세요 — README 'Rebuilding a repo made with an older yjcli'."])
    if m and repomod.is_older(now, m.version) and not force:
        fail([f"설치된 yjcli({now})가 이 저장소를 마지막으로 구성한 버전({m.version})보다 낮습니다. 옛 내용으로 덮어쓰지 않도록 중단합니다.",
              "`uv tool upgrade yjcli` 후 다시 실행하세요 (그래도 진행하려면 --force)."])
    return repo


def _cancelled() -> None:
    console.print("취소했습니다. 아무 파일도 바꾸지 않았습니다.")
    raise typer.Exit(0)


def _remove_commands(plan: Plan) -> str:
    before, cfg = plan.before, plan.config
    out = []
    for pid, units in (before.units.items() if before else []):
        if pid not in cfg.units:
            out.append(f"yjcli platform remove {pid}")
        elif not PLATFORM[pid].contract and (gone := [u for u in units if u not in cfg.units[pid]]):
            out.append(f"yjcli service remove -n {pid}={','.join(gone)}")
    return " · ".join(out)


def run(root: Path, collect: Collect, *, kind: str, yes: bool, dry_run: bool, force: bool = False,
        diff: bool = False, mode: str | None = None) -> None:
    """kind: wizard (pick everything) | update (configuration unchanged) | change (one delta command)."""
    repo = checks(root, force)
    if mode not in (None, "new", "update"):
        fail([f"--mode 는 new 또는 update 입니다: {mode}"])
    if mode == "new" and repo.configured:
        fail(["이미 yjcli 로 구성된 저장소입니다 (.yjcli/manifest.toml)"])
    if (mode == "update" or kind != "wizard") and not repo.configured:
        fail([".yjcli/manifest.toml 이 없습니다. 먼저 `yjcli wizard` 로 구성하세요"])

    req, errors = Request(), []
    collect(req, repo, errors)
    if errors:
        fail(errors)
    fill_defaults(req, repo)

    def make_plan(r: Request) -> tuple[Plan | None, list[str]]:
        cfg, errs = resolve(r, repo)
        return (None, errs) if errs else (build_plan(cfg, repo, version=installed_version(), force=force, notes=r.notes), [])

    asking = interactive() and not yes
    diff_root = root if diff else None
    if kind == "wizard" and asking:
        from yjcli.ui.prompts import QuestionaryPrompter
        from yjcli.ui.wizard import Cancelled, run_wizard

        try:
            plan = run_wizard(req, repo, QuestionaryPrompter(), console, make_plan, dry_run=dry_run, diff_root=diff_root)
        except (Cancelled, KeyboardInterrupt):
            _cancelled()
        if dry_run:
            return
    else:
        missing = gaps(req, repo) if kind == "wizard" else []
        if not asking and not yes and not dry_run:
            missing.append("--yes (터미널이 아니면 확인 대신 --yes 또는 --dry-run 이 필요합니다)")
        if missing:
            fail(missing, "missing")
        plan, errs = make_plan(req)
        if errs:
            fail(errs)
        if kind == "update" and not plan.file_changes:
            if plan.changes and not dry_run:
                apply(plan, root)  # only the recorded version moves
            console.print(f"최신 상태입니다 (yjcli {plan.version}).")
            return
        if dry_run:
            report.summary(console, plan, details=True, diff_root=diff_root)
            return
        if asking:
            from yjcli.ui.prompts import QuestionaryPrompter
            from yjcli.ui.wizard import Cancelled

            try:
                if kind == "update":
                    from yjcli.ui.update import run_update

                    run_update(repo, plan, QuestionaryPrompter(), console)
                else:
                    report.summary(console, plan, diff_root=diff_root)
                    choices = [("cancel", "취소"), ("apply", "적용")] if plan.removals else [("apply", "적용"), ("cancel", "취소")]
                    question = "삭제가 포함되어 있습니다. 적용할까요?" if plan.removals else "적용할까요?"
                    if QuestionaryPrompter().select(question, choices) != "apply":
                        raise Cancelled
            except (Cancelled, KeyboardInterrupt):
                _cancelled()
        else:
            if plan.removes_code and not req.code_removal_ok:
                code = ", ".join(f"{r.path} ({r.why}, 파일 {r.files}개)" for r in plan.removals if r.code)
                fail([f"목록에서 빠진 항목의 코드가 삭제됩니다: {code}",
                      f"코드 삭제는 확인이 필요합니다 — 마법사에서 확인하거나 remove 명령으로 실행하세요: {_remove_commands(plan)}"])
            report.summary(console, plan, diff_root=diff_root, table_only=not diff)
    try:
        apply(plan, root)
    except ApplyError as exc:
        if exc.unrestored:
            fail([f"적용 중 실패: {exc}", "되돌리기도 일부 실패했습니다. 아래 경로를 직접 확인하세요 (git status):",
                  *[f"복원 못 함: {p}" for p in exc.unrestored]])
        fail([f"적용 중 실패: {exc}", "바꾼 것을 모두 원래대로 되돌렸습니다. 원인을 고친 뒤 다시 실행하세요."])
    report.result(console, plan)
    report.next_steps(console, plan)


# -------------------------------------------------------------------- commands


def _show_version(value: bool) -> None:
    if value:
        typer.echo(installed_version())
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context, version_: Annotated[Optional[bool], typer.Option(
        "--version", callback=_show_version, is_eager=True, help="버전 출력")] = None) -> None:
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command("help")
def help_(ctx: typer.Context, command: Annotated[Optional[list[str]], typer.Argument(
        help="명령 (예: service remove)")] = None) -> None:
    """도움말 (yjcli help <command>)."""
    context, cmd = ctx.parent, ctx.parent.command
    for name in command or []:
        sub = cmd.get_command(context, name) if hasattr(cmd, "get_command") else None
        if sub is None:
            fail([f"알 수 없는 명령: {' '.join(command)} — yjcli help 로 목록을 보세요"])
        context, cmd = type(context)(sub, info_name=name, parent=context), sub
    typer.echo(cmd.get_help(context))


def _wizard_collect(llm, platform, plugin, name, proto_lang, secrets) -> Collect:
    def collect(req: Request, repo: Repo, errors: list[str]) -> None:
        req.llms = parse_ids(llm, list(LLM), "LLM", errors)
        req.platforms = parse_ids(platform, all_platforms(), "플랫폼", errors)
        req.plugins = parse_ids(plugin, list(PLUGIN), "플러그인", errors)
        on = parse_ids(secrets, service_platforms(), "플랫폼 (--secrets)", errors)
        if on is not None:
            req.secrets = {p: p in on for p in service_platforms()}
            req.answered.add("secrets")
        for pid, names in parse_assignments(name, "--name", errors).items():
            add_units(req, repo, pid, names, errors, f"--name {pid}")
            req.answered.add(f"units:{pid}")
        if proto_lang is not None:
            add_units(req, repo, PROTO, " ".join(proto_lang), errors, "--proto-lang")
            req.answered.add(f"units:{PROTO}")
        platforms_answered = platform is not None
        if req.add:  # -n / --proto-lang bring their platform along, the others stay
            base = req.platforms if req.platforms is not None else repo.platforms()
            req.platforms = [p for p in all_platforms() if p in {*base, *req.add}]
            platforms_answered = True
        req.answered |= {s for s, given in (("llms", llm is not None), ("platforms", platforms_answered),
                                             ("plugins", plugin is not None)) if given}
    return collect


@app.command("wizard")
def wizard(llm: Llms = None, platform: Platforms = None, plugin: Plugins = None, name: Names = None,
           proto_lang: ProtoLangs = None, secrets: Secrets = None, mode: Mode = None, yes: Yes = False,
           dry_run: DryRun = False, force: Force = False, diff: Diff = False, path: PathOpt = Path(".")) -> None:
    """구성을 고르는 마법사 (새 저장소 또는 기존 저장소). 인자는 답을 미리 채우고, -y 면 묻지 않고 적용."""
    run(path, _wizard_collect(llm, platform, plugin, name, proto_lang, secrets), kind="wizard", yes=yes,
        dry_run=dry_run, force=force, diff=diff, mode=mode)


@app.command("plan")
def plan_(llm: Llms = None, platform: Platforms = None, plugin: Plugins = None, name: Names = None,
          proto_lang: ProtoLangs = None, secrets: Secrets = None, mode: Mode = None, force: Force = False,
          diff: Diff = False, path: PathOpt = Path(".")) -> None:
    """적용하지 않고 계획만 출력 (wizard --dry-run 과 같음)."""
    run(path, _wizard_collect(llm, platform, plugin, name, proto_lang, secrets), kind="wizard", yes=True,
        dry_run=True, force=force, diff=diff, mode=mode)


@app.command("update")
def update(yes: Yes = False, dry_run: DryRun = False, force: Force = False, diff: Diff = False,
           path: PathOpt = Path(".")) -> None:
    """구성은 그대로 두고 설치된 yjcli 버전을 반영 (스킬, AGENTS.md 블록, 가이드, Makefile …)."""
    run(path, lambda req, repo, errors: None, kind="update", yes=yes, dry_run=dry_run, force=force, diff=diff)


@app.command("status")
def status(path: PathOpt = Path(".")) -> None:
    """저장된 구성, 플랫폼별 옵션, 버전 차이, 로컬에서 수정한 관리 파일, 블록 밖 참조."""
    repo = read_repo(path)
    m, now = repo.manifest, installed_version()
    if not m:
        console.print("yjcli 로 구성되지 않은 폴더입니다 (.yjcli/manifest.toml 없음).")
        raise typer.Exit(1)
    console.print(f"yjcli {m.version} 로 구성됨 (설치된 버전 {now})", markup=False)
    if repomod.unsupported(m.version, now):
        console.print(f"  {repomod.MIN_SUPPORTED} 이전 버전으로 구성되어 지원하지 않습니다 — 다시 구성하세요 (README)",
                      style="yellow", markup=False)
    elif repomod.is_older(now, m.version):
        console.print("  설치된 yjcli 가 더 낮습니다 — `uv tool upgrade yjcli` 필요", style="yellow", markup=False)
    elif repomod.version_key(now) != repomod.version_key(m.version):
        console.print("  새 버전이 설치되어 있습니다 — `yjcli update` 로 반영하세요", markup=False)
    console.print(f"  LLM: {', '.join(m.llms)}", markup=False)
    console.print(f"  플러그인: {', '.join(m.plugins) or '없음'}", markup=False)
    for pid, units in m.units.items():
        option = "" if PLATFORM[pid].contract else f"  (secrets {'끔' if pid in m.secrets_off else '켬'})"
        console.print(f"  {pid}: {', '.join(units)}{option}", markup=False)
    edited = [rel for rel, rec in sorted(m.files.items()) if rec.policy == MANAGED and (path / rel).is_file()
              and repomod.sha256((path / rel).read_bytes()) != rec.sha256]
    if edited:
        console.print("로컬에서 수정한 관리 파일 (다음 업데이트 때 덮어씀 — 옮겨 둘 내용이 있는지 확인):", style="yellow", markup=False)
        for rel in edited:
            console.print(f"  ! {rel}", markup=False)
    if stale := stale_references(path, m.llms, m.plugins, list(m.units)):
        console.print("블록 밖에 남은 참조 (지금 구성에 없는 경로):", style="yellow", markup=False)
        for line in stale:
            console.print(line, markup=False)


@app.command("doctor")
def doctor() -> None:
    """패키지 자산 점검."""
    console.print("yjcli packaged data:")
    for sub in ("templates", "plugins", "skills"):
        console.print(f"  {sub}: {sum(1 for f in (DATA / sub).rglob('*') if f.is_file())} files")


# --------------------------------------------------------------- delta commands


def _group(name: str, help_text: str) -> typer.Typer:
    group = typer.Typer(help=help_text, no_args_is_help=True)
    app.add_typer(group, name=name)
    return group


llm_app = _group("llm", "LLM 대상 추가/삭제 (add, remove)")
plugin_app = _group("plugin", "플러그인 추가/삭제 (add, remove)")
platform_app = _group("platform", "플랫폼 추가/삭제 (add, remove)")
service_app = _group("service", "서비스 추가/삭제 (add, remove)")
proto_app = _group("proto", "proto 언어 추가/삭제 (add, remove)")
secrets_app = _group("secrets", "플랫폼별 tools/secrets/ 켜기/끄기 (on, off)")


def change(path: Path, collect: Collect, yes: bool, dry_run: bool) -> None:
    run(path, collect, kind="change", yes=yes, dry_run=dry_run)


def _toggled(current: list[str], ids: list[str], known: list[str], add: bool, what: str, req: Request,
             errors: list[str]) -> list[str]:
    wanted = parse_ids(ids, known, what, errors) or []
    req.notes += [f"{x}: 이미 {'있음' if add else '없음'} (변경 없음)" for x in wanted if (x in current) == add]
    chosen = set(current) | set(wanted) if add else set(current) - set(wanted)
    return [k for k in known if k in chosen]


@llm_app.command("add")
def llm_add(llm: Ids, yes: Yes = False, dry_run: DryRun = False, path: PathOpt = Path(".")) -> None:
    """LLM 대상 추가 (예: yjcli llm add codex)."""
    def collect(req, repo, errors):
        req.llms = _toggled(repo.manifest.llms, llm, list(LLM), True, "LLM", req, errors)
    change(path, collect, yes, dry_run)


@llm_app.command("remove")
def llm_remove(llm: Ids, yes: Yes = False, dry_run: DryRun = False, path: PathOpt = Path(".")) -> None:
    """LLM 대상 삭제 (스킬 폴더 전체와 지침·설정 파일. 다른 LLM이 쓰는 경로는 남김)."""
    def collect(req, repo, errors):
        req.llms = _toggled(repo.manifest.llms, llm, list(LLM), False, "LLM", req, errors)
    change(path, collect, yes, dry_run)


@plugin_app.command("add")
def plugin_add(plugin: Ids, yes: Yes = False, dry_run: DryRun = False, path: PathOpt = Path(".")) -> None:
    """플러그인 추가 (예: yjcli plugin add builder deployer)."""
    def collect(req, repo, errors):
        req.plugins = _toggled(repo.manifest.plugins, plugin, list(PLUGIN), True, "플러그인", req, errors)
        if lacking := sorted({r for rs in plugins_lacking(req.plugins).values() for r in rs}):
            errors.append(f"{', '.join(lacking)} 가 필요합니다 — 함께 지정하세요: "
                          f"yjcli plugin add {' '.join(dict.fromkeys([*lacking, *(split(plugin) or [])]))}")
    change(path, collect, yes, dry_run)


@plugin_app.command("remove")
def plugin_remove(plugin: Ids, yes: Yes = False, dry_run: DryRun = False, path: PathOpt = Path(".")) -> None:
    """플러그인 삭제 (tools/<plugin>/ 폴더 전체)."""
    def collect(req, repo, errors):
        req.plugins = _toggled(repo.manifest.plugins, plugin, list(PLUGIN), False, "플러그인", req, errors)
        if users := list(plugins_lacking(req.plugins)):
            errors.append(f"{', '.join(users)} 가 필요로 합니다 — 함께 지정하세요: "
                          f"yjcli plugin remove {' '.join([*(split(plugin) or []), *users])}")
    change(path, collect, yes, dry_run)


@service_app.command("add")
def service_add(name: Names = None, yes: Yes = False, dry_run: DryRun = False, path: PathOpt = Path(".")) -> None:
    """서비스 추가 (예: yjcli service add -n backend=a3)."""
    def collect(req, repo, errors):
        if not name:
            errors.append("--name <platform>=<이름들> 이 필요합니다")
        for pid, names in parse_assignments(name, "--name", errors).items():
            if pid not in repo.platforms():
                errors.append(f"--name {pid}: 구성되지 않은 플랫폼입니다 (yjcli platform add {pid} -n {pid}=…)")
            else:
                add_units(req, repo, pid, names, errors, f"--name {pid}")
    change(path, collect, yes, dry_run)


@service_app.command("remove")
def service_remove(name: Names = None, yes: Yes = False, dry_run: DryRun = False, path: PathOpt = Path(".")) -> None:
    """서비스 삭제 (서비스 폴더, env, 빌드 결과까지. 마지막 서비스면 플랫폼도 삭제)."""
    def collect(req, repo, errors):
        if not name:
            errors.append("--name <platform>=<이름들> 이 필요합니다")
        for pid, names in parse_assignments(name, "--name", errors).items():
            remove_units(req, repo, pid, names, errors, f"--name {pid}")
        req.code_removal_ok = True
    change(path, collect, yes, dry_run)


@platform_app.command("add")
def platform_add(platform: Annotated[str, typer.Argument(help="플랫폼")], name: Names = None,
                 proto_lang: ProtoLangs = None,
                 secrets: Annotated[bool, typer.Option("--secrets/--no-secrets", help="tools/secrets/ 사용 (기본 켬)")] = True,
                 yes: Yes = False, dry_run: DryRun = False, path: PathOpt = Path(".")) -> None:
    """플랫폼 추가 (예: yjcli platform add frontend -n frontend=f1 · yjcli platform add proto --proto-lang go)."""
    def collect(req, repo, errors):
        if platform not in PLATFORM:
            errors.append(f"알 수 없는 플랫폼: {platform} (사용 가능: {IDS['platform']})")
            return
        if platform in repo.platforms():
            req.notes.append(f"{platform}: 이미 있음 (서비스 추가는 yjcli service add)")
        req.platforms = [*repo.platforms(), platform]
        if PLATFORM[platform].contract:
            add_units(req, repo, platform, " ".join(proto_lang or []), errors, "--proto-lang")
            return
        for pid, names in parse_assignments(name, "--name", errors).items():
            if pid == platform:
                add_units(req, repo, pid, names, errors, f"--name {pid}")
            else:
                errors.append(f"--name {pid}: {platform} 의 서비스만 지정할 수 있습니다")
        if platform not in repo.platforms():
            req.secrets[platform] = secrets
    change(path, collect, yes, dry_run)


@platform_app.command("remove")
def platform_remove(platform: Ids, yes: Yes = False, dry_run: DryRun = False, path: PathOpt = Path(".")) -> None:
    """플랫폼 삭제 (플랫폼 폴더 전체, 서비스·도구 스크립트·env·빌드 결과·스킬까지)."""
    def collect(req, repo, errors):
        req.platforms = _toggled(repo.platforms(), platform, all_platforms(), False, "플랫폼", req, errors)
        for pid in set(repo.platforms()) - set(req.platforms):
            if users := [p for p in req.platforms if pid in PLATFORM[p].requires]:
                errors.append(f"{', '.join(users)} 가 {pid} 를 사용하므로 뺄 수 없습니다 — 함께 지정하세요: "
                              f"yjcli platform remove {' '.join([*users, pid])}")
        req.code_removal_ok = True
    change(path, collect, yes, dry_run)


@proto_app.command("add")
def proto_add(lang: Ids, yes: Yes = False, dry_run: DryRun = False, path: PathOpt = Path(".")) -> None:
    """proto 언어 추가 (예: yjcli proto add python). proto 가 없으면 함께 추가."""
    def collect(req, repo, errors):
        req.platforms = [*repo.platforms(), PROTO]
        add_units(req, repo, PROTO, " ".join(lang), errors, "proto add")
    change(path, collect, yes, dry_run)


@proto_app.command("remove")
def proto_remove(lang: Ids, yes: Yes = False, dry_run: DryRun = False, path: PathOpt = Path(".")) -> None:
    """proto 언어 삭제 (proto/dist/<언어>/)."""
    def collect(req, repo, errors):
        remove_units(req, repo, PROTO, " ".join(lang), errors, "proto remove")
    change(path, collect, yes, dry_run)


def _secrets(platforms: list[str], on: bool) -> Collect:
    def collect(req, repo, errors):
        for pid in parse_ids(platforms, service_platforms(), "플랫폼", errors) or []:
            if pid not in repo.platforms():
                errors.append(f"{pid}: 구성되지 않은 플랫폼입니다")
            req.secrets[pid] = on
    return collect


@secrets_app.command("on")
def secrets_on(platform: Ids, yes: Yes = False, dry_run: DryRun = False, path: PathOpt = Path(".")) -> None:
    """tools/secrets/ 켜기 (그 플랫폼의 모든 서비스에 env 파일 생성)."""
    change(path, _secrets(platform, True), yes, dry_run)


@secrets_app.command("off")
def secrets_off(platform: Ids, yes: Yes = False, dry_run: DryRun = False, path: PathOpt = Path(".")) -> None:
    """tools/secrets/ 끄기 (tools/secrets/<platform>/ 폴더 삭제)."""
    change(path, _secrets(platform, False), yes, dry_run)

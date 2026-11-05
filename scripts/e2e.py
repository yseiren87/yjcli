"""End-to-end scenarios: each case runs yjcli into sandbox/<case>/ and checks the result.

    scripts/e2e.sh              all cases (also removes sandbox folders of cases that no longer exist)
    scripts/e2e.sh -k remove    cases whose name contains "remove"
    scripts/e2e.sh -v           print the log of failed cases

Cases are grouped by area: 1x create, 2x add, 3x update,
4x remove, 5x arguments. Every case starts from an empty folder and leaves its
result in sandbox/ for inspection (`11-create-everything` selects everything).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SANDBOX = REPO / "sandbox"
CASES: list[tuple[str, str, object]] = []
DOWN, LEFT = "j", "\x1b[D"


def case(name: str, title: str):
    def register(fn):
        CASES.append((name, title, fn))
        return fn
    return register


@dataclass
class Out:
    code: int
    text: str


@dataclass
class Case:
    name: str
    dir: Path
    failures: list[str] = field(default_factory=list)
    log: list[str] = field(default_factory=list)
    checks: int = 0

    # ------------------------------------------------------------- running
    def _run(self, cmd: list[str], expect: int | None, cwd: Path, label: str, stdin=subprocess.DEVNULL) -> Out:
        env = {**os.environ, "COLUMNS": "220", "NO_COLOR": "1", "TERM": "dumb"}
        proc = subprocess.run(cmd, cwd=cwd, stdin=stdin, capture_output=True, text=True, env=env)
        out = proc.stdout + proc.stderr
        self.log.append(f"$ {label}  (exit {proc.returncode})\n{out}")
        if expect is not None:
            self.check(proc.returncode == expect, f"`{label}` exit {proc.returncode}, expected {expect}")
        return Out(proc.returncode, out)

    def yjcli(self, *args: str, expect: int | None = 0) -> Out:
        return self._run([sys.executable, "-m", "yjcli", *args, "--path", str(self.dir)], expect, REPO,
                         "yjcli " + " ".join(args))

    def bare(self, *args: str, expect: int | None = 0) -> Out:
        """yjcli without --path (help and friends)."""
        return self._run([sys.executable, "-m", "yjcli", *args], expect, REPO, "yjcli " + " ".join(args))

    def sh(self, command: str, expect: int | None = 0) -> Out:
        return self._run(["bash", "-c", command], expect, self.dir, command)

    def keys(self, kind: str, *presses: str, expect: int = 0) -> Out:
        """Drive `wizard` / `update` interactively with scripted key presses."""
        return self._run([sys.executable, "-c", KEYS, str(self.dir), kind, *presses], expect, REPO,
                         f"{kind} (keys: {' | '.join(map(repr, presses))})")

    # -------------------------------------------------------------- checks
    def check(self, ok: bool, message: str) -> None:
        self.checks += 1
        if not ok:
            self.failures.append(message)

    def has(self, *paths: str) -> None:
        for p in paths:
            self.check((self.dir / p).exists(), f"missing: {p}")

    def hasnt(self, *paths: str) -> None:
        for p in paths:
            self.check(not (self.dir / p).exists(), f"should not exist: {p}")

    def text(self, path: str) -> str:
        f = self.dir / path
        return f.read_text(encoding="utf-8") if f.is_file() else ""

    def contains(self, path: str, *needles: str) -> None:
        text = self.text(path)
        for n in needles:
            self.check(n in text, f"{path} should contain {n!r}")

    def lacks(self, path: str, *needles: str) -> None:
        text = self.text(path)
        for n in needles:
            self.check(n not in text, f"{path} should not contain {n!r}")

    def says(self, out: Out, *needles: str) -> None:
        for n in needles:
            self.check(n in out.text, f"output should contain {n!r}")

    def quiet(self, out: Out) -> None:
        """Nothing changed."""
        if "최신 상태입니다" not in out.text:
            self.says(out, "+ 생성 0개", "~ 변경 0개", "- 삭제 0개")

    def executable(self, *paths: str) -> None:
        for p in paths:
            self.check((self.dir / p).is_file() and bool((self.dir / p).stat().st_mode & 0o100), f"not executable: {p}")

    # ------------------------------------------------------------- helpers
    def write(self, path: str, content: str) -> None:
        f = self.dir / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(content)

    def implement(self, script: str, function: str, body: str) -> None:
        """Replace the body of `function` in a generated .sh (`name() {`) or .ps1 (`function Name(...) {`)."""
        pattern = (rf"^function {re.escape(function)}(\([^)]*\))? *\{{[^\n]*\n.*?^\}}" if script.endswith(".ps1")
                   else rf"^{re.escape(function)}\(\) \{{[^\n]*\n.*?^\}}")
        head = (lambda m: f"function {function}{m.group(1) or ''} {{") if script.endswith(".ps1") else (lambda m: f"{function}() {{")
        f = self.dir / script
        text, n = re.subn(pattern, lambda m: f"{head(m)}\n{body}\n}}", f.read_text(), count=1, flags=re.S | re.M)
        self.check(n == 1, f"{script}: function {function} not found")
        f.write_text(text)

    def manifest_set(self, pattern: str, replacement: str) -> None:
        f = self.dir / ".yjcli/manifest.toml"
        text, n = re.subn(pattern, replacement, f.read_text(), flags=re.M)
        self.check(n >= 1, f"manifest: {pattern!r} not found")
        f.write_text(text)

    def pretend_older(self, rel: str, content: str) -> None:
        """Make a managed file look like an older yjcli wrote it (content and recorded hash)."""
        self.write(rel, content)
        digest = hashlib.sha256((self.dir / rel).read_bytes()).hexdigest()
        self.manifest_set(rf'^("{re.escape(rel)}" = \{{ policy = "managed", sha256 = ")[0-9a-f]+', rf"\g<1>{digest}")


KEYS = r'''
import sys
from pathlib import Path
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
import yjcli.cli as cli

root, kind, presses = Path(sys.argv[1]), sys.argv[2], sys.argv[3:]
cli.interactive = lambda: True
with create_pipe_input() as pipe:
    for p in presses:
        pipe.send_text(p)
    with create_app_session(input=pipe, output=DummyOutput()):
        collect = cli._wizard_collect(None, None, None, None, None, None) if kind == "wizard" else (lambda *a: None)
        try:
            cli.run(root, collect, kind=kind, yes=False, dry_run=False)
        except Exception as exc:  # typer.Exit outside an app
            if not hasattr(exc, "exit_code"):
                raise
            sys.exit(exc.exit_code)
'''

TOOLS = ("runner", "builder", "deployer")


# ============================================================== 1x create


@case("10-create-code-only", "생성: 플러그인 없이 코드·env·에이전트 연결만, 다시 실행하면 변경 없음")
def _(c: Case):
    out = c.yjcli("wizard", "-l", "claude", "-n", "backend=a1,a2", "--plugin", "none", "-y")
    c.says(out, "완료 — 적용 결과", "평문으로 커밋됩니다")
    c.has("backend/a1/apps", "backend/a1/domains", "backend/a2/.env.examples", "tools/secrets/backend/a1/.env.local-dev",
          "tools/secrets/backend/a2/.env.production", "AGENTS.md", "CLAUDE.md", ".claude/settings.json",
          ".claude/skills/yj-arch-core/SKILL.md", ".claude/skills/yj-backend/SKILL.md", ".gitignore", ".yjcli/manifest.toml")
    c.hasnt("Makefile", "make.ps1", "tools/runner", ".cursor")
    c.contains("tools/secrets/backend/a1/.env.local-dev", "NAME=a1", "PORT=8080")
    c.contains("CLAUDE.md", "@AGENTS.md")
    c.contains("AGENTS.md", "<!-- yjcli:rules -->", "<!-- yjcli:skills -->", "<!-- yjcli:layout -->", "`backend/**`")
    c.contains(".gitignore", "# >>> yjcli:managed", "!tools/secrets/**", "/dist/")
    c.contains(".claude/skills/yj-arch-core/SKILL.md", "No run/build/deploy tooling")
    c.contains(".yjcli/manifest.toml", 'llms = ["claude"]', 'plugins = []', '[platforms."backend"]', 'services = ["a1", "a2"]')
    c.quiet(c.yjcli("wizard", "-y"))
    c.quiet(c.yjcli("update", "-y"))


@case("11-create-everything", "생성: 모든 LLM·플랫폼·플러그인·proto 언어 (sandbox 에서 직접 살펴보는 용도)")
def _(c: Case):
    names = ["backend=api", "backend-msa=user", "backend-ssr=site", "frontend=web", "mobile-app=app", "pc-app=desk",
             "cli=tool", "browser-extension=ext,native_host", "scheduler=jobs"]
    args = [a for n in names for a in ("-n", n)]
    c.yjcli("wizard", "-l", "all", *args, "--proto-lang", "go,dart,python", "--plugin", "all", "-y")
    for llm_dir in (".cursor/skills", ".claude/skills", ".agents/skills"):
        for skill in ("yj-arch-core", "yj-proto", "yj-backend", "yj-backend-msa", "yj-backend-ssr", "yj-frontend",
                      "yj-mobile-app", "yj-pc-app", "yj-cli", "yj-browser-extension", "yj-scheduler"):
            c.has(f"{llm_dir}/{skill}/SKILL.md")
    for n in names:
        pid = n.split("=")[0]
        for tool in TOOLS:
            c.has(f"tools/{tool}/{pid}/{tool}.sh", f"tools/{tool}/{pid}/{tool}.ps1")
            c.executable(f"tools/{tool}/{pid}/{tool}.sh")
    c.has("proto/dist/go/go.mod", "proto/dist/dart/pubspec.yaml", "proto/dist/python/pyproject.toml",
          "tools/builder/proto/builder.sh", "tools/builder/proto/builder.ps1")
    c.hasnt("tools/runner/proto", "tools/deployer/proto", "tools/secrets/proto")
    leftovers = [str(f.relative_to(c.dir)) for f in c.dir.rglob("*") if f.is_file() and ".yjcli" not in f.parts
                 and re.search(r"\{\{[^}]*\}\}", f.read_text(errors="ignore"))]
    c.check(not leftovers, f"unrendered template tags in {leftovers[:5]}")
    c.contains("Makefile", "PLATFORMS := backend backend-msa backend-ssr frontend mobile-app pc-app cli browser-extension scheduler",
               "proto-build:")
    c.contains(".gitignore", "!proto/dist/")
    c.contains("AGENTS.md", "`browser-extension/native_*/**`", "`tools/deployer/`")
    c.contains(".yjcli/manifest.toml", 'languages = ["dart", "go", "python"]')
    c.quiet(c.yjcli("update", "-y"))


@case("12-create-platform-shapes", "생성: 플랫폼별 폴더·스택 파일·env 종류 (frontend, SSR views, native_*, proto 이름)")
def _(c: Case):
    c.dir.mkdir(parents=True, exist_ok=True)
    root = c.dir / "My Shop"
    out = c._run([sys.executable, "-m", "yjcli", "wizard", "-l", "codex", "-n", "frontend=web", "-n", "backend-ssr=site",
                  "-n", "browser-extension=popup,native_host", "-n", "backend-msa=user", "--proto-lang", "go,python",
                  "--plugin", "none", "-y", "--path", str(root)], 0, REPO, "wizard (repo folder 'My Shop')")
    sub = "My Shop/"
    c.has(sub + "frontend/web/package.json", sub + "frontend/web/vite.config.ts", sub + "frontend/web/src",
          sub + "backend-ssr/site/views", sub + "browser-extension/popup/manifest.json", sub + "browser-extension/popup/src/popup",
          sub + "browser-extension/native_host/apps")
    c.hasnt(sub + "browser-extension/native_host/manifest.json")
    c.contains(sub + "frontend/web/package.json", '"name": "web"')
    c.contains(sub + "frontend/web/vite.config.ts", "__APP_NAME__")
    c.contains(sub + "tools/secrets/frontend/web/.env.local-dev", "PORT=5173")
    c.contains(sub + "tools/secrets/browser-extension/native_host/.env.local-dev", "NAME=native_host")
    c.lacks(sub + "tools/secrets/browser-extension/popup/.env.local-dev", "PORT=")
    c.contains(sub + "proto/dist/go/go.mod", "module my-shop/proto")
    c.contains(sub + "proto/dist/python/pyproject.toml", 'name = "my-shop-proto"', "my_shop_proto")
    c.contains(sub + ".agents/skills/yj-arch-core/SKILL.md", "`listen`", "`worker`", "`browser-extension/native_*`")


@case("13-create-tools-run", "생성: runner·builder·deployer 스크립트가 실제로 동작 (동시 실행, env, dist, BUILD_INFO)")
def _(c: Case):
    c.yjcli("wizard", "-l", "claude", "-n", "backend=a1,a2", "--plugin", "all", "-y")
    c.implement("tools/runner/backend/runner.sh", "run_one", '  echo "hello from $NAME on $PORT"')
    out = c.sh("make backend")
    c.says(out, "[a1] hello from a1 on 8080", "[a2] hello from a2 on 8080")
    c.says(c.sh("make backend NAME=a2"), "[a2] hello")
    c.implement("tools/runner/backend/runner.sh", "run_one", '  [ "$1" = a2 ] && exit 3; sleep 5')
    c.check(c.sh("make backend", expect=None).code != 0, "a failing service must fail the runner")

    out = c.sh("make backend-deploy-development", expect=None)
    c.check(out.code != 0, "deploy without a build must fail")
    c.says(out, "make backend-build-development")
    c.implement("tools/builder/backend/builder.sh", "build_one", '  echo built > "$OUT/app"; test -f "$ENV_FILE"')
    c.sh("make backend-build-development")
    c.has("dist/backend/a1/app", "dist/backend/a2/BUILD_INFO")
    c.contains("dist/backend/a1/BUILD_INFO", "environment=development", "service=a1")
    c.implement("tools/deployer/backend/deployer.sh", "deploy_one", '  echo "deployed $1 from $(basename "$IN")"')
    c.says(c.sh("make backend-deploy-production", expect=None), "built for development", "deployed a1")
    # an added environment works once every service has its env file
    c.write("tools/secrets/backend/a1/.env.staging", "NAME=a1\nPORT=8080\n")
    out = c.sh("make backend-build-staging", expect=None)
    c.check(out.code != 0, "a missing env file must stop the build")
    c.says(out, "missing tools/secrets/backend/a2/.env.staging")
    c.write("tools/secrets/backend/a2/.env.staging", "NAME=a2\nPORT=8080\n")
    c.sh("make backend-build-staging")
    c.contains("dist/backend/a2/BUILD_INFO", "environment=staging")
    c.says(c.sh("make backend-deploy-staging"), "deployed a2")
    c.check(c.sh("make backend-build-local-dev", expect=None).code != 0, "local-dev is for local runs only")
    c.says(c.sh("make nope-build-staging", expect=None), "unknown target")
    c.implement("tools/builder/backend/builder.sh", "build_one", '  echo half > "$OUT/app"; exit 1')
    c.check(c.sh("make backend-build-production NAME=a1", expect=None).code != 0, "a failing build must fail")
    c.hasnt("dist/backend/a1")  # no half-written output


@case("14-create-no-secrets", "생성: secrets 끈 플랫폼은 env 없이 스크립트 생성·실행, 가이드·스킬에 표시")
def _(c: Case):
    out = c.yjcli("wizard", "-l", "claude", "-n", "backend=a1", "-n", "frontend=f1", "--plugin", "all",
                  "--secrets", "frontend", "-y")
    c.says(out, "backend 끔", "frontend 켬")
    c.hasnt("tools/secrets/backend")
    c.has("tools/secrets/frontend/f1/.env.local-dev")
    c.contains(".yjcli/manifest.toml", '[platforms."backend"]\nservices = ["a1"]\nsecrets = false')
    for tool in TOOLS:
        c.lacks(f"tools/{tool}/backend/{tool}.sh", "SECRETS_DIR")
        c.lacks(f"tools/{tool}/backend/{tool}.ps1", "SecretsDir")
        c.contains(f"tools/{tool}/frontend/{tool}.sh", "SECRETS_DIR")
        c.contains(f"tools/{tool}/GUIDE.md", "No `tools/secrets/` for `backend`")
    c.contains(".claude/skills/yj-arch-core/SKILL.md", "No `tools/secrets/` for `backend`")
    c.contains("AGENTS.md", "`frontend` only")
    c.implement("tools/runner/backend/runner.sh", "run_one", '  echo "ran $1"')
    c.says(c.sh("make backend"), "[a1] ran a1")
    c.yjcli("wizard", "--secrets", "none", "-y")
    c.lacks(".gitignore", "!tools/secrets/")
    c.contains(".claude/skills/yj-arch-core/SKILL.md", "does not use `tools/secrets/`")


@case("15-create-wizard", "생성: 대화형 마법사 (← 로 되돌아가기, 의존성 자동 체크, 옵션)")
def _(c: Case):
    out = c.keys("wizard",
                 " " + DOWN + " \r",       # LLM: cursor + claude
                 "\r",                     # platforms: nothing → stays (minimum 1)
                 " " + DOWN * 3 + " \r",   # platforms: backend + frontend
                 LEFT,                     # plugins: ← back to platforms
                 "\r",                     # platforms: keep
                 DOWN + " \r",             # plugins: runner (default) + builder
                 "a1, a2\r",               # backend names
                 LEFT,                     # backend options: ← back to names
                 "\r",                     # backend names: keep
                 " \r",                    # backend options: secrets off
                 "\r",                     # frontend names: empty → refused, stays
                 "f1\r",                   # frontend names
                 "\r",                     # frontend options: keep
                 "\r")                     # confirm: 적용
    c.says(out, "완료 — 적용 결과")
    c.has("backend/a1/apps", "backend/a2/apps", "frontend/f1/package.json", ".cursor/skills/yj-backend/SKILL.md",
          ".claude/skills/yj-frontend/SKILL.md", "tools/builder/frontend/builder.sh", "tools/secrets/frontend/f1/.env.local-dev")
    c.hasnt("tools/secrets/backend", "tools/deployer")
    c.contains(".yjcli/manifest.toml", 'llms = ["cursor", "claude"]', 'plugins = ["runner", "builder"]', "secrets = false")


@case("16-create-powershell", "생성: make.ps1 와 .ps1 스크립트 (pwsh 가 있을 때만)")
def _(c: Case):
    if not shutil.which("pwsh"):
        c.check(True, "")
        return
    c.yjcli("wizard", "-l", "claude", "-n", "backend=a1,a2", "--plugin", "all", "-y")
    ps = lambda *a, expect=0: c._run(["pwsh", "-NoProfile", "-File", "make.ps1", *a], expect, c.dir, "make.ps1 " + " ".join(a))
    c.implement("tools/runner/backend/runner.ps1", "Invoke-RunOne", '    Write-Output "hello from $env:NAME"')
    c.says(ps("backend"), "[a1] hello from a1", "[a2] hello from a2")
    c.implement("tools/builder/backend/builder.ps1", "Invoke-BuildOne", '    Set-Content (Join-Path $Out "app") "built"')
    ps("backend-build-development", "NAME=a1")
    c.contains("dist/backend/a1/BUILD_INFO", "environment=development")
    c.implement("tools/deployer/backend/deployer.ps1", "Invoke-DeployOne", '    Write-Output "deployed $Name"')
    c.says(ps("backend-deploy-development", "NAME=a1"), "deployed a1")
    c.write("tools/secrets/backend/a1/.env.staging", "NAME=a1\n")
    ps("backend-build-staging", "NAME=a1")
    c.contains("dist/backend/a1/BUILD_INFO", "environment=staging")


# ================================================================= 2x add


@case("20-add-commands", "추가: service·platform·plugin·llm·proto·secrets 명령, 기존 이름은 안내만")
def _(c: Case):
    c.yjcli("wizard", "-l", "claude", "-n", "backend=a1", "--plugin", "runner", "-y")
    c.write("tools/secrets/backend/a1/.env.local-dev", "NAME=mine\n")
    out = c.yjcli("service", "add", "-n", "backend=a1,a2", "-y")
    c.says(out, "backend: a1: 이미 있음 (변경 없음)", "(+ backend/a2)")
    c.has("backend/a2/apps", "tools/secrets/backend/a2/.env.local-dev")
    c.contains("tools/secrets/backend/a1/.env.local-dev", "NAME=mine")
    c.contains("tools/runner/GUIDE.md", "`a1`, `a2`")
    c.says(c.yjcli("service", "add", "-n", "frontend=f", "-y", expect=1), "구성되지 않은 플랫폼")

    c.yjcli("platform", "add", "frontend", "-n", "frontend=f1", "--no-secrets", "-y")
    c.has("frontend/f1/package.json", "tools/runner/frontend/runner.sh", ".claude/skills/yj-frontend/SKILL.md")
    c.hasnt("tools/secrets/frontend")
    c.contains("Makefile", "PLATFORMS := backend frontend")

    c.says(c.yjcli("plugin", "add", "deployer", "-y", expect=1), "builder 가 필요합니다", "yjcli plugin add builder deployer")
    c.yjcli("plugin", "add", "builder", "deployer", "-y")
    c.has("tools/builder/frontend/builder.sh", "tools/deployer/GUIDE.md")
    c.contains(".claude/skills/yj-arch-core/SKILL.md", "### Deployer")
    c.says(c.yjcli("plugin", "add", "runner", "-y"), "runner: 이미 있음 (변경 없음)")

    c.yjcli("llm", "add", "codex", "-y")
    c.has(".agents/skills/yj-frontend/SKILL.md")
    c.contains("AGENTS.md", ".agents/skills")

    c.yjcli("proto", "add", "go", "-y")
    c.has("proto/dist/go/go.mod", ".claude/skills/yj-proto/SKILL.md", "tools/builder/proto/builder.sh")
    c.contains(".gitignore", "!proto/dist/")
    c.says(c.sh("make proto-build"), "no .proto")
    c.yjcli("secrets", "on", "frontend", "-y")
    c.has("tools/secrets/frontend/f1/.env.local-dev")
    c.says(c.yjcli("wizard", "-n", "backend=a3", "-y"), "(+ backend/a3)")
    c.has("backend/a3/apps", "frontend/f1")


@case("21-add-wizard-existing", "추가·삭제: 기존 저장소에서 마법사, 체크=추가 · 해제=삭제, 삭제가 있으면 기본은 취소")
def _(c: Case):
    c.yjcli("wizard", "-l", "claude", "-n", "backend=a1,a2", "-n", "frontend=f1", "--plugin", "runner", "-y")
    flow = ["\r", "\r", "\r",           # LLM, platforms, plugins: keep
            DOWN + " \r",               # backend services: uncheck a2
            "b3\r",                     # backend new names
            "\r",                       # backend options: keep
            "\r", "\r",                 # frontend services, names: keep
            " \r"]                      # frontend options: secrets off
    out = c.keys("wizard", *flow, "\r")  # confirm: the default is 취소 when something is removed
    c.says(out, "삭제:", "backend/a2", "tools/secrets/frontend", "취소했습니다")
    c.has("backend/a2", "tools/secrets/frontend/f1/.env.local-dev")
    c.hasnt("backend/b3")
    out = c.keys("wizard", *flow, DOWN + "\r")  # confirm: 적용
    c.says(out, "완료 — 적용 결과", "(+ backend/b3)", "(- backend/a2)")
    c.hasnt("backend/a2", "tools/secrets/backend/a2", "tools/secrets/frontend")
    c.has("backend/b3/apps", "tools/secrets/backend/b3/.env.local-dev", "frontend/f1/package.json")
    c.contains(".yjcli/manifest.toml", 'services = ["a1", "b3"]', "secrets = false")


# ============================================================== 3x update


@case("30-update-refresh", "업데이트: 관리 파일은 로컬 수정까지 덮어쓰고 보고, 블록만 갱신, seed 는 그대로")
def _(c: Case):
    c.yjcli("wizard", "-l", "claude", "-n", "backend=a1", "--plugin", "runner", "-y")
    c.write("tools/runner/GUIDE.md", c.text("tools/runner/GUIDE.md") + "\nlocal tweak\n")
    c.pretend_older(".claude/skills/yj-backend/SKILL.md", "old skill\n")
    agents = c.text("AGENTS.md").replace("- Name: `<name>`", "- Name: `shop`")
    start, end = agents.index("<!-- yjcli:layout -->"), agents.index("<!-- /yjcli:layout -->") + len("<!-- /yjcli:layout -->")
    c.write("AGENTS.md", agents[:start] + "my layout notes" + agents[end:])
    c.write(".gitignore", c.text(".gitignore") + "\nmy-local/\n")
    c.implement("tools/runner/backend/runner.sh", "run_one", "  exec mine")
    c.manifest_set(r'^("tools/runner/backend/runner.sh" = \{ policy = "seed", sha256 = "[0-9a-f]+", template = ")[0-9a-f]+',
                   r"\g<1>0000")  # the starting template "changed"
    st = c.yjcli("status")
    c.says(st, "! tools/runner/GUIDE.md", "다음 업데이트 때 덮어씀")
    out = c.yjcli("update", "-y")
    c.says(out, "tools/runner/GUIDE.md (로컬 수정 덮어씀)", ".claude/skills/yj-backend/SKILL.md",
           "프로젝트 메모는 AGENTS.md 에 적으세요",
           "<!-- yjcli:layout --> 블록이 없어 파일 끝에 다시 넣었습니다",
           "tools/runner/backend/runner.sh: 시작 템플릿이 바뀌었습니다", "tools/runner/GUIDE.md 기준으로 확인하세요")
    c.lacks("tools/runner/GUIDE.md", "local tweak")
    c.lacks(".claude/skills/yj-backend/SKILL.md", "old skill")
    c.contains("AGENTS.md", "- Name: `shop`", "my layout notes", "<!-- yjcli:layout -->")
    c.contains(".gitignore", "my-local/", "# >>> yjcli:managed")
    c.contains("tools/runner/backend/runner.sh", "exec mine")
    c.quiet(c.yjcli("update", "-y"))


@case("31-update-seeds", "업데이트: 새 seed 는 생성, 지운 seed 는 다시 만들지 않음, 스킬 추가 규칙, 만든 적 없는 파일은 --force")
def _(c: Case):
    c.write("CLAUDE.md", "hand made\n")
    out = c.yjcli("wizard", "-l", "claude", "-n", "backend=a1", "--plugin", "runner", "-y")
    c.says(out, "! CLAUDE.md: yjcli 가 만들지 않은 파일이 이미 있음")
    c.contains("CLAUDE.md", "hand made")
    c.yjcli("wizard", "--force", "-y")
    c.contains("CLAUDE.md", "@AGENTS.md")
    (c.dir / "tools/runner/backend/runner.ps1").unlink()  # opt out
    c.manifest_set(r'^"tools/secrets/backend/a1/\.env\.production" = .*\n', "")  # a seed this repo never had
    (c.dir / "tools/secrets/backend/a1/.env.production").unlink()
    c.yjcli("update", "-y")
    c.hasnt("tools/runner/backend/runner.ps1")
    c.has("tools/secrets/backend/a1/.env.production")
    c.write(".yjcli/skills/yj-backend.md", "- Use PostgreSQL via modules/db only.\n")
    c.write(".yjcli/skills/yj-typo.md", "x\n")
    out = c.yjcli("update", "-y")
    c.says(out, "yj-typo.md: 알 수 없는 스킬 이름")
    c.contains(".claude/skills/yj-backend/SKILL.md", "## Project-specific additions", "modules/db only")
    c.lacks(".claude/skills/yj-arch-core/SKILL.md", "Project-specific additions")


@case("32-update-wizard", "업데이트: 마법사 (현황 → 바뀌는 내용 → 확인), 중단하면 그대로, 바뀐 게 없으면 최신 상태")
def _(c: Case):
    c.yjcli("wizard", "-l", "claude", "-n", "backend=a1", "--plugin", "runner", "-y")
    c.says(c.keys("update"), "최신 상태입니다")
    c.write("tools/runner/GUIDE.md", c.text("tools/runner/GUIDE.md") + "\nlocal tweak\n")
    c.pretend_older(".claude/skills/yj-backend/SKILL.md", "old skill\n")
    out = c.keys("update", DOWN * 2 + "\r")  # status: 중단
    c.says(out, "1. 현황", "로컬에서 수정한 관리 파일 (덮어써집니다)", "프로젝트 메모는 AGENTS.md 로", "취소했습니다")
    c.contains("tools/runner/GUIDE.md", "local tweak")
    out = c.keys("update", "\r", "\r", "\r")  # 계속 → 다음 → 적용
    c.says(out, "2. 바뀌는 내용", "1개 갱신", "tools/runner", "완료 — 적용 결과")
    c.lacks("tools/runner/GUIDE.md", "local tweak")
    c.quiet(c.yjcli("update", "-y"))


@case("33-update-version-guard", "업데이트: 더 낮은 yjcli 는 거부(--force), MIN_SUPPORTED 미만 저장소는 지원 안 함")
def _(c: Case):
    c.yjcli("wizard", "-l", "claude", "-n", "backend=a1", "--plugin", "none", "-y")
    c.manifest_set(r'^yjcli_version = ".*"', 'yjcli_version = "99.0.0"')
    for args in (("update", "-y"), ("wizard", "-y"), ("service", "add", "-n", "backend=a2", "-y")):
        c.says(c.yjcli(*args, expect=1), "보다 낮습니다", "uv tool upgrade yjcli")
    c.hasnt("backend/a2")
    c.says(c.yjcli("status"), "설치된 yjcli 가 더 낮습니다")
    c.yjcli("update", "--force", "-y")
    c.lacks(".yjcli/manifest.toml", '"99.0.0"')
    c.manifest_set(r'^yjcli_version = ".*"', 'yjcli_version = "0.4.3"')
    for args in (("update", "-y"), ("update", "--force", "-y")):
        c.says(c.yjcli(*args, expect=1), "지원하지 않습니다", "Rebuilding a repo made with an older yjcli")
    c.says(c.yjcli("status"), "지원하지 않습니다")


# ============================================================== 4x remove


@case("40-remove-commands", "삭제: llm·plugin·service·platform·proto·secrets 를 폴더째 삭제, 공유 경로는 남김")
def _(c: Case):
    c.yjcli("wizard", "-l", "cursor,claude", "-n", "backend=a1,a2", "-n", "frontend=f1", "-n", "backend-msa=m1",
            "--proto-lang", "go,dart", "--plugin", "runner,builder", "-y")
    c.write(".cursor/skills/my-skill/SKILL.md", "mine\n")
    c.write(".cursor/rules/team.mdc", "rule\n")
    c.write("tools/runner/backend/helper.sh", "# added by the project\n")
    c.write("dist/backend/a2/app", "bin")
    c.write("tools/secrets/frontend/f1/.env.production", "API_KEY=real\n")

    out = c.yjcli("service", "remove", "-n", "backend=a2", "--dry-run")
    c.says(out, "삭제:", "backend/a2", "tools/secrets/backend/a2", "dist/backend/a2", "서비스 backend/a2")
    c.has("backend/a2")
    out = c.yjcli("service", "remove", "-n", "backend=a2", "-y")
    c.says(out, "- 폴더 삭제  backend/a2", "(- backend/a2)")
    c.hasnt("backend/a2", "tools/secrets/backend/a2", "dist/backend/a2")
    c.says(c.yjcli("service", "remove", "-n", "backend=zz", "-y", expect=1), "backend 에 없는 서비스입니다: zz")

    c.yjcli("llm", "remove", "cursor", "-y")
    c.hasnt(".cursor/skills")
    c.has(".cursor/rules/team.mdc", "AGENTS.md", ".claude/skills/yj-backend/SKILL.md")
    c.says(c.yjcli("llm", "remove", "claude", "-y", expect=1), "최소 1개")

    c.says(c.yjcli("plugin", "remove", "runner", "-y"), "- 폴더 삭제  tools/runner")
    c.hasnt("tools/runner")
    c.has("Makefile")  # builder still uses it

    c.says(c.yjcli("proto", "remove", "dart", "-y"), "- 폴더 삭제  proto/dist/dart")
    c.hasnt("proto/dist/dart")
    c.says(c.yjcli("platform", "remove", "proto", "-y", expect=1), "backend-msa 가 proto 를 사용")
    c.yjcli("platform", "remove", "backend-msa", "proto", "-y")
    c.hasnt("backend-msa", "proto", "tools/builder/backend-msa", "tools/builder/proto", ".claude/skills/yj-proto",
            ".claude/skills/yj-backend-msa")
    c.lacks(".gitignore", "!proto/dist/")

    c.says(c.yjcli("secrets", "off", "frontend", "-y"), "- 폴더 삭제  tools/secrets/frontend")
    c.hasnt("tools/secrets/frontend")
    c.contains(".yjcli/manifest.toml", "secrets = false")

    c.yjcli("service", "remove", "-n", "frontend=f1", "-y")  # the last service takes the platform
    c.hasnt("frontend", "tools/builder/frontend", ".claude/skills/yj-frontend")
    c.lacks(".yjcli/manifest.toml", '[platforms."frontend"]')
    c.yjcli("plugin", "remove", "builder", "-y")
    c.hasnt("Makefile", "make.ps1", "tools/builder")
    c.has("backend/a1/apps", "tools/secrets/backend/a1/.env.local-dev")
    c.quiet(c.yjcli("update", "-y"))


@case("41-remove-references", "삭제: 블록 밖에 남은 참조를 줄 번호와 함께 알림 (고치지는 않음)")
def _(c: Case):
    c.yjcli("wizard", "-l", "claude", "-n", "backend=a1,a2", "--plugin", "runner,builder", "-y")
    c.write("AGENTS.md", c.text("AGENTS.md") + "\n- Run: `make backend NAME=a2` (tools/runner/GUIDE.md)\n")
    out = c.yjcli("plugin", "remove", "runner", "-y")
    line = next(i for i, l in enumerate(c.text("AGENTS.md").splitlines(), 1) if "- Run:" in l)
    c.says(out, "블록 밖에 남은 참조", f"AGENTS.md:{line} — `tools/runner`")
    c.contains("AGENTS.md", "tools/runner/GUIDE.md")
    c.says(c.yjcli("status"), "블록 밖에 남은 참조")


@case("42-remove-guard", "삭제: 목록 교체 인자로 코드가 지워지면 -y 를 거부하고 remove 명령 안내")
def _(c: Case):
    c.yjcli("wizard", "-l", "claude", "-n", "backend=a1", "-n", "frontend=f1", "--plugin", "runner", "-y")
    out = c.yjcli("wizard", "-p", "frontend", "-y", expect=1)
    c.says(out, "목록에서 빠진 항목의 코드가 삭제됩니다", "yjcli platform remove backend")
    c.has("backend/a1")
    c.yjcli("wizard", "--plugin", "none", "-y")  # not code: --yes is the consent
    c.hasnt("tools/runner")


# =========================================================== 5x arguments


@case("50-args-validation", "인자: 문제는 한 번에 모두, 빠진 값 안내, 터미널이 아니면 --yes 필요, 아무것도 쓰지 않음")
def _(c: Case):
    out = c.yjcli("wizard", "-l", "claude,gpt", "-n", "backend=-bad", "-n", "proto=go", "--plugin", "deployer,x", "-y",
                  expect=1)
    c.says(out, "알 수 없는 LLM: gpt", "알 수 없는 플러그인: x", "'-bad'", "proto 는 서비스가 아니라 언어를 고릅니다")
    out = c.yjcli("wizard", "-p", "backend", expect=1)
    c.says(out, "missing: --llm", "missing: --plugin", "missing: --name backend=", "missing: --yes")
    c.says(c.yjcli("wizard", "-l", "claude", "-n", "backend=a1", "--plugin", "deployer", "-y", expect=1),
           "deployer 는 builder 가 필요합니다")
    c.says(c.yjcli("wizard", "--mode", "x", "-y", expect=1), "--mode")
    c.says(c.yjcli("update", "-y", expect=1), "먼저 `yjcli wizard` 로 구성하세요")
    c.check(not c.dir.exists() or not any(c.dir.iterdir()), "nothing may be written")
    c.yjcli("wizard", "-l", "claude", "-n", "backend=a1", "--plugin", "none", "-y")
    c.says(c.yjcli("wizard", "--mode", "new", "-y", expect=1), "이미 yjcli 로 구성된 저장소")


@case("51-args-dry-run", "인자: --dry-run · plan · --diff 는 아무것도 쓰지 않음")
def _(c: Case):
    out = c.yjcli("plan", "-l", "claude", "-n", "backend=a1", "--plugin", "runner")
    c.says(out, "계획 요약 — 신규 설치", "+ 생성")
    c.check(not c.dir.exists() or not any(c.dir.iterdir()), "plan must not write")
    c.yjcli("wizard", "-l", "claude", "-n", "backend=a1", "--plugin", "runner", "-y")
    c.write("tools/runner/GUIDE.md", c.text("tools/runner/GUIDE.md") + "tweak\n")
    out = c.yjcli("update", "--dry-run", "--diff")
    c.says(out, "-tweak", "로컬 수정 덮어씀")
    c.contains("tools/runner/GUIDE.md", "tweak")


@case("52-args-help-status", "인자: yjcli · help · help <command> · status · doctor · --version")
def _(c: Case):
    for args in ((), ("help",)):
        c.says(c.bare(*args), "Usage:", "wizard", "update", "platform", "service", "proto", "secrets", "help")
    c.says(c.bare("help", "service", "remove"), "yjcli service remove", "--name", "마지막 서비스면 플랫폼도 삭제")
    c.says(c.bare("help", "nope", expect=1), "알 수 없는 명령: nope")
    c.says(c.bare("doctor"), "templates:", "skills:")
    c.check(bool(re.search(r"\d+\.\d+", c.bare("--version").text)), "--version prints a version")
    c.says(c.yjcli("status", expect=1), "구성되지 않은 폴더")
    c.yjcli("wizard", "-l", "claude", "-n", "backend=a1", "--plugin", "none", "--secrets", "none", "-y")
    c.says(c.yjcli("status"), "LLM: claude", "backend: a1  (secrets 끔)")


@case("53-args-rollback", "인자: 적용 중 실패하면 모두 되돌리고 매니페스트도 쓰지 않음")
def _(c: Case):
    c.write("CLAUDE.md/blocked", "a folder where a file should go\n")  # writing CLAUDE.md will fail
    out = c.yjcli("wizard", "-l", "claude", "-n", "backend=a1", "--plugin", "runner", "-y", "--force", expect=1)
    c.says(out, "적용 중 실패", "모두 원래대로 되돌렸습니다")
    c.hasnt("backend", "AGENTS.md", "tools", ".yjcli/manifest.toml")
    c.has("CLAUDE.md/blocked")


# ============================================================== runner


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-k", help="only cases whose name contains this")
    parser.add_argument("-v", action="store_true", help="print the log of failed cases")
    args = parser.parse_args()
    selected = [x for x in CASES if not args.k or args.k in x[0]]
    if not selected:
        print(f"no case matches {args.k!r}")
        return 1
    SANDBOX.mkdir(exist_ok=True)
    if not args.k:
        names = {name for name, _, _ in CASES}
        for stale in SANDBOX.iterdir():
            if stale.is_dir() and stale.name not in names:
                shutil.rmtree(stale)
    passed = checks = 0
    for name, title, fn in selected:
        folder = SANDBOX / name
        shutil.rmtree(folder, ignore_errors=True)
        c = Case(name, folder)
        try:
            fn(c)
        except Exception:
            c.failures.append("crashed:\n" + traceback.format_exc())
        checks += c.checks
        ok = not c.failures
        passed += ok
        print(f"{'PASS' if ok else 'FAIL'}  {name:<28} {title}  ({c.checks} checks)")
        for f in c.failures:
            print(f"        - {f}")
        if not ok and args.v:
            for entry in c.log:
                print("\n".join("        | " + line for line in entry.splitlines()))
    print(f"\n{passed}/{len(selected)} cases passed, {checks} checks. sandbox: {SANDBOX}")
    return 0 if passed == len(selected) else 1


if __name__ == "__main__":
    sys.exit(main())

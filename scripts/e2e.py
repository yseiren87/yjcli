"""End-to-end scenarios: run yjcli into sandbox/<case>/ and check the result.

Usage (from the repo root):
    scripts/e2e.sh                 # all cases
    scripts/e2e.sh -k builder      # cases whose name contains "builder"
    scripts/e2e.sh -v              # also print yjcli output of failed cases
    scripts/e2e.sh -k fullspec     # only regenerate sandbox/24-fullspec (everything selected)

Every case starts from an empty folder under sandbox/ (git-ignored) and is
left there afterwards so the generated tree can be inspected by hand. A full run
(no -k) also removes sandbox folders that no longer belong to a case.
"""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

REPO = Path(__file__).resolve().parent.parent
SANDBOX = REPO / "sandbox"

CASES: list[tuple[str, str, Callable[["Case"], None]]] = []


def case(name: str, title: str):
    def register(fn):
        CASES.append((name, title, fn))
        return fn

    return register


@dataclass
class Result:
    code: int
    out: str


@dataclass
class Case:
    name: str
    dir: Path
    failures: list[str] = field(default_factory=list)
    log: list[str] = field(default_factory=list)
    checks: int = 0

    # ----------------------------------------------------------------- running
    def yjcli(self, *args: str, expect: int | None = 0) -> Result:
        if args and args[0].startswith("-"):
            args = ("start", *args)  # options only → the wizard command
        cmd = [sys.executable, "-m", "yjcli", *args, "--path", str(self.dir)]
        return self._run(cmd, expect, cwd=REPO, label="yjcli " + " ".join(args))

    def sh(self, command: str, expect: int | None = 0) -> Result:
        return self._run(["bash", "-c", command], expect, cwd=self.dir, label=command)

    def _run(self, cmd: list[str], expect: int | None, *, cwd: Path, label: str) -> Result:
        env = {**os.environ, "COLUMNS": "200", "NO_COLOR": "1", "TERM": "dumb"}
        proc = subprocess.run(cmd, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, text=True, env=env)
        out = proc.stdout + proc.stderr
        self.log.append(f"$ {label}\n{out}")
        if expect is not None:
            self.check(proc.returncode == expect, f"`{label}` exit {proc.returncode} (expected {expect})")
        return Result(proc.returncode, out)

    # ------------------------------------------------------------------ checks
    def check(self, ok: bool, message: str) -> bool:
        self.checks += 1
        if not ok:
            self.failures.append(message)
        return ok

    def exists(self, *paths: str) -> None:
        for p in paths:
            self.check((self.dir / p).exists(), f"missing: {p}")

    def absent(self, *paths: str) -> None:
        for p in paths:
            self.check(not (self.dir / p).exists(), f"should not exist: {p}")

    def read(self, path: str) -> str:
        f = self.dir / path
        return f.read_text(encoding="utf-8") if f.is_file() else ""

    def contains(self, path: str, *needles: str) -> None:
        text = self.read(path)
        for n in needles:
            self.check(n in text, f"{path}: expected to contain {n!r}")

    def lacks(self, path: str, *needles: str) -> None:
        text = self.read(path)
        for n in needles:
            self.check(n not in text, f"{path}: should not contain {n!r}")

    def output_has(self, result: Result, *needles: str) -> None:
        for n in needles:
            self.check(n in result.out, f"output should contain {n!r}")

    def executable(self, *paths: str) -> None:
        for p in paths:
            f = self.dir / p
            self.check(f.is_file() and bool(f.stat().st_mode & stat.S_IXUSR), f"not executable: {p}")

    def tree(self, sub: str = ".") -> list[str]:
        base = self.dir / sub
        return sorted(str(p.relative_to(base)) for p in base.rglob("*") if p.is_file())

    def fake_older_package(self, rel: str, content: str) -> None:
        """Make a managed file look like an older yjcli wrote it (content + recorded hash)."""
        import hashlib
        import re

        f = self.dir / rel
        f.write_text(content)
        digest = hashlib.sha256(f.read_bytes()).hexdigest()
        manifest = self.dir / ".yjcli/manifest.toml"
        text = manifest.read_text()
        pattern = r'("%s" = \{ policy = "managed", sha256 = ")[0-9a-f]+' % re.escape(rel)
        updated, n = re.subn(pattern, r"\g<1>" + digest, text)
        self.check(n == 1, f"manifest record for {rel} not found")
        manifest.write_text(updated)

    def set_manifest_version(self, version: str) -> None:
        manifest = self.dir / ".yjcli/manifest.toml"
        lines = [f'yjcli_version = "{version}"' if l.startswith("yjcli_version") else l
                 for l in manifest.read_text().splitlines()]
        manifest.write_text("\n".join(lines) + "\n")

    def pwsh(self, *args: str, expect: int | None = 0) -> Result:
        cmd = ["pwsh", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "make.ps1", *args]
        return self._run(cmd, expect, cwd=self.dir, label="make.ps1 " + " ".join(args))

    def implement_ps1(self, script: str, function: str, body: str) -> None:
        """Replace the stub body of `function` in a generated .ps1 skeleton."""
        import re

        f = self.dir / script
        text, n = re.subn(r"^function %s(\([^)]*\))? *\{\n.*?^\}" % re.escape(function),
                          lambda m: f"function {function}{m.group(1) or ''} {{\n{body}\n}}", f.read_text(),
                          count=1, flags=re.S | re.M)
        self.check(n == 1, f"{script}: function {function} not found")
        f.write_text(text)

    def implement(self, script: str, function: str, body: str) -> None:
        """Replace the stub body of `function` in a generated .sh skeleton."""
        import re

        f = self.dir / script
        text, n = re.subn(r"^%s\(\) \{\n.*?^\}" % re.escape(function),
                          lambda _: f"{function}() {{\n{body}\n}}", f.read_text(), count=1, flags=re.S | re.M)
        self.check(n == 1, f"{script}: function {function} not found")
        f.write_text(text)


def no_changes(c: Case, r: Result) -> None:
    c.output_has(r, "+ 생성 0개", "~ 변경 0개", "- 삭제 0개")


# =============================================================================
# Cases
# =============================================================================


@case("01-code-only", "플러그인 없이: 코드 + 환경 값(tools/secrets)만 생성")
def _(c: Case):
    r = c.yjcli("-l", "claude", "-n", "backend=a1,a2", "--plugin", "none", "-y")
    c.output_has(r, "평문으로 커밋")
    c.exists("backend/a1/apps", "backend/a1/services", "backend/a1/domains", "backend/a1/modules",
             "backend/a1/.env.examples", "backend/a2/.env.examples",
             "tools/secrets/backend/a1/.env.local-dev", "tools/secrets/backend/a2/.env.production",
             "AGENTS.md", "CLAUDE.md", ".gitignore", ".yjcli/manifest.toml", ".claude/settings.json",
             ".claude/skills/yj-arch-core/SKILL.md", ".claude/skills/yj-backend/SKILL.md")
    c.absent("tools/runner", "tools/builder", "tools/deployer", "Makefile", "make.ps1", "make.bat",
             "backend/scripts", "backend/a1/Dockerfile", "backend/a1/.env.local-dev", "backend/proto",
             ".cursor", ".agents", "Diff.md", "TOOLS.md")
    c.check((c.dir / "CLAUDE.md").read_text() == "@AGENTS.md\n", "CLAUDE.md should only import AGENTS.md")
    c.contains(".claude/skills/yj-arch-core/SKILL.md", "holds code and env", "### Secrets")
    c.lacks(".claude/skills/yj-arch-core/SKILL.md", "tools/runner", "tools/builder", "tools/deployer")
    c.contains("AGENTS.md", "| `backend/**` | `yj-backend` |", "<!-- yjcli:layout -->", "`tools/secrets/<platform>/<service>/`")
    c.lacks("AGENTS.md", "Makefile", "tools/runner", "Diff.md", "TOOLS.md", "frontend")
    c.contains(".yjcli/manifest.toml", 'plugins = []', 'services = ["a1", "a2"]')
    c.contains(".gitignore", "!tools/secrets/**", "/dist/")


@case("02-runner", "runner: 플랫폼별 runner.sh/ps1 + GUIDE, make 로 동시 실행")
def _(c: Case):
    c.yjcli("-l", "cursor,claude", "-n", "backend=a1 a2", "-n", "frontend=f1", "--plugin", "runner", "-y")
    c.exists("Makefile", "make.ps1", "tools/runner/GUIDE.md",
             "tools/runner/backend/runner.sh", "tools/runner/backend/runner.ps1",
             "tools/runner/frontend/runner.sh", "tools/runner/frontend/runner.ps1",
             "tools/secrets/backend/a1/.env.local-dev", "tools/secrets/backend/a1/.env.development",
             "tools/secrets/backend/a1/.env.production", "tools/secrets/frontend/f1/.env.local-dev",
             "frontend/f1/package.json", "frontend/f1/vite.config.ts", "frontend/f1/src",
             ".cursor/skills/yj-frontend/SKILL.md", ".claude/skills/yj-frontend/SKILL.md")
    c.absent("tools/builder", "tools/deployer", "make.bat", "tools/runner/run.sh", "tools/runner/run.bat",
             "backend/a1/Dockerfile", "backend/a1/.env.local-dev", "backend/scripts")
    c.executable("tools/runner/backend/runner.sh", "tools/runner/frontend/runner.sh")
    c.contains("tools/secrets/backend/a1/.env.local-dev", "NAME=a1", "PORT=8080")
    c.lacks("tools/secrets/backend/a1/.env.local-dev", "RUN_COMMAND")
    c.contains("tools/secrets/frontend/f1/.env.local-dev", "NAME=f1", "PORT=5173")
    c.contains("frontend/f1/package.json", '"name": "f1"')
    c.contains("Makefile", "PLATFORMS := backend frontend", 'tools/runner/$@/runner.sh')
    c.lacks("Makefile", "-build-", "-deploy-", "{{")
    c.contains("make.ps1", '$Platforms = "backend frontend"', '$tool = "runner"')
    c.lacks("make.ps1", "-build-", "{{")
    c.contains("tools/runner/GUIDE.md", "- `backend/`: `a1`, `a2`", "Ctrl+C", "More than one script")
    c.contains("tools/runner/backend/runner.sh", "read tools/runner/GUIDE.md", "helper scripts")
    c.contains("AGENTS.md", "`tools/runner/`", "`tools/secrets/<platform>/<service>/`", "`.cursor/skills/` (Cursor)")
    c.contains(".claude/skills/yj-arch-core/SKILL.md", "### Runner", "### Secrets", "`listen`: `backend` (PORT 8080), `frontend` (PORT 5173)")
    c.lacks(".claude/skills/yj-arch-core/SKILL.md", "### Builder", "### Deployer")

    r = c.sh("make frontend NAME=f1", expect=None)
    c.check(r.code != 0 and "not implemented — read tools/runner/GUIDE.md" in r.out, "unimplemented runner should fail with a hint")
    c.implement("tools/runner/backend/runner.sh", "run_one", '  echo "hello-$NAME-${PORT:-none}"')
    one = c.sh("make backend NAME=a1")
    c.output_has(one, "[a1] hello-a1-8080", "running 1 service(s)")
    both = c.sh("make backend")
    c.output_has(both, "[a1] hello-a1-8080", "[a2] hello-a2-8080", "running 2 service(s)")
    c.implement("tools/runner/backend/runner.sh", "run_one",
                '  if [ "$1" = a2 ]; then exit 3; fi\n  exec sleep 30')
    fail = c.sh("make backend", expect=None)
    c.check(fail.code != 0 and "[a2] exited with 3" in fail.out, "a failing service should stop the run with its code")
    (c.dir / "tools/secrets/backend/a2/.env.local-dev").unlink()
    c.implement("tools/runner/backend/runner.sh", "run_one", '  echo "ran $1"')
    skip = c.sh("make backend")
    c.output_has(skip, "[a2] skipped", "[a1] ran a1")

    c.sh("git init -q . && touch backend/a1/.env.local-dev")
    c.sh("git check-ignore -q tools/secrets/backend/a1/.env.local-dev", expect=1)  # tracked
    c.sh("git check-ignore -q backend/a1/.env.local-dev", expect=0)  # ignored
    c.sh("git check-ignore -q backend/a1/.env.examples", expect=1)


@case("03-builder-deployer", "builder/deployer: 플랫폼별 스크립트, dist/<platform>/<service>, 배포는 dist 만 사용")
def _(c: Case):
    c.yjcli("-l", "codex", "-n", "backend=a1", "-n", "frontend=f1", "-n", "cli=tool", "-n", "scheduler=jobs",
            "--plugin", "all", "-y")
    for p in ("backend", "frontend", "cli", "scheduler"):
        for tool in ("runner", "builder", "deployer"):
            c.exists(f"tools/{tool}/{p}/{tool}.ps1")
            c.executable(f"tools/{tool}/{p}/{tool}.sh")
    c.exists("tools/builder/GUIDE.md", "tools/deployer/GUIDE.md",
             ".agents/skills/yj-cli/SKILL.md", ".agents/skills/yj-scheduler/SKILL.md")
    c.absent("backend/a1/Dockerfile", "backend/a1/.dockerignore", "frontend/f1/Dockerfile", "tools/builder/steps",
             "tools/builder/build-common.sh", ".claude", ".cursor", "CLAUDE.md")
    c.contains("tools/builder/backend/builder.sh", "build_proto")  # backend may opt into proto/
    c.lacks("tools/builder/frontend/builder.sh", "build_proto")
    c.contains("Makefile", "BUILD_TARGETS", "DEPLOY_TARGETS", "tools/builder/$$p/builder.sh", "tools/deployer/$$p/deployer.sh")
    c.contains(".agents/skills/yj-arch-core/SKILL.md", "### Builder", "### Deployer", "--env-file")
    c.contains("tools/deployer/GUIDE.md", "--env-file", "never builds", "More than one script")
    c.contains("tools/builder/GUIDE.md", "dist/<platform>/<service>/", "BUILD_INFO")

    r = c.sh("make backend-build-development NAME=a1", expect=None)
    c.check(r.code != 0 and "builder for backend/a1 is not implemented" in r.out, "unimplemented build should fail")
    c.absent("dist/backend/a1")  # failed build leaves no output
    r = c.sh("make backend-deploy-development NAME=a1", expect=None)
    c.check(r.code != 0 and "run: make backend-build-development NAME=a1" in r.out, "deploy without dist should fail with a hint")
    r = c.sh("make backend-build-staging", expect=None)
    c.check(r.code != 0, "unknown environment target should fail")

    c.implement("tools/builder/backend/builder.sh", "build_one", '  echo "built $1 for $ENVIRONMENT" > "$OUT/app"')
    c.implement("tools/builder/frontend/builder.sh", "build_one", '  echo ok > "$OUT/index.html"')
    c.implement("tools/deployer/backend/deployer.sh", "deploy_one", '  echo "shipping $(cat app) env=$ENV_FILE"')
    c.sh("make backend-build-development")
    c.contains("dist/backend/a1/app", "built a1 for development")
    c.contains("dist/backend/a1/BUILD_INFO", "platform=backend", "service=a1", "environment=development", "version=unknown")
    (c.dir / "dist/backend/a1/stale").write_text("x")
    c.sh("make backend-build-development NAME=a1")
    c.absent("dist/backend/a1/stale")  # emptied before each build
    c.sh("make frontend-build-production")
    c.contains("dist/frontend/f1/BUILD_INFO", "version=0.1.0", "environment=production")
    r = c.sh("make backend-deploy-development NAME=a1")
    c.output_has(r, "shipping built a1 for development env=" + str(c.dir.resolve() / "tools/secrets/backend/a1/.env.development"))
    r = c.sh("make backend-deploy-production")
    c.output_has(r, "warning: dist/backend/a1 was built for development, deploying to production")
    c.sh("git init -q . && git check-ignore -q dist/backend/a1/app", expect=0)


@case("04-plugin-dependencies", "deployer 는 builder 필요 · builder 만 선택 시 빌드 타깃만")
def _(c: Case):
    r = c.yjcli("-l", "claude", "-n", "backend=a1", "--plugin", "runner,deployer", "-y", expect=1)
    c.output_has(r, "deployer 는 builder 가 필요합니다")
    c.check(not c.dir.exists() or not any(c.dir.iterdir()), "nothing should be written")
    c.yjcli("-l", "claude", "-n", "backend=a1", "--plugin", "builder", "-y")
    c.exists("Makefile", "make.ps1", "tools/builder/backend/builder.sh", "tools/secrets/backend/a1/.env.production")
    c.absent("tools/runner", "tools/deployer")
    c.lacks("Makefile", "tools/runner", "DEPLOY_TARGETS")
    c.contains("Makefile", "BUILD_TARGETS")
    r = c.sh("make backend NAME=a1", expect=None)
    c.check("[a1]" not in r.out and "Nothing to be done" in r.out, "runner target must not exist without runner")
    r = c.yjcli("--plugin", "deployer", "-y", expect=1)
    c.output_has(r, "deployer 는 builder 가 필요합니다")
    c.yjcli("--plugin", "builder,deployer", "-y")
    c.exists("tools/deployer/backend/deployer.sh", "tools/deployer/GUIDE.md")


@case("05-backend-variants", "backend / backend-msa(proto 고정) / backend-ssr(views) / proto 옵션")
def _(c: Case):
    c.yjcli("-l", "claude", "-n", "backend=api", "-n", "backend-msa=user,order", "-n", "backend-ssr=web",
            "-o", "backend=proto", "--plugin", "none", "-y")
    c.exists("backend/proto/.gitkeep", "backend/proto/dist/.gitkeep", "backend-msa/proto/dist/.gitkeep",
             "backend-ssr/web/views", "backend-msa/user/apps", "backend-msa/order/apps",
             ".claude/skills/yj-backend/SKILL.md", ".claude/skills/yj-backend-msa/SKILL.md",
             ".claude/skills/yj-backend-ssr/SKILL.md")
    c.absent("backend-ssr/proto", "backend/api/views", ".claude/skills/yj-backend-service")
    c.contains("AGENTS.md", "| `backend-msa/**` | `yj-backend-msa` |", "| `backend-ssr/**` | `yj-backend-ssr` |",
               "| `backend-msa/proto/` | gRPC/protobuf contract |", "| `backend/proto/` | (optional) gRPC/protobuf contract |")
    c.contains(".claude/skills/yj-backend-ssr/SKILL.md", "## Server templating", "## Roles", "## Optional: gRPC transport")
    c.contains(".claude/skills/yj-backend/SKILL.md", "## Roles", "## Optional: gRPC transport",
               "editing `backend/**`, `browser-extension/native_*/**`.")
    c.lacks(".claude/skills/yj-backend-msa/SKILL.md", "Optional: server templating", "backend/proto")
    c.contains(".claude/skills/yj-backend-msa/SKILL.md", "backend-msa/proto/dist/{lang}")
    r = c.yjcli("-l", "claude", "-n", "backend-msa=x", "-o", "backend-msa=no-proto", "--plugin", "none",
                "--mode", "update", "-y", expect=1)
    c.output_has(r, "고정 옵션")


@case("06-browser-extension", "browser-extension: native_* 는 백엔드 구조 + yj-backend")
def _(c: Case):
    c.yjcli("-l", "claude", "-n", "browser-extension=ext native_host", "--plugin", "none", "-y")
    c.exists("browser-extension/ext/manifest.json", "browser-extension/ext/src/background",
             "browser-extension/native_host/apps", "browser-extension/native_host/.env.examples",
             ".claude/skills/yj-browser-extension/SKILL.md", ".claude/skills/yj-backend/SKILL.md",
             "tools/secrets/browser-extension/native_host/.env.local-dev")
    c.absent("browser-extension/native_host/manifest.json", "browser-extension/native_host/src")
    c.contains("browser-extension/native_host/.env.examples", "Optional listen port")
    agents = c.read("AGENTS.md")
    native = agents.find("`browser-extension/native_*/**`")
    other = agents.find("`browser-extension/**` (other than `native_*`)")
    c.check(0 <= native < other, "native_* routing row must come before the generic browser-extension row")


@case("07-everything", "모든 LLM·플랫폼·플러그인: 렌더링 누락/옛 이름 없음")
def _(c: Case):
    names = ["backend=a", "backend-msa=b", "backend-ssr=c", "frontend=d", "mobile-app=e", "pc-app=f",
             "cli=g", "browser-extension=h", "scheduler=i"]
    args = ["-l", "all", "--plugin", "all", "-y"]
    for n in names:
        args += ["-n", n]
    c.yjcli(*args)
    skill_sets = {d: c.tree(d) for d in (".cursor/skills", ".claude/skills", ".agents/skills")}
    c.check(len({tuple(v) for v in skill_sets.values()}) == 1, "all LLM skill dirs should hold the same skills")
    c.check(len(skill_sets[".claude/skills"]) == 10, f"expected 10 skills, got {len(skill_sets['.claude/skills'])}")
    for rel in c.tree():
        if rel.startswith(".git/"):
            continue
        text = (c.dir / rel).read_text(encoding="utf-8", errors="ignore")
        c.check("{{" not in text, f"{rel}: unrendered template tag")
        c.check("backend-service" not in text, f"{rel}: mentions removed platform backend-service")
        c.check("plugin-build" not in text, f"{rel}: mentions old plugin-build-* script")
        c.check("Diff.md" not in text and "TOOLS.md" not in text, f"{rel}: mentions removed Diff.md/TOOLS.md")
        for old in ("RUN_COMMAND", "make.bat", "build-common", "steps/docker", "--build-arg \"$key"):
            c.check(old not in text, f"{rel}: mentions removed {old}")
    for p in ("backend", "backend-msa", "backend-ssr", "frontend", "mobile-app", "pc-app", "cli", "browser-extension", "scheduler"):
        c.absent(f"{p}/scripts")
    for skill in ("yj-backend", "yj-frontend", "yj-cli", "yj-scheduler", "yj-mobile-app", "yj-pc-app",
                  "yj-browser-extension", "yj-backend-msa", "yj-backend-ssr"):
        c.lacks(f".claude/skills/{skill}/SKILL.md", "tools/", ".env.local-dev", "Do not use for")


@case("08-idempotent", "같은 선택으로 다시 실행하면 변경 없음")
def _(c: Case):
    c.yjcli("-l", "claude,cursor", "-n", "backend=a1", "-n", "frontend=f1", "--plugin", "all", "-y")
    no_changes(c, c.yjcli("-y"))
    no_changes(c, c.yjcli("-l", "claude,cursor", "--plugin", "all", "-y"))


@case("09-service-add", "서비스 추가: 새 서비스만 생성, 사용자 파일 보존, GUIDE 갱신")
def _(c: Case):
    c.yjcli("-l", "claude", "-n", "backend=a1", "--plugin", "all", "-y")
    (c.dir / "tools/secrets/backend/a1/.env.local-dev").write_text("NAME=mine\n")
    (c.dir / "backend/a1/.env.examples").write_text("# mine\nX=\n")
    c.implement("tools/builder/backend/builder.sh", "build_one", "  : mine")
    r = c.yjcli("service", "add", "-n", "backend=a3,a4", "-y")
    c.output_has(r, "backend/a3 (+)", "backend/a4 (+)")
    c.exists("backend/a3/apps", "backend/a4/.env.examples", "tools/secrets/backend/a3/.env.local-dev")
    c.contains("tools/secrets/backend/a1/.env.local-dev", "NAME=mine")
    c.contains("backend/a1/.env.examples", "# mine")
    c.contains("tools/builder/backend/builder.sh", ": mine")
    c.contains("tools/builder/GUIDE.md", "- `backend/`: `a1`, `a3`, `a4`")
    c.contains(".yjcli/manifest.toml", 'services = ["a1", "a3", "a4"]')
    r = c.yjcli("service", "add", "-n", "backend=a3", "-y")  # existing name: kept as is, not an error
    c.output_has(r, "backend: a3: 이미 있음 (변경 없음)", "+ 생성 0개", "~ 변경 0개")
    r = c.yjcli("service", "add", "-n", "frontend=x", "-y", expect=1)
    c.output_has(r, "구성되지 않은 플랫폼")


@case("10-plugin-add-remove", "플러그인 추가/제거: 안 건드린 파일은 삭제, 구현한 스크립트는 남김")
def _(c: Case):
    c.yjcli("-l", "claude", "-n", "backend=a1", "-n", "cli=t", "--plugin", "runner", "-y")
    c.yjcli("--plugin", "runner,builder", "-y")
    c.exists("tools/builder/backend/builder.sh", "tools/builder/cli/builder.ps1", "tools/builder/GUIDE.md")
    c.contains(".claude/skills/yj-arch-core/SKILL.md", "### Builder")
    c.contains("AGENTS.md", "`tools/builder/`")
    c.implement("tools/runner/backend/runner.sh", "run_one", "  exec mine")
    r = c.yjcli("--plugin", "builder", "-y")
    c.output_has(r, "- 삭제", "남겨 둔 파일 1개", "    tools/runner/backend/runner.sh", "--purge")
    c.absent("tools/runner/GUIDE.md", "tools/runner/cli", "tools/runner/backend/runner.ps1")
    c.exists("tools/runner/backend/runner.sh", "tools/secrets/backend/a1/.env.local-dev", "Makefile")
    c.lacks("Makefile", "tools/runner")
    c.lacks("AGENTS.md", "`tools/runner/`")
    c.lacks(".claude/skills/yj-arch-core/SKILL.md", "### Runner")
    c.yjcli("--plugin", "none", "-y")
    c.absent("Makefile", "make.ps1", "tools/builder")
    c.exists("tools/secrets/backend/a1/.env.local-dev", "tools/runner/backend/runner.sh")
    c.contains(".claude/skills/yj-arch-core/SKILL.md", "holds code and env")
    c.contains(".gitignore", "!tools/secrets/")


@case("11-modified-managed", "사용자가 고친 관리 파일(GUIDE.md)은 건너뛰고 --force 로만 덮어씀")
def _(c: Case):
    c.yjcli("-l", "claude", "-n", "backend=a1", "--plugin", "runner", "-y")
    guide = c.dir / "tools/runner/GUIDE.md"
    guide.write_text(guide.read_text() + "\nlocal tweak\n")
    r = c.yjcli("-y")
    c.output_has(r, "tools/runner/GUIDE.md: 사용자가 수정함")
    c.contains("tools/runner/GUIDE.md", "local tweak")
    st = c.yjcli("status")
    c.output_has(st, "! tools/runner/GUIDE.md")
    c.yjcli("--force", "-y")
    c.lacks("tools/runner/GUIDE.md", "local tweak")
    no_changes(c, c.yjcli("-y"))


@case("12-llm-remove", "LLM 제거: yj 스킬만 삭제, 사용자 스킬 보존")
def _(c: Case):
    c.yjcli("-l", "cursor,claude", "-n", "backend=a1", "--plugin", "none", "-y")
    mine = c.dir / ".cursor/skills/my-skill/SKILL.md"
    mine.parent.mkdir(parents=True)
    mine.write_text("mine\n")
    c.yjcli("-l", "claude", "-y")
    c.absent(".cursor/skills/yj-arch-core", ".cursor/skills/yj-backend")
    c.exists(".cursor/skills/my-skill/SKILL.md", ".claude/skills/yj-backend/SKILL.md")
    c.lacks("AGENTS.md", ".cursor/skills")
    c.yjcli("-l", "claude,codex", "-y")
    c.exists(".agents/skills/yj-backend/SKILL.md", "CLAUDE.md", ".cursor/skills/my-skill/SKILL.md")


@case("13-platform-remove-guard", "서비스가 있는 플랫폼은 해제 불가")
def _(c: Case):
    c.yjcli("-l", "claude", "-n", "backend=a1", "-n", "frontend=f1", "--plugin", "none", "-y")
    r = c.yjcli("-p", "frontend", "-y", expect=1)
    c.output_has(r, "서비스가 있는 플랫폼은 해제할 수 없습니다")
    c.exists("backend/a1")
    r = c.yjcli("-n", "cli=t", "-y")  # --name alone adds a platform, keeps the others
    c.exists("cli/t/apps", "backend/a1", "frontend/f1")
    c.contains(".yjcli/manifest.toml", '[platforms."cli"]', '[platforms."backend"]')


@case("14-validation", "잘못된 입력: 모든 문제를 한 번에 알림, 파일은 만들지 않음")
def _(c: Case):
    r = c.yjcli("-l", "claude", "-n", "backend=a1,-x,proto,a1", "--plugin", "none", "-y", expect=1)
    c.output_has(r, "'-x'", "'proto': 예약된 이름")
    r = c.yjcli("-l", "gpt", "-p", "nope", "--plugin", "magic", "-y", expect=1)
    c.output_has(r, "알 수 없는 LLM: gpt", "알 수 없는 플랫폼: nope", "알 수 없는 플러그인: magic")
    r = c.yjcli("-l", "claude", expect=1)
    c.output_has(r, "--platform 또는 --name", "--plugin", "--yes")
    r = c.yjcli("-l", "claude", "-p", "backend", "--plugin", "none", "-y", expect=1)
    c.output_has(r, "--name backend=")
    r = c.yjcli("-l", "claude", "-n", "backend=a1", "--plugin", "none", "--mode", "update", "-y", expect=1)
    c.output_has(r, "manifest.toml 이 없습니다")
    r = c.yjcli("-o", "frontend=proto", "-n", "frontend=f", "-l", "claude", "--plugin", "none", "-y", expect=1)
    c.output_has(r, "알 수 없는 옵션 'proto'")
    c.check(not c.dir.exists() or not any(c.dir.iterdir()), "nothing should be written on validation errors")
    c.yjcli("-l", "claude", "-n", "backend=a1", "--plugin", "none", "-y")
    r = c.yjcli("-l", "claude", "-n", "backend=a2", "--plugin", "none", "--mode", "new", "-y", expect=1)
    c.output_has(r, "이미 yjcli 로 구성된 저장소")


@case("15-dry-run", "--dry-run / plan: 파일을 만들지 않음")
def _(c: Case):
    r = c.yjcli("-l", "claude", "-n", "backend=a1", "--plugin", "all", "--dry-run")
    c.output_has(r, "+ 생성", "tools/runner/backend/runner.sh", "tools/deployer/GUIDE.md")
    c.check(not c.dir.exists() or not any(c.dir.iterdir()), "--dry-run must not write files")
    r = c.yjcli("plan", "-l", "claude", "-n", "backend=a1", "--plugin", "none")
    c.check(not any(c.dir.iterdir()), "plan must not write files")


@case("16-agents-md-user-edits", "AGENTS.md: 블록 밖 사용자 편집은 보존, 블록만 갱신")
def _(c: Case):
    c.yjcli("-l", "claude", "-n", "backend=a1", "--plugin", "none", "-y")
    agents = c.dir / "AGENTS.md"
    text = agents.read_text().replace("- Name: `<name>`", "- Name: `my-project`")
    text = text.replace("| `<path>/` | `<role>` |", "| `docs/` | team docs |")
    agents.write_text(text)
    gi = c.dir / ".gitignore"
    gi.write_text(gi.read_text() + "\nmy-local-dir/\n")
    c.yjcli("-n", "frontend=f1", "--plugin", "runner", "-y")
    c.contains("AGENTS.md", "- Name: `my-project`", "| `docs/` | team docs |", "| `frontend/**` | `yj-frontend` |",
               "`tools/runner/`")
    c.contains(".gitignore", "my-local-dir/", "!tools/secrets/**")


@case("17-wizard", "대화형 위저드: 키 입력으로 전체 흐름 (←, 의존성 자동 체크 포함)")
def _(c: Case):
    code = r'''
import sys
from pathlib import Path
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
import yjcli.cli as cli

root = Path(sys.argv[1])
DOWN, LEFT = "j", "\x1b[D"
keys = [
    " j \r",              # 1 LLM: cursor + claude
    "\r",                 # 2 platforms: nothing → stays (minimum 1)
    " jjj \r",            # 2 platforms: backend + frontend
    LEFT,                 # 3 plugins: ← back to platforms
    "\r",                 # 2 platforms: keep
    "j j k  \r",          # 3 plugins: runner default; builder on → deployer enabled, on; builder off drops deployer; builder on
    "a1, a2\r",           # 4 backend names
    "\r",                 # 4 backend options: proto off
    "\r",                 # 4 frontend names: empty → error, stays
    "f1\r",               # 4 frontend names
    "\r",                 # 5 confirm: 적용
]
cli._interactive = lambda: True
with create_pipe_input() as inp:
    for k in keys:
        inp.send_text(k)
    with create_app_session(input=inp, output=DummyOutput()):
        cli.run(root, mode=None, llm=None, platform=None, plugin=None, name=None, option=None,
                yes=False, dry_run=False, force=False)
'''
    c.dir.mkdir(parents=True, exist_ok=True)
    r = c._run([sys.executable, "-c", code, str(c.dir)], 0, cwd=REPO, label="wizard (scripted keys)")
    c.output_has(r, "완료.")
    c.exists("backend/a1/apps", "backend/a2/apps", "frontend/f1/package.json", ".cursor/skills/yj-backend/SKILL.md",
             ".claude/skills/yj-frontend/SKILL.md", "tools/runner/backend/runner.sh", "tools/builder/frontend/builder.sh",
             "tools/secrets/frontend/f1/.env.local-dev")
    c.absent("backend/proto", "tools/deployer")
    c.contains(".yjcli/manifest.toml", 'llms = ["cursor", "claude"]', 'plugins = ["runner", "builder"]')


@case("18-status-doctor", "status / doctor / 인자 없는 yjcli 는 도움말")
def _(c: Case):
    r = c._run([sys.executable, "-m", "yjcli"], 0, cwd=REPO, label="yjcli (no args)")
    c.output_has(r, "Usage:", "start", "update")
    c.check(not c.dir.exists() or not any(c.dir.iterdir()), "bare yjcli must not write anything")
    r = c.yjcli("status", expect=1)
    c.output_has(r, "구성되지 않은 폴더")
    c.yjcli("-l", "claude", "-n", "backend=a1", "--plugin", "runner", "-y")
    r = c.yjcli("status")
    c.output_has(r, "LLM: claude", "플러그인: runner", "backend: a1")
    r = c._run([sys.executable, "-m", "yjcli", "doctor"], 0, cwd=REPO, label="yjcli doctor")
    c.output_has(r, "templates:", "plugins:", "skills:")


@case("19-update-propagation", "yjcli update: 새 패키지의 스킬·AGENTS.md 규칙 블록 반영, 사용자 편집 보존")
def _(c: Case):
    c.yjcli("-l", "claude,cursor", "-n", "backend=a1", "--plugin", "runner", "-y")
    # an older yjcli wrote different skill/runner content
    c.fake_older_package(".claude/skills/yj-arch-core/SKILL.md", "OLD SKILL\n")
    c.fake_older_package("tools/runner/GUIDE.md", "old guide\n")
    # an older AGENTS.md rules block + the user's own edits outside blocks
    agents = c.dir / "AGENTS.md"
    text = agents.read_text()
    text = text.replace("- No filler, no repeated explanations.\n", "- OLD RULE\n")
    text = text.replace("- `<rule>`", "- Always write tests first.")
    text = text.replace("- Name: `<name>`", "- Name: `shop`")
    agents.write_text(text)
    r = c.yjcli("update", "--dry-run", "--diff")
    c.output_has(r, "~ 덮어쓰기", ".claude/skills/yj-arch-core/SKILL.md", "-OLD SKILL", "+name: yj-arch-core",
                 "-- OLD RULE", "+- No filler, no repeated explanations.")
    c.contains(".claude/skills/yj-arch-core/SKILL.md", "OLD SKILL")  # dry-run wrote nothing
    c.yjcli("update", "-y")
    c.contains(".claude/skills/yj-arch-core/SKILL.md", "name: yj-arch-core")
    c.lacks("tools/runner/GUIDE.md", "old guide")
    c.contains("AGENTS.md", "- No filler, no repeated explanations.", "- Always write tests first.", "- Name: `shop`")
    c.lacks("AGENTS.md", "OLD RULE")
    no_changes(c, c.yjcli("update", "-y"))


@case("20-skill-additions", "스킬 추가 규칙: .yjcli/skills/<skill>.md 가 모든 LLM 스킬에 덧붙음")
def _(c: Case):
    c.yjcli("-l", "claude,codex", "-n", "backend=a1", "--plugin", "none", "-y")
    extra = c.dir / ".yjcli/skills/yj-backend.md"
    extra.parent.mkdir(parents=True, exist_ok=True)
    extra.write_text("- Use PostgreSQL via modules/db only.\n")
    (c.dir / ".yjcli/skills/yj-typo.md").write_text("x\n")
    r = c.yjcli("update", "-y")
    c.output_has(r, "yj-typo.md: 알 수 없는 스킬 이름")
    for d in (".claude/skills", ".agents/skills"):
        c.contains(f"{d}/yj-backend/SKILL.md", "## Project-specific additions", "- Use PostgreSQL via modules/db only.",
                   "<!-- from .yjcli/skills/yj-backend.md")
        c.lacks(f"{d}/yj-arch-core/SKILL.md", "Project-specific additions")
    c.contains("AGENTS.md", "`.yjcli/skills/<skill>.md`")
    # editing the rendered skill directly is skipped and points to the additions file
    skill = c.dir / ".claude/skills/yj-backend/SKILL.md"
    skill.write_text(skill.read_text() + "\nhand edit\n")
    r = c.yjcli("update", "-y")
    c.output_has(r, "사용자가 수정함", ".yjcli/skills/yj-backend.md 에 추가 규칙을 적으세요")
    c.yjcli("update", "--force", "-y")
    extra.unlink()
    c.yjcli("update", "-y")
    c.lacks(".agents/skills/yj-backend/SKILL.md", "Project-specific additions")


@case("21-version-guard", "버전 가드: 더 낮은 yjcli 는 덮어쓰지 않음")
def _(c: Case):
    c.yjcli("-l", "claude", "-n", "backend=a1", "--plugin", "runner", "-y")
    c.set_manifest_version("99.0.0")
    for args in (("update", "-y"), ("-y",), ("service", "add", "-n", "backend=a2", "-y")):
        r = c.yjcli(*args, expect=1)
        c.output_has(r, "보다 낮습니다", "uv tool upgrade yjcli")
    c.absent("backend/a2")
    st = c.yjcli("status")
    c.output_has(st, "설치된 yjcli 가 더 낮습니다")
    c.yjcli("update", "--force", "-y")
    c.lacks(".yjcli/manifest.toml", '"99.0.0"')
    c.set_manifest_version("0.3.4")  # repo from before 0.4: no backward compatibility
    for args in (("update", "-y"), ("update", "--force", "-y"), ("-y",)):
        r = c.yjcli(*args, expect=1)
        c.output_has(r, "지원하지 않습니다", "Rebuilding a repo made with an older yjcli")
    st = c.yjcli("status")
    c.output_has(st, "지원하지 않습니다")


@case("22-new-seed-on-update", "업데이트: 처음 보는 seed 는 생성, 사용자가 지운 seed 는 다시 만들지 않음")
def _(c: Case):
    import re

    c.yjcli("-l", "claude", "-n", "backend=a1", "--plugin", "runner", "-y")
    # a repo from an older yjcli that never had this seed: no file, no record
    (c.dir / "tools/runner/backend/runner.sh").unlink()
    m = c.dir / ".yjcli/manifest.toml"
    m.write_text(re.sub(r'^"tools/runner/backend/runner\.sh" = .*\n', "", m.read_text(), flags=re.M))
    # a seed the user deleted on purpose
    (c.dir / "tools/runner/backend/runner.ps1").unlink()
    c.yjcli("update", "-y")
    c.executable("tools/runner/backend/runner.sh")
    c.absent("tools/runner/backend/runner.ps1")
    c.yjcli("update", "-y")
    c.absent("tools/runner/backend/runner.ps1")
    c.contains(".yjcli/manifest.toml", '"tools/runner/backend/runner.ps1"')


@case("23-powershell", "make.ps1 + .ps1 스켈레톤 (pwsh 가 있을 때만)")
def _(c: Case):
    if not shutil.which("pwsh"):
        c.log.append("pwsh not installed — skipped")
        return
    c.yjcli("-l", "claude", "-n", "backend-msa=user,order", "-n", "frontend=web", "--plugin", "all", "-y")
    r = c.pwsh()
    c.output_has(r, "make.ps1 <platform>-deploy-<env>", "Platforms: backend-msa frontend")
    c.pwsh("nope", expect=1)
    r = c.pwsh("frontend", expect=1)
    c.output_has(r, "[web] runner for frontend/web is not implemented - read tools/runner/GUIDE.md")
    r = c.pwsh("frontend-build-development", expect=1)
    c.output_has(r, "builder for frontend/web is not implemented")
    c.absent("dist/frontend/web")
    r = c.pwsh("frontend-deploy-production", "NAME=web", expect=1)
    c.output_has(r, "run: make.ps1 frontend-build-production NAME=web")

    c.implement_ps1("tools/runner/backend-msa/runner.ps1", "Invoke-RunOne",
                    '    Write-Output "hello $env:NAME port=$env:PORT"')
    r = c.pwsh("backend-msa")
    c.output_has(r, "[order] hello order port=8080", "[user] hello user port=8080", "running 2 service(s)")
    c.implement_ps1("tools/runner/backend-msa/runner.ps1", "Invoke-RunOne",
                    '    if ($Name -eq "order") { exit 3 }\n    Start-Sleep 30')
    r = c.pwsh("backend-msa", expect=3)
    c.output_has(r, "[order] exited with 3")

    c.implement_ps1("tools/builder/backend-msa/builder.ps1", "Invoke-BuildProto", '    Write-Host "protoc ok"')
    c.implement_ps1("tools/builder/backend-msa/builder.ps1", "Invoke-BuildOne",
                    '    Set-Content -Path (Join-Path $Out "app") -Value "built $Name for $Environment"')
    c.implement_ps1("tools/deployer/backend-msa/deployer.ps1", "Invoke-DeployOne",
                    '    Write-Host "shipping $(Get-Content app)"')
    r = c.pwsh("backend-msa-build-development")
    c.output_has(r, "protoc ok", "[build] done: order user")
    c.contains("dist/backend-msa/user/BUILD_INFO", "platform=backend-msa", "environment=development")
    r = c.pwsh("backend-msa-deploy-production", "NAME=user")
    c.output_has(r, "was built for development, deploying to production", "shipping built user for development")
    c.implement_ps1("tools/builder/backend-msa/builder.ps1", "Invoke-BuildOne",
                    '    Set-Content -Path (Join-Path $Out "half") -Value x\n    exit 4')
    c.pwsh("backend-msa-build-production", "NAME=order", expect=4)
    c.absent("dist/backend-msa/order")
    c.exists("dist/backend-msa/user/BUILD_INFO")


@case("24-fullspec", "전체 선택: 모든 LLM·플랫폼·플러그인 + 플랫폼마다 서비스 (직접 살펴보는 용도)")
def _(c: Case):
    names = {
        "backend": "api,admin", "backend-msa": "user,order", "backend-ssr": "web", "frontend": "app,console",
        "mobile-app": "mobile", "pc-app": "desktop", "cli": "tool", "browser-extension": "ext,native_host",
        "scheduler": "jobs",
    }
    args = ["-l", "all", "--plugin", "all", "-o", "backend=proto", "-o", "backend-ssr=proto", "-y"]
    for platform, value in names.items():
        args += ["-n", f"{platform}={value}"]
    c.yjcli(*args)
    for platform, value in names.items():
        for tool in ("runner", "builder", "deployer"):
            c.executable(f"tools/{tool}/{platform}/{tool}.sh")
            c.exists(f"tools/{tool}/{platform}/{tool}.ps1")
        for service in value.split(","):
            c.exists(f"{platform}/{service}/.env.examples", f"tools/secrets/{platform}/{service}/.env.local-dev")
    c.exists("backend/proto", "backend-msa/proto", "backend-ssr/proto", "browser-extension/native_host/apps",
             "Makefile", "make.ps1", "CLAUDE.md", ".cursor/skills", ".claude/skills", ".agents/skills")
    for d in (".cursor/skills", ".claude/skills", ".agents/skills"):
        c.check(len(c.tree(d)) == 10, f"{d}: expected 10 skills")
    for rel in c.tree():
        c.check("{{" not in (c.dir / rel).read_text(encoding="utf-8", errors="ignore"), f"{rel}: unrendered template tag")
    r = c.sh("make")
    c.output_has(r, "Platforms: " + " ".join(names))
    no_changes(c, c.yjcli("update", "--dry-run"))


@case("25-delta-commands", "plugin/llm add·remove, --purge, 블록 밖 참조 경고, --name 기존 서비스")
def _(c: Case):
    c.yjcli("-l", "claude,cursor", "-n", "backend=a1", "--plugin", "runner", "-y")
    # add / remove only what changes; the rest comes from the manifest
    r = c.yjcli("plugin", "add", "deployer", "-y", expect=1)
    c.output_has(r, "builder 가 필요합니다", "yjcli plugin add builder deployer")
    c.yjcli("plugin", "add", "builder", "deployer", "-y")
    c.contains(".yjcli/manifest.toml", 'plugins = ["runner", "builder", "deployer"]', 'llms = ["cursor", "claude"]')
    r = c.yjcli("plugin", "add", "runner", "-y")
    c.output_has(r, "runner: 이미 설치되어 있음 (변경 없음)", "+ 생성 0개")
    r = c.yjcli("plugin", "remove", "builder", "-y", expect=1)
    c.output_has(r, "yjcli plugin remove builder deployer")
    r = c.yjcli("plugin", "add", "nope", "-y", expect=1)
    c.output_has(r, "알 수 없는 플러그인: nope")

    # removing a plugin: untouched files go, the implemented script stays as an orphan
    c.implement("tools/runner/backend/runner.sh", "run_one", "  exec mine")
    agents = c.dir / "AGENTS.md"
    agents.write_text(agents.read_text() + "\n- Run locally: `make backend NAME=a1` (tools/runner/GUIDE.md)\n")
    r = c.yjcli("plugin", "remove", "runner", "-y")
    c.output_has(r, "남겨 둔 파일 1개", "tools/runner/backend/runner.sh", "--purge 로 함께 지울 수 있습니다",
                 "블록 밖에 남은 참조", "AGENTS.md:")
    c.absent("tools/runner/GUIDE.md", "tools/runner/backend/runner.ps1")
    c.contains(".yjcli/manifest.toml", '"tools/runner/backend/runner.sh" = { policy = "seed"', "orphan = true")
    line = next(i for i, l in enumerate(agents.read_text().splitlines(), 1) if "Run locally" in l)
    c.output_has(r, f"AGENTS.md:{line} — `tools/runner`")  # line number of the file after the run
    st = c.yjcli("status")
    c.output_has(st, "남겨 둔 파일", "tools/runner/backend/runner.sh", "yjcli update --purge", "블록 밖에 남은 참조")
    r = c.yjcli("update", "--purge", "--dry-run")
    c.output_has(r, "tools/runner/backend/runner.sh (purge)")
    c.exists("tools/runner/backend/runner.sh")
    c.yjcli("update", "--purge", "-y")
    c.absent("tools/runner")
    c.lacks(".yjcli/manifest.toml", "orphan = true")

    # env value files are never purged
    (c.dir / "tools/secrets/backend/a1/.env.production").write_text("NAME=a1\nSECRET=x\n")
    c.yjcli("service", "add", "-n", "backend=a2", "-y")
    shutil.rmtree(c.dir / "backend/a1")
    r = c.yjcli("update", "--purge", "-y")
    c.output_has(r, "tools/secrets/backend/a1/.env.production")
    c.exists("tools/secrets/backend/a1/.env.production")

    # LLMs
    c.yjcli("llm", "add", "codex", "-y")
    c.exists(".agents/skills/yj-backend/SKILL.md")
    c.yjcli("llm", "remove", "cursor", "-y")
    c.absent(".cursor/skills/yj-backend")
    r = c.yjcli("llm", "remove", "claude", "codex", "-y", expect=1)
    c.output_has(r, "최소 1개")

    # --name with an existing service is a no-op, not an error
    r = c.yjcli("-n", "backend=a2,a3", "-y")
    c.output_has(r, "backend: a2: 이미 있음 (변경 없음)", "backend/a3 (+)")
    c.exists("backend/a3/.env.examples")


# =============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-k", dest="pattern", help="run cases whose name contains this text")
    parser.add_argument("-v", "--verbose", action="store_true", help="print yjcli output of failed cases")
    args = parser.parse_args()

    selected = [c for c in CASES if not args.pattern or args.pattern in c[0]]
    if not selected:
        print(f"no case matches {args.pattern!r}")
        return 1
    SANDBOX.mkdir(exist_ok=True)
    if not args.pattern:  # drop leftovers of renamed/removed cases
        known = {name for name, _, _ in CASES}
        for stale in sorted(p for p in SANDBOX.iterdir() if p.name not in known):
            print(f"removing stale sandbox/{stale.name}")
            shutil.rmtree(stale) if stale.is_dir() else stale.unlink()
    results: list[Case] = []
    for name, title, fn in selected:
        target = SANDBOX / name
        shutil.rmtree(target, ignore_errors=True)
        c = Case(name=name, dir=target)
        try:
            fn(c)
        except Exception:  # a crash in a case is a failure, not an abort
            c.failures.append("exception:\n" + traceback.format_exc())
        status = "PASS" if not c.failures else "FAIL"
        print(f"{status}  {name:<28} {title}  ({c.checks} checks)")
        for f in c.failures:
            print(f"        - {f}")
        if c.failures and args.verbose:
            print("\n".join("        | " + line for entry in c.log for line in entry.splitlines()))
        results.append(c)

    failed = [c for c in results if c.failures]
    total = sum(c.checks for c in results)
    print()
    print(f"{len(results) - len(failed)}/{len(results)} cases passed, {total} checks. sandbox: {SANDBOX}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

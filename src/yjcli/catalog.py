"""What yjcli knows about: LLM targets, platforms, proto languages, plugins, skills."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

DATA = Path(__file__).parent / "data"


# ------------------------------------------------------------------ LLM targets


@dataclass(frozen=True)
class Llm:
    id: str
    label: str
    skills_dir: str
    instructions: str | None = None  # file that imports AGENTS.md
    settings: tuple[tuple[str, str], ...] = ()  # (template under data/templates, destination) — seeds


LLMS: tuple[Llm, ...] = (
    Llm("cursor", "Cursor", ".cursor/skills"),
    Llm("claude", "Claude Code", ".claude/skills", "CLAUDE.md", (("root/claude-settings.json", ".claude/settings.json"),)),
    Llm("codex", "Codex", ".agents/skills"),
)
LLM = {l.id: l for l in LLMS}


# -------------------------------------------------------------------- platforms


@dataclass(frozen=True)
class Variant:
    """Service shape chosen by a name prefix (browser-extension `native_*`)."""

    prefix: str
    env_kind: str
    folders: tuple[str, ...]


@dataclass(frozen=True)
class Platform:
    id: str
    hint: str  # wizard label (Korean)
    role: str  # AGENTS.md layout row (English)
    skills: tuple[str, ...]
    env_kind: str = ""  # listen | worker | app ("" for the contract)
    port: str | None = None
    folders: tuple[str, ...] = ()
    stack: str | None = None  # data/templates/platform/<stack>/ copied into each service
    files: tuple[tuple[str, str], ...] = ()  # extra (path, content) per service
    variants: tuple[Variant, ...] = ()
    requires: tuple[str, ...] = ()
    contract: bool = False  # proto: units are languages, not services

    def variant(self, service: str) -> Variant | None:
        return next((v for v in self.variants if service.startswith(v.prefix)), None)

    def env_kind_of(self, service: str) -> str:
        v = self.variant(service)
        return v.env_kind if v else self.env_kind

    def folders_of(self, service: str) -> tuple[str, ...]:
        v = self.variant(service)
        return v.folders if v else self.folders


BACKEND = ("apps", "services", "domains", "modules")
PROTO = "proto"

PLATFORMS: tuple[Platform, ...] = (
    Platform("backend", "단일 백엔드 (API)", "Single backend services (API)", ("yj-backend",),
             "listen", "8080", BACKEND),
    Platform("backend-msa", "gRPC MSA", "gRPC microservices sharing the root proto contract", ("yj-backend-msa",),
             "listen", "8080", BACKEND, requires=(PROTO,)),
    Platform("backend-ssr", "서버 템플릿/SSR", "Server-rendered (SSR/MPA) backend services", ("yj-backend-ssr",),
             "listen", "8080", (*BACKEND, "views")),
    Platform("frontend", "Vite + React + TS", "Vite + React + TS web apps", ("yj-frontend",),
             "listen", "5173", ("src",), stack="frontend"),
    Platform("mobile-app", "Flutter", "Flutter mobile apps", ("yj-mobile-app",), "app", None, ("lib",)),
    Platform("pc-app", "Electron", "Electron desktop apps", ("yj-pc-app",), "app", None,
             ("main", "preload", "renderer/src")),
    Platform("cli", "CLI", "Command-line applications", ("yj-cli",), "app", None, ("apps", "services", "modules")),
    Platform("browser-extension", "MV3", "MV3 browser extensions (`native_*` = native messaging hosts)",
             ("yj-browser-extension", "yj-backend"), "app", None,
             ("src/background", "src/content", "src/popup", "src/lib"), files=(("manifest.json", "{}\n"),),
             variants=(Variant("native_", "worker", ("apps", "services", "modules")),)),
    Platform("scheduler", "주기 배치 작업", "Long-running schedulers for periodic batch jobs", ("yj-scheduler",),
             "worker", None, BACKEND),
    Platform(PROTO, "공유 gRPC/protobuf 계약 (언어별 라이브러리)",
             "Shared gRPC/protobuf contract: `*.proto` schemas, generated libraries in `proto/dist/<language>/`",
             ("yj-proto",), contract=True),
)
PLATFORM = {p.id: p for p in PLATFORMS}
SERVICE_PLATFORMS = tuple(p.id for p in PLATFORMS if not p.contract)


def catalog_order(ids, known=PLATFORM) -> list[str]:
    wanted = set(ids)
    return [k for k in known if k in wanted]


def with_required(platforms) -> tuple[list[str], list[str]]:
    """Platforms plus the ones they require (catalog order), and the ones added."""
    chosen = set(platforms)
    added = [r for p in catalog_order(chosen) for r in PLATFORM[p].requires if r not in chosen]
    return catalog_order(chosen | set(added)), list(dict.fromkeys(added))


@dataclass(frozen=True)
class Language:
    id: str
    label: str
    manifest: str  # library manifest under proto/dist/<id>/ (data/templates/platform/proto/<id>/<manifest>)


LANGUAGES: tuple[Language, ...] = (
    Language("go", "Go", "go.mod"),
    Language("dart", "Dart", "pubspec.yaml"),
    Language("python", "Python", "pyproject.toml"),
)
LANGUAGE = {l.id: l for l in LANGUAGES}


# ---------------------------------------------------------------------- plugins

MANAGED, SEED, BLOCK, CODE = "managed", "seed", "merge", "code"


@dataclass(frozen=True)
class PluginFile:
    template: str  # under data/plugins
    dest: str  # may contain {platform}
    policy: str
    scope: str = "root"  # root | service (each service platform) | contract (the proto platform)
    executable: bool = False


@dataclass(frozen=True)
class Plugin:
    id: str
    label: str
    requires: tuple[str, ...] = ()
    default: bool = False
    files: tuple[PluginFile, ...] = ()
    layout: tuple[tuple[str, str], ...] = ()  # AGENTS.md layout rows


def _tool(tool: str) -> tuple[PluginFile, ...]:
    return (
        PluginFile(f"{tool}/GUIDE.md", f"tools/{tool}/GUIDE.md", MANAGED),
        PluginFile(f"{tool}/{tool}.sh", f"tools/{tool}/{{platform}}/{tool}.sh", SEED, "service", True),
        PluginFile(f"{tool}/{tool}.ps1", f"tools/{tool}/{{platform}}/{tool}.ps1", SEED, "service"),
    )


PLUGINS: tuple[Plugin, ...] = (
    Plugin("runner", "로컬 실행 (make <platform>)", default=True, files=_tool("runner"), layout=(
        ("`tools/runner/`", "Local run — `GUIDE.md` (managed) + `<platform>/runner.{sh,ps1}` (repository-owned); `make <platform> [NAME=<service>]`"),
    )),
    Plugin("builder", "빌드 (dist/<platform>/<service>/)", files=(
        *_tool("builder"),
        PluginFile("builder/proto-builder.sh", "tools/builder/{platform}/builder.sh", SEED, "contract", True),
        PluginFile("builder/proto-builder.ps1", "tools/builder/{platform}/builder.ps1", SEED, "contract"),
    ), layout=(
        ("`tools/builder/`", "Build — `GUIDE.md` (managed) + `<platform>/builder.{sh,ps1}` (repository-owned); `make <platform>-build-<env>`, `make proto-build`"),
        ("`dist/<platform>/<service>/`", "Build output (git-ignored) — the deployer's input"),
    )),
    Plugin("deployer", "배포 (dist → 배포 대상)", requires=("builder",), files=_tool("deployer"), layout=(
        ("`tools/deployer/`", "Deploy — `GUIDE.md` (managed) + `<platform>/deployer.{sh,ps1}` (repository-owned); `make <platform>-deploy-<env>`"),
    )),
)
PLUGIN = {p.id: p for p in PLUGINS}


def plugins_lacking(selected) -> dict[str, list[str]]:
    """Selected plugin -> its requirements that are not selected."""
    chosen = set(selected)
    return {p: [r for r in PLUGIN[p].requires if r not in chosen] for p in selected
            if any(r not in chosen for r in PLUGIN[p].requires)}


def drop_dependents(selected) -> tuple[list[str], list[str]]:
    """Remove plugins whose requirement is gone (repeatedly); returns (kept, dropped)."""
    kept, dropped = set(selected), []
    while lacking := plugins_lacking(kept):
        for p in lacking:
            kept.discard(p)
            dropped.append(p)
    return catalog_order(kept, PLUGIN), dropped


# ----------------------------------------------------------------------- skills


@dataclass(frozen=True)
class Skill:
    id: str
    routes: tuple[tuple[str, str], ...] = ()  # (path pattern, note) rows of the routing table


CORE_SKILL = "yj-arch-core"
SKILLS: tuple[Skill, ...] = (
    Skill(CORE_SKILL),
    Skill("yj-proto", (("proto/**", ""),)),
    Skill("yj-backend", (("backend/**", ""), ("browser-extension/native_*/**", ""))),
    Skill("yj-backend-msa", (("backend-msa/**", ""),)),
    Skill("yj-backend-ssr", (("backend-ssr/**", ""),)),
    Skill("yj-frontend", (("frontend/**", ""),)),
    Skill("yj-mobile-app", (("mobile-app/**", ""),)),
    Skill("yj-pc-app", (("pc-app/**", ""),)),
    Skill("yj-cli", (("cli/**", ""),)),
    Skill("yj-browser-extension", (("browser-extension/**", "(other than `native_*`)"),)),
    Skill("yj-scheduler", (("scheduler/**", ""),)),
)
SKILL = {s.id: s for s in SKILLS}


def skills_for(platforms) -> list[str]:
    wanted = {CORE_SKILL, *(s for p in platforms for s in PLATFORM[p].skills)}
    return [s.id for s in SKILLS if s.id in wanted]


def routes_for(platforms) -> list[tuple[str, str]]:
    """(path, skill) rows: platform order; within a platform the more specific pattern first."""
    skills = skills_for(platforms)
    rows = []
    for p in catalog_order(platforms):
        mine = [(pattern, note, s) for s in skills for pattern, note in SKILL[s].routes
                if pattern.split("/", 1)[0] == p]
        mine.sort(key=lambda r: "*" not in "".join(r[0].removesuffix("/**").split("/", 1)[1:]))
        rows += [(f"`{pattern}`" + (f" {note}" if note else ""), f"`{s}`") for pattern, note, s in mine]
    return rows

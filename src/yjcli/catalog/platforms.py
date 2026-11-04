"""Platforms: code-only scaffolds (service folders, stack files, .env.examples)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Option:
    """Platform-level code option, asked once when the platform is created.

    Whether it is "on" later is decided by disk state (the created folder), not
    by the manifest — yjcli only creates the starting files and never deletes them.
    """

    id: str
    label: str
    creates: tuple[str, ...]  # paths relative to the platform root
    default: bool = False
    fixed: bool = False  # always applied, never asked


@dataclass(frozen=True)
class ServiceVariant:
    """Alternative service shape selected by name prefix (e.g. native_*)."""

    prefix: str
    env_kind: str
    service_dirs: tuple[str, ...]
    files: tuple[tuple[str, str], ...] = ()  # (dest, content)


@dataclass(frozen=True)
class Platform:
    id: str
    hint: str
    role: str  # English role text for the AGENTS.md layout table
    skills: tuple[str, ...]
    env_kind: str  # listen | worker | app
    service_dirs: tuple[str, ...]
    env_vars: dict[str, str] = field(default_factory=dict)
    stack_template: str | None = None  # dir under data/templates/platform
    service_files: tuple[tuple[str, str], ...] = ()  # (dest, content)
    options: tuple[Option, ...] = ()
    variants: tuple[ServiceVariant, ...] = ()

    def variant_for(self, service: str) -> ServiceVariant | None:
        for variant in self.variants:
            if service.startswith(variant.prefix):
                return variant
        return None


_BACKEND_DIRS = ("apps", "services", "domains", "modules")

_PROTO = Option(
    id="proto",
    label="gRPC/protobuf 사용 (proto/ 생성)",
    creates=("proto/.gitkeep", "proto/dist/.gitkeep"),
)

PLATFORMS: tuple[Platform, ...] = (
    Platform(
        id="backend",
        hint="단일 백엔드 (API)",
        role="Single backend services (API)",
        skills=("yj-backend",),
        env_kind="listen",
        env_vars={"__PORT__": "8080"},
        service_dirs=_BACKEND_DIRS,
        options=(_PROTO,),
    ),
    Platform(
        id="backend-msa",
        hint="gRPC MSA",
        role="gRPC microservices sharing one proto contract",
        skills=("yj-backend-msa",),
        env_kind="listen",
        env_vars={"__PORT__": "8080"},
        service_dirs=_BACKEND_DIRS,
        options=(Option(id="proto", label=_PROTO.label, creates=_PROTO.creates, fixed=True),),
    ),
    Platform(
        id="backend-ssr",
        hint="서버 템플릿/SSR",
        role="Server-rendered (SSR/MPA) backend services",
        skills=("yj-backend-ssr",),
        env_kind="listen",
        env_vars={"__PORT__": "8080"},
        service_dirs=(*_BACKEND_DIRS, "views"),
        options=(_PROTO,),
    ),
    Platform(
        id="frontend",
        hint="Vite + React + TS",
        role="Vite + React + TS web apps",
        skills=("yj-frontend",),
        env_kind="listen",
        env_vars={"__PORT__": "5173"},
        service_dirs=("src",),
        stack_template="frontend",
    ),
    Platform(
        id="mobile-app",
        hint="Flutter",
        role="Flutter mobile apps",
        skills=("yj-mobile-app",),
        env_kind="app",
        service_dirs=("lib",),
    ),
    Platform(
        id="pc-app",
        hint="Electron",
        role="Electron desktop apps",
        skills=("yj-pc-app",),
        env_kind="app",
        service_dirs=("main", "preload", "renderer/src"),
    ),
    Platform(
        id="cli",
        hint="CLI",
        role="Command-line applications",
        skills=("yj-cli",),
        env_kind="app",
        service_dirs=("apps", "services", "modules"),
    ),
    Platform(
        id="browser-extension",
        hint="MV3",
        role="MV3 browser extensions (`native_*` = native messaging hosts)",
        skills=("yj-browser-extension", "yj-backend"),
        env_kind="app",
        service_dirs=("src/background", "src/content", "src/popup", "src/lib"),
        service_files=(("manifest.json", "{}\n"),),
        variants=(
            ServiceVariant(
                prefix="native_",
                env_kind="worker",
                service_dirs=("apps", "services", "modules"),
            ),
        ),
    ),
    Platform(
        id="scheduler",
        hint="주기 배치 작업",
        role="Long-running schedulers for periodic batch jobs",
        skills=("yj-scheduler",),
        env_kind="worker",
        service_dirs=_BACKEND_DIRS,
    ),
)

PLATFORM_BY_ID: dict[str, Platform] = {p.id: p for p in PLATFORMS}

# Folder names under a platform root that are not services.
NON_SERVICE_DIRS: frozenset[str] = frozenset({"proto"})
RESERVED_SERVICE_NAMES: frozenset[str] = NON_SERVICE_DIRS

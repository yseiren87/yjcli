"""Platforms: code-only scaffolds (service folders, stack files, .env.examples).

Most platforms hold services. A *contract* platform (`proto`) holds no services:
it is one shared schema folder whose "units" are the languages code is
generated for (`proto/dist/<lang>/`).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Language:
    """Code-generation target of the contract platform (library under dist/<id>/)."""

    id: str
    label: str
    manifest: str  # library manifest seeded under proto/dist/<id>/ (template file name)


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
    env_kind: str  # listen | worker | app ("" for the contract platform)
    service_dirs: tuple[str, ...]
    env_vars: dict[str, str] = field(default_factory=dict)
    stack_template: str | None = None  # dir under data/templates/platform
    service_files: tuple[tuple[str, str], ...] = ()  # (dest, content)
    variants: tuple[ServiceVariant, ...] = ()
    kind: str = "service"  # service | contract
    requires: tuple[str, ...] = ()  # platforms selected automatically with this one

    @property
    def is_contract(self) -> bool:
        return self.kind == "contract"

    def variant_for(self, service: str) -> ServiceVariant | None:
        for variant in self.variants:
            if service.startswith(variant.prefix):
                return variant
        return None


_BACKEND_DIRS = ("apps", "services", "domains", "modules")

LANGUAGES: tuple[Language, ...] = (
    Language("go", "Go", "go.mod"),
    Language("dart", "Dart", "pubspec.yaml"),
    Language("python", "Python", "pyproject.toml"),
)
LANGUAGE_BY_ID: dict[str, Language] = {l.id: l for l in LANGUAGES}

PROTO = "proto"

PLATFORMS: tuple[Platform, ...] = (
    Platform(
        id="backend",
        hint="단일 백엔드 (API)",
        role="Single backend services (API)",
        skills=("yj-backend",),
        env_kind="listen",
        env_vars={"__PORT__": "8080"},
        service_dirs=_BACKEND_DIRS,
    ),
    Platform(
        id="backend-msa",
        hint="gRPC MSA",
        role="gRPC microservices sharing one proto contract",
        skills=("yj-backend-msa",),
        env_kind="listen",
        env_vars={"__PORT__": "8080"},
        service_dirs=_BACKEND_DIRS,
        requires=(PROTO,),
    ),
    Platform(
        id="backend-ssr",
        hint="서버 템플릿/SSR",
        role="Server-rendered (SSR/MPA) backend services",
        skills=("yj-backend-ssr",),
        env_kind="listen",
        env_vars={"__PORT__": "8080"},
        service_dirs=(*_BACKEND_DIRS, "views"),
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
    Platform(
        id=PROTO,
        hint="공유 gRPC/protobuf 계약 (언어별 라이브러리 생성)",
        role="Shared gRPC/protobuf contract: `*.proto` schemas and generated libraries in `proto/dist/<lang>/`",
        skills=("yj-proto",),
        env_kind="",
        service_dirs=(),
        kind="contract",
    ),
)

PLATFORM_BY_ID: dict[str, Platform] = {p.id: p for p in PLATFORMS}


def with_required(platforms: list[str]) -> tuple[list[str], list[str]]:
    """(selection plus platforms it requires, in catalog order; the ones added)."""
    wanted = set(platforms)
    added = [r for p in platforms for r in PLATFORM_BY_ID[p].requires if r not in wanted]
    wanted.update(added)
    return [p.id for p in PLATFORMS if p.id in wanted], list(dict.fromkeys(added))

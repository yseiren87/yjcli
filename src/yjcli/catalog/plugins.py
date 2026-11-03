"""Repository-level tooling plugins installed under tools/.

Not to be confused with build steps (tools/builder/steps/*.sh), which are part
of the builder plugin.
"""

from __future__ import annotations

from dataclasses import dataclass

MANAGED = "managed"
SEED = "seed"


@dataclass(frozen=True)
class PluginFile:
    """One file a plugin installs.

    `template` is relative to data/plugins; `dest` is relative to the repo root.
    Both may use {platform}, {service} and {env_kind}.
    """

    template: str
    dest: str
    policy: str
    scope: str  # root | platform | service
    executable: bool = False
    deployable_only: bool = False
    # Fill __NAME__ / __PORT__ placeholders (secrets env files).
    substitute: bool = False


@dataclass(frozen=True)
class Plugin:
    id: str
    label: str
    location: str
    requires: tuple[str, ...] = ()
    default: bool = False
    files: tuple[PluginFile, ...] = ()
    skill_fragment: str | None = None  # under data/skills/_shared
    layout_rows: tuple[tuple[str, str], ...] = ()
    note: str | None = None  # shown in the plan summary when selected


def _env_files() -> tuple[PluginFile, ...]:
    return tuple(
        PluginFile(
            template=f"secrets/{{env_kind}}/env.{env}",
            dest=f"tools/secrets/{{platform}}/{{service}}/.env.{env}",
            policy=SEED,
            scope="service",
            substitute=True,
        )
        for env in ("local-dev", "development", "production")
    )


PLUGINS: tuple[Plugin, ...] = (
    Plugin(
        id="runner",
        label="플랫폼 일괄 실행 + Makefile",
        location="tools/runner/",
        requires=("secrets",),
        default=True,
        files=(
            PluginFile("runner/run.sh", "tools/runner/run.sh", MANAGED, "root", executable=True),
            PluginFile("runner/run.bat", "tools/runner/run.bat", MANAGED, "root"),
            PluginFile("runner/run.ps1", "tools/runner/run.ps1", MANAGED, "root"),
        ),
        skill_fragment="plugin-runner.md",
        layout_rows=(
            ("`Makefile`, `make.bat`", "Root entry — `make <platform> [NAME=<service>]` runs services via tools/runner"),
            ("`tools/runner/`", "Platform runner — `run.sh` / `run.bat` / `run.ps1 <platform> [service]` (managed by yjcli)"),
        ),
    ),
    Plugin(
        id="secrets",
        label="서비스별 환경 파일 모음 (평문 커밋)",
        location="tools/secrets/",
        default=True,
        files=_env_files(),
        skill_fragment="plugin-secrets.md",
        layout_rows=(
            ("`tools/secrets/<platform>/<service>/`", "Per-service env values (`.env.local-dev`, `.env.<environment>`) — committed in plain text"),
        ),
        note="tools/secrets/ 는 평문으로 커밋됩니다. private 저장소에서만 사용하세요.",
    ),
    Plugin(
        id="builder",
        label="빌드/배포 스크립트 + Dockerfile",
        location="tools/builder/",
        requires=("secrets",),
        files=(
            PluginFile("builder/build-common.sh", "tools/builder/build-common.sh", MANAGED, "root", executable=True),
            PluginFile("builder/deploy-common.sh", "tools/builder/deploy-common.sh", MANAGED, "root", executable=True),
            PluginFile("builder/steps/proto.sh", "tools/builder/steps/proto.sh", MANAGED, "root", executable=True),
            PluginFile("builder/steps/ssr.sh", "tools/builder/steps/ssr.sh", MANAGED, "root", executable=True),
            PluginFile("builder/steps/docker.sh", "tools/builder/steps/docker.sh", MANAGED, "root", executable=True),
            *(
                PluginFile(
                    f"builder/platform/{name}.sh",
                    f"tools/builder/{{platform}}/{name}.sh",
                    SEED,
                    "platform",
                    executable=True,
                )
                for name in ("build-development", "build-production", "deploy-development", "deploy-production")
            ),
            PluginFile("builder/service/Dockerfile", "{platform}/{service}/Dockerfile", SEED, "service", deployable_only=True),
            PluginFile("builder/service/dockerignore", "{platform}/{service}/.dockerignore", SEED, "service", deployable_only=True),
        ),
        skill_fragment="plugin-builder.md",
        layout_rows=(
            ("`tools/builder/`", "Build/deploy — shared hosts and `steps/` (managed), `<platform>/build-*.sh` / `deploy-*.sh` (repository-owned); `make <platform>-build-<env>` / `-deploy-<env>`"),
            ("`<platform>/<service>/Dockerfile`", "Docker build stub for deployable services — delete it to opt a service out"),
        ),
    ),
)

PLUGIN_BY_ID: dict[str, Plugin] = {p.id: p for p in PLUGINS}

# Root Makefile / make.bat are shared by plugins that contribute make targets.
MAKEFILE_PLUGINS: tuple[str, ...] = ("runner", "builder")


def resolve_requires(selected: list[str]) -> tuple[list[str], list[str]]:
    """Return (closed selection in catalog order, plugins added automatically)."""
    wanted = set(selected)
    added: list[str] = []
    changed = True
    while changed:
        changed = False
        for pid in list(wanted):
            for req in PLUGIN_BY_ID[pid].requires:
                if req not in wanted:
                    wanted.add(req)
                    added.append(req)
                    changed = True
    return [p.id for p in PLUGINS if p.id in wanted], added


def drop_dependents(selected: list[str]) -> tuple[list[str], list[str]]:
    """Remove plugins whose requirements are not selected (used when unchecking)."""
    wanted = set(selected)
    dropped: list[str] = []
    changed = True
    while changed:
        changed = False
        for pid in list(wanted):
            if any(req not in wanted for req in PLUGIN_BY_ID[pid].requires):
                wanted.discard(pid)
                dropped.append(pid)
                changed = True
    return [p.id for p in PLUGINS if p.id in wanted], dropped

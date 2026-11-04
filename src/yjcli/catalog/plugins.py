"""Repository-level tooling plugins installed under tools/.

Each plugin ships a managed tools/<plugin>/GUIDE.md (the contract) and one
seed entry script pair per platform, tools/<plugin>/<platform>/<plugin>.{sh,ps1}:
the shared skeleton works out of the box and the project implements one
function in it. Env value files (tools/secrets/) are not a plugin — every
service gets them.
"""

from __future__ import annotations

from dataclasses import dataclass

MANAGED = "managed"
SEED = "seed"


@dataclass(frozen=True)
class PluginFile:
    """One file a plugin installs.

    `template` is relative to data/plugins; `dest` is relative to the repo root.
    Both may use {platform}. Every plugin file is rendered with the plan context
    (plus `platform` and `needs_proto` for platform-scoped files).
    """

    template: str
    dest: str
    policy: str
    scope: str  # root | platform
    executable: bool = False
    kinds: tuple[str, ...] = ("service",)  # platform kinds a platform-scoped file applies to


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


def _tool_files(tool: str) -> tuple[PluginFile, ...]:
    return (
        PluginFile(f"{tool}/GUIDE.md", f"tools/{tool}/GUIDE.md", MANAGED, "root"),
        PluginFile(f"{tool}/{tool}.sh", f"tools/{tool}/{{platform}}/{tool}.sh", SEED, "platform", executable=True),
        PluginFile(f"{tool}/{tool}.ps1", f"tools/{tool}/{{platform}}/{tool}.ps1", SEED, "platform"),
    )


# The proto contract has no services: it gets a codegen entry instead of a build one.
_PROTO_BUILDER = (
    PluginFile("builder/proto-builder.sh", "tools/builder/{platform}/builder.sh", SEED, "platform",
               executable=True, kinds=("contract",)),
    PluginFile("builder/proto-builder.ps1", "tools/builder/{platform}/builder.ps1", SEED, "platform",
               kinds=("contract",)),
)


PLUGINS: tuple[Plugin, ...] = (
    Plugin(
        id="runner",
        label="로컬 실행 (make <platform>)",
        location="tools/runner/",
        default=True,
        files=_tool_files("runner"),
        skill_fragment="plugin-runner.md",
        layout_rows=(
            ("`tools/runner/`", "Local run — `GUIDE.md` (managed) + `<platform>/runner.{sh,ps1}` (repository-owned); `make <platform> [NAME=<service>]`"),
        ),
    ),
    Plugin(
        id="builder",
        label="빌드 (dist/<platform>/<service>/)",
        location="tools/builder/",
        files=(*_tool_files("builder"), *_PROTO_BUILDER),
        skill_fragment="plugin-builder.md",
        layout_rows=(
            ("`tools/builder/`", "Build — `GUIDE.md` (managed) + `<platform>/builder.{sh,ps1}` (repository-owned); `make <platform>-build-<env>`, `make proto-build` (codegen)"),
            ("`dist/<platform>/<service>/`", "Build output (git-ignored) — input of the deployer"),
        ),
    ),
    Plugin(
        id="deployer",
        label="배포 (dist → 배포 대상)",
        location="tools/deployer/",
        requires=("builder",),
        files=_tool_files("deployer"),
        skill_fragment="plugin-deployer.md",
        layout_rows=(
            ("`tools/deployer/`", "Deploy — `GUIDE.md` (managed) + `<platform>/deployer.{sh,ps1}` (repository-owned); `make <platform>-deploy-<env>`"),
        ),
    ),
)

PLUGIN_BY_ID: dict[str, Plugin] = {p.id: p for p in PLUGINS}

# Root Makefile / make.ps1 are shared by every plugin (each adds its targets).
MAKEFILE_PLUGINS: tuple[str, ...] = ("runner", "builder", "deployer")


def missing_requires(selected: list[str]) -> list[str]:
    """Messages for selected plugins whose requirement is not selected."""
    wanted = set(selected)
    return [
        f"{pid} 는 {', '.join(r for r in PLUGIN_BY_ID[pid].requires if r not in wanted)} 가 필요합니다"
        for pid in selected
        if any(r not in wanted for r in PLUGIN_BY_ID[pid].requires)
    ]


def disabled_reasons(selected: list[str]) -> dict[str, str | None]:
    """Per plugin: why it cannot be checked right now (None = selectable)."""
    wanted = set(selected)
    out: dict[str, str | None] = {}
    for p in PLUGINS:
        lacking = [r for r in p.requires if r not in wanted]
        out[p.id] = f"{', '.join(lacking)} 먼저 선택" if lacking else None
    return out


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

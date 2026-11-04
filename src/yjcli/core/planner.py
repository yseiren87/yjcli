"""Selection + repo state + catalog -> Plan (pure: reads disk, never writes).

The plan is built in two halves and merged:
  * code plan    — platform/service folders, stack files, .env.examples, options
  * tooling plan — agent wiring (AGENTS.md, CLAUDE.md, skills), env value files
                   (tools/secrets/, every service), plugin files

Every tracked file carries a policy:
  managed  yjcli owns it; refreshed on every run (skipped with a warning if the
           user changed it since yjcli wrote it, unless --force)
  seed     created once when its owner (LLM/platform/service/plugin) is new;
           user-owned afterwards
  merge    user file with a yjcli block regenerated in place
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from yjcli.catalog import data_root
from yjcli.catalog.llms import LLM_BY_ID, LLMS
from yjcli.catalog.platforms import PLATFORM_BY_ID, PLATFORMS, Platform
from yjcli.catalog.plugins import MAKEFILE_PLUGINS, MANAGED, PLUGIN_BY_ID, PLUGINS, SEED
from yjcli.catalog.skills import CORE_SKILL, SKILL_BY_ID, routing_rows, skills_for
from yjcli.core import render as r
from yjcli.core.manifest import MANIFEST_PATH, FileRecord, Manifest, dumps, sha256
from yjcli.core.selection import Draft, option_values
from yjcli.core.state import RepoState

MERGE = "merge"
SECRET_ENVS = ("local-dev", "development", "production")


class PlanError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("\n".join(errors))
        self.errors = errors


@dataclass
class Spec:
    content: bytes
    policy: str
    executable: bool = False
    introduce: bool = True  # seed: create when missing
    template_hash: str | None = None


@dataclass
class Action:
    kind: str  # create | overwrite | merge | chmod | delete | rmtree | mkdir
    path: str
    content: bytes | None = None
    executable: bool = False
    reason: str = ""


@dataclass
class Plan:
    mode: str
    llms: list[str]
    platforms: list[str]
    plugins: list[str]
    services: dict[str, list[str]]
    new_services: dict[str, list[str]]
    new_platforms: list[str]
    skills: list[str]
    actions: list[Action] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)  # unchanged / preserved paths
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    manifest: Manifest | None = None
    from_version: str | None = None  # yjcli version that wrote the previous manifest
    to_version: str = ""

    def count(self, *kinds: str) -> int:
        return sum(1 for a in self.actions if a.kind in kinds)


def _templates() -> Path:
    return data_root() / "templates"


def _plugin_data() -> Path:
    return data_root() / "plugins"


def _skills_data() -> Path:
    return data_root() / "skills"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- context


def _context(llms: list[str], platforms: list[str], plugins: list[str], skills: list[str]) -> dict:
    roots = []
    for p in PLATFORMS:
        if p.id in platforms:
            roots.append(f"{p.id + '/':<22}# {', '.join(p.skills)}")
    shared = _skills_data() / "_shared"
    fragments = []
    for plugin in PLUGINS:
        if plugin.id in plugins and plugin.skill_fragment:
            fragments.append(_read(shared / plugin.skill_fragment).rstrip("\n"))
    ctx: dict = {
        "platform_roots": "\n".join(roots),
        "skill_routes": r.markdown_table(("Path", "Platform skill"), routing_rows(platforms, skills)),
        "plugins": "\n\n".join(fragments)
        or "No run/build/deploy tooling is installed: this repository holds code and env\n"
        "values only. Do not add run/build/deploy scripts or Makefiles unless the user asks.",
        "platforms": " ".join(p.id for p in PLATFORMS if p.id in platforms),
        "env_kinds": _env_kinds(platforms),
        "has_proto": any(_has_proto(PLATFORM_BY_ID[p]) for p in platforms),
    }
    for plugin in PLUGINS:
        ctx[plugin.id] = plugin.id in plugins
    for p in PLATFORMS:
        ctx["platform_" + p.id.replace("-", "_")] = p.id in platforms
    return ctx


def _has_proto(platform: Platform) -> bool:
    return any(o.id == "proto" for o in platform.options)


def _service_list(services: dict[str, list[str]]) -> str:
    rows = [f"- `{p}/`: " + ", ".join(f"`{s}`" for s in names) for p, names in services.items() if names]
    return "\n".join(rows) or "- (none yet)"


def _env_kinds(platforms: list[str]) -> str:
    kinds: dict[str, list[str]] = {}
    for p in PLATFORMS:
        if p.id not in platforms:
            continue
        port = p.env_vars.get("__PORT__")
        kinds.setdefault(p.env_kind, []).append(f"`{p.id}`" + (f" (PORT {port})" if port else ""))
        for variant in p.variants:
            kinds.setdefault(variant.env_kind, []).append(f"`{p.id}/{variant.prefix}*`")
    return "\n".join(f"  - `{kind}`: {', '.join(names)}" for kind, names in kinds.items())


def _skills_block(llms: list[str], platforms: list[str], skills: list[str]) -> str:
    table = r.markdown_table(("Path", "Skill"), routing_rows(platforms, skills))
    dirs = "\n".join(f"- `{LLM_BY_ID[l].skills_dir}/` ({LLM_BY_ID[l].label})" for l in llms)
    return (
        "When creating, modifying, reviewing, or refactoring code:\n\n"
        f"1. Read and follow skill `{CORE_SKILL}`.\n"
        "2. Load **exactly one** matching platform skill for the folder being edited "
        "(the first matching row wins):\n\n"
        f"{table}\n\n"
        "Never load all platform skills. Never apply a platform skill outside its folder.\n\n"
        f"Skills are installed under:\n\n{dirs}"
    )


def _layout_block(llms: list[str], platforms: list[str], plugins: list[str]) -> str:
    rows: list[tuple[str, str]] = [
        ("`AGENTS.md`", "Agent / contributor guide (this file) — source of truth"),
        ("`.gitignore`", "Ignore rules (the `# >>> yjcli` block is managed)"),
        ("`.yjcli/manifest.toml`", "yjcli selection state — do not edit by hand"),
        ("`.yjcli/skills/<skill>.md`", "(optional) project-specific rules appended to that rendered skill"),
    ]
    for llm in LLMS:
        if llm.id not in llms:
            continue
        if llm.instructions:
            rows.append((f"`{llm.instructions}`", f"{llm.label} entry — imports `AGENTS.md` (`@AGENTS.md`); do not edit"))
        rows.append((f"`{llm.skills_dir}/`", f"{llm.label} skills (rendered by yjcli)"))
        for extra in llm.extras:
            rows.append((f"`{extra.dest}`", f"{llm.label} settings"))
    for p in PLATFORMS:
        if p.id not in platforms:
            continue
        rows.append((f"`{p.id}/`", f"{p.role} — skill {', '.join(f'`{s}`' for s in p.skills)}"))
        for option in p.options:
            folder = option.creates[0].split("/", 1)[0]
            rows.append((f"`{p.id}/{folder}/`", ("" if option.fixed else "(optional) ") + "gRPC/protobuf contract"))
    if platforms:
        rows.append(("`tools/secrets/<platform>/<service>/`",
                     "Per-service env values (`.env.local-dev`, `.env.<environment>`) — committed in plain text"))
    for plugin in PLUGINS:
        if plugin.id in plugins:
            rows += list(plugin.layout_rows)
    return r.markdown_table(("Path", "Role"), rows)


def _gitignore_block() -> str:
    return "\n".join([
        "# Managed by yjcli — regenerated on every run.",
        "# Env values are committed in plain text (private repos only).",
        "!tools/secrets/",
        "!tools/secrets/**",
        "# Build output (tools/builder).",
        "/dist/",
    ])


# --------------------------------------------------------------------------- specs


@dataclass
class _Desired:
    files: dict[str, Spec] = field(default_factory=dict)
    dirs: list[str] = field(default_factory=list)


def _service_env_kind(platform: Platform, service: str) -> str:
    variant = platform.variant_for(service)
    return variant.env_kind if variant else platform.env_kind


def _add_code(desired: _Desired, platform: Platform, service: str, is_new_platform: bool, opts: dict[str, bool]) -> None:
    base = f"{platform.id}/{service}"
    variant = platform.variant_for(service)
    for sub in variant.service_dirs if variant else platform.service_dirs:
        desired.dirs.append(f"{base}/{sub}")
    replace = {"__NAME__": service, **platform.env_vars}
    kind = _service_env_kind(platform, service)
    examples = _read(_templates() / "platform" / "envs" / kind / "env.examples")
    desired.files[f"{base}/.env.examples"] = Spec(examples.encode(), "code")
    if not variant:
        if platform.stack_template:
            for file in sorted((_templates() / "platform" / platform.stack_template).iterdir()):
                if file.is_file():
                    text = r.substitute(_read(file), replace)
                    desired.files[f"{base}/{file.name}"] = Spec(text.encode(), "code")
        for dest, content in platform.service_files:
            desired.files[f"{base}/{dest}"] = Spec(content.encode(), "code")
    if is_new_platform:
        for option in platform.options:
            if opts.get(option.id):
                for rel in option.creates:
                    desired.files[f"{platform.id}/{rel}"] = Spec(b"", "code")


ADDITIONS_DIR = Path(".yjcli") / "skills"


def _skill_additions(root: Path, plan: "Plan") -> dict[str, str]:
    """Project-specific rules from .yjcli/skills/<skill>.md (user-owned)."""
    folder = root / ADDITIONS_DIR
    if not folder.is_dir():
        return {}
    additions: dict[str, str] = {}
    for file in sorted(folder.glob("*.md")):
        if file.stem not in SKILL_BY_ID:
            plan.warnings.append(f"! {ADDITIONS_DIR / file.name}: 알 수 없는 스킬 이름이라 무시합니다")
            continue
        text = file.read_text(encoding="utf-8").strip()
        if text:
            additions[file.stem] = text
    return additions


def _render_skill(skill_id: str, ctx: dict, addition: str | None = None) -> bytes:
    skill = SKILL_BY_ID[skill_id]
    text = _read(_skills_data() / skill_id / "SKILL.md")
    self_routes = ", ".join(f"`{pattern}`" for pattern, _ in skill.routes)
    out = r.render(text, {**ctx, "self_routes": self_routes}, shared_dir=_skills_data() / "_shared")
    left = r.leftover_tags(out)
    if left:
        raise r.RenderError(f"{skill_id}: unrendered tags {left}")
    if addition:
        out = (
            out.rstrip("\n")
            + f"\n\n## Project-specific additions\n\n<!-- from {ADDITIONS_DIR / (skill_id + '.md')} — edit that file, not this one -->\n\n"
            + addition
            + "\n"
        )
    return out.encode()


def build_plan(draft: Draft, state: RepoState, *, version: str, force: bool = False) -> Plan:
    old = state.manifest
    llms = list(draft.llms or [])
    platforms = [p.id for p in PLATFORMS if p.id in (draft.platforms or [])]
    plugins = [p.id for p in PLUGINS if p.id in (draft.plugins or [])]
    skills = skills_for(platforms)

    old_llms = set(old.llms) if old else set()
    old_plugins = set(old.plugins) if old else set()
    new_platforms = set(draft.new_platforms(state))

    services: dict[str, list[str]] = {}
    new_services: dict[str, list[str]] = {}
    for pid in platforms:
        existing = state.existing(pid)
        added = [n for n in draft.names.get(pid, []) if n not in existing]
        services[pid] = sorted(set(existing) | set(added))
        if added:
            new_services[pid] = added

    plan = Plan(
        mode=draft.mode,
        llms=llms,
        platforms=platforms,
        plugins=plugins,
        services=services,
        new_services=new_services,
        new_platforms=[p for p in platforms if p in new_platforms],
        skills=skills,
        notes=list(draft.notes),
        from_version=old.yjcli_version if old else None,
        to_version=version,
    )

    desired = _Desired()
    ctx = _context(llms, platforms, plugins, skills)
    ctx["service_list"] = _service_list(services)

    # ---- code plan: only new services (and options of new platforms) ----
    for pid, names in new_services.items():
        platform = PLATFORM_BY_ID[pid]
        opts = option_values(draft, pid)
        for name in names:
            _add_code(desired, platform, name, pid in new_platforms, opts)
    for pid in new_platforms:
        if pid not in new_services:
            plan.warnings.append(f"{pid}: 서비스 이름이 없어 플랫폼 폴더를 만들지 않습니다")

    # ---- agent wiring ----
    agents_tpl = _read(_templates() / "root" / "AGENTS.md")
    blocks = {
        "rules": _read(_templates() / "root" / "agents-rules.md").rstrip("\n"),
        "skills": _skills_block(llms, platforms, skills),
        "layout": _layout_block(llms, platforms, plugins),
    }
    additions = _skill_additions(state.root, plan)
    for llm in LLMS:
        if llm.id not in llms:
            continue
        if llm.instructions:
            desired.files[llm.instructions] = Spec(b"@AGENTS.md\n", MANAGED)
        for extra in llm.extras:
            content = (_templates() / extra.template).read_bytes()
            desired.files[extra.dest] = Spec(content, SEED, introduce=llm.id not in old_llms, template_hash=sha256(content))
        for skill_id in skills:
            desired.files[f"{llm.skills_dir}/{skill_id}/SKILL.md"] = Spec(
                _render_skill(skill_id, ctx, additions.get(skill_id)), MANAGED
            )

    # ---- env values: every service (seed, created with the service) ----
    for p in platforms:
        platform = PLATFORM_BY_ID[p]
        for s in services[p]:
            kind = _service_env_kind(platform, s)
            for env in SECRET_ENVS:
                text = r.substitute(_read(_templates() / "secrets" / kind / f"env.{env}"), {"__NAME__": s, **platform.env_vars})
                content = text.encode()
                desired.files[f"tools/secrets/{p}/{s}/.env.{env}"] = Spec(
                    content, SEED, introduce=s in new_services.get(p, []), template_hash=sha256(content)
                )

    # ---- plugins ----
    if any(p in plugins for p in MAKEFILE_PLUGINS):
        for name in ("Makefile", "make.ps1"):
            text = r.render(_read(_plugin_data() / "_shared" / name), ctx)
            desired.files[name] = Spec(text.encode(), MANAGED)
    for pid in plugins:
        plugin = PLUGIN_BY_ID[pid]
        plugin_new = pid not in old_plugins
        for pf in plugin.files:
            if pf.scope == "root":
                targets = [({}, ctx, plugin_new)]
            else:
                targets = [
                    ({"platform": p}, {**ctx, "platform": p, "proto": _has_proto(PLATFORM_BY_ID[p])},
                     plugin_new or p in new_platforms)
                    for p in platforms if services[p]
                ]
            for values, render_ctx, introduce in targets:
                content = r.render(_read(_plugin_data() / pf.template), render_ctx).encode()
                desired.files[pf.dest.format(**values)] = Spec(
                    content, pf.policy, executable=pf.executable, introduce=introduce,
                    template_hash=sha256(content) if pf.policy == SEED else None,
                )

    # ---- compare with disk ----
    root = state.root
    old_files = dict(old.files) if old else {}
    records: dict[str, FileRecord] = {}

    for rel in desired.dirs:
        if not (root / rel).is_dir():
            plan.actions.append(Action("mkdir", rel))

    for rel, spec in desired.files.items():
        path = root / rel
        exists = path.is_file()
        rec = old_files.get(rel)
        if spec.policy == "code":
            if exists:
                plan.kept.append(rel)
            else:
                plan.actions.append(Action("create", rel, spec.content, spec.executable))
            continue
        if spec.policy == MANAGED:
            if not exists:
                plan.actions.append(Action("create", rel, spec.content, spec.executable))
                records[rel] = FileRecord(MANAGED, sha256(spec.content))
                continue
            disk = path.read_bytes()
            if disk == spec.content:
                records[rel] = FileRecord(MANAGED, sha256(disk))
                if spec.executable and not _is_executable(path):
                    plan.actions.append(Action("chmod", rel, executable=True))
                else:
                    plan.kept.append(rel)
                continue
            user_changed = rec is None or sha256(disk) != rec.sha256
            if user_changed and not force:
                why = "사용자가 수정함" if rec else "yjcli 가 만들지 않은 파일이 이미 있음"
                plan.warnings.append(f"! {rel}: {why} — 건너뜀 (--force 로 덮어쓰기)")
                if rel.endswith("/SKILL.md"):
                    skill_id = rel.rsplit("/", 2)[-2]
                    plan.warnings.append(f"  스킬은 직접 고치지 말고 {ADDITIONS_DIR / (skill_id + '.md')} 에 추가 규칙을 적으세요")
                if rec:
                    records[rel] = rec
                continue
            plan.actions.append(Action("overwrite", rel, spec.content, spec.executable, "forced" if user_changed else ""))
            records[rel] = FileRecord(MANAGED, sha256(spec.content))
            continue
        # seed
        if exists:
            plan.kept.append(rel)
            if rec and rec.template and spec.template_hash and rec.template != spec.template_hash:
                plan.notes.append(f"{rel}: 템플릿이 바뀌었습니다 (사용자 파일이라 적용하지 않음)")
            records[rel] = FileRecord(SEED, rec.sha256 if rec else sha256(path.read_bytes()), spec.template_hash)
        elif spec.introduce or rec is None:
            # New owner, or a seed this repo never had (added by a newer yjcli).
            plan.actions.append(Action("create", rel, spec.content, spec.executable))
            records[rel] = FileRecord(SEED, sha256(spec.content), spec.template_hash)
        else:
            records[rel] = rec  # deleted by the user: remember the opt-out

    # AGENTS.md (seed + managed blocks)
    _plan_agents(plan, root, agents_tpl, blocks, old_files, records)
    # .gitignore (merge block)
    _plan_gitignore(plan, root, _gitignore_block(), records)

    # ---- files yjcli tracked before but no longer wants ----
    for rel, rec in old_files.items():
        if rel in records or rel in desired.files or rel in ("AGENTS.md", ".gitignore"):
            continue
        path = root / rel
        if not path.is_file():
            continue
        if rec.policy == MANAGED:
            if sha256(path.read_bytes()) == rec.sha256 or force:
                plan.actions.append(Action("delete", rel))
            else:
                plan.warnings.append(f"! {rel}: 더 이상 관리하지 않지만 사용자가 수정해서 남겨 둡니다")
        elif rec.template and sha256(path.read_bytes()) == rec.sha256 == rec.template:
            # Seed still identical to the template yjcli wrote (e.g. an unimplemented
            # script). Files adopted from the user never match their template hash.
            plan.actions.append(Action("delete", rel))
        else:
            plan.notes.append(f"{rel}: 사용자 파일이라 남겨 둡니다 (더 이상 yjcli 가 관리하지 않음)")

    # ---- removed platforms (validated: they have no services) ----
    if old:
        for pid in old.platforms:
            if pid in platforms:
                continue
            pdir = root / pid
            if pdir.is_dir():
                leftovers = [p for p in pdir.rglob("*") if p.is_file() and p.name != ".gitkeep"]
                if leftovers:
                    plan.warnings.append(f"{pid}/: 파일이 남아 있어 폴더는 지우지 않습니다")
                else:
                    plan.actions.append(Action("rmtree", pid))
        for pid, names in old.platforms.items():
            for s in names:
                if pid in platforms and s not in services.get(pid, []):
                    plan.notes.append(f"{pid}/{s}: 폴더가 없어 매니페스트에서 정리합니다")
                    if (root / "tools" / "secrets" / pid / s).is_dir():
                        plan.notes.append(f"tools/secrets/{pid}/{s}/: 서비스가 없는 환경 파일이 남아 있습니다")

    if any(a.kind == "create" and a.path.startswith("tools/secrets/") for a in plan.actions):
        plan.warnings.append("tools/secrets/ 는 평문으로 커밋됩니다. private 저장소에서만 사용하세요.")

    plan.manifest = Manifest(
        yjcli_version=version,
        llms=llms,
        plugins=plugins,
        platforms={p: services[p] for p in platforms if services[p]},
        files=records,
    )
    manifest_text = dumps(plan.manifest)
    path = root / MANIFEST_PATH
    if not path.is_file() or path.read_text(encoding="utf-8") != manifest_text:
        plan.actions.append(Action("overwrite" if path.is_file() else "create", str(MANIFEST_PATH), manifest_text.encode()))
    return plan


def _is_executable(path: Path) -> bool:
    return bool(path.stat().st_mode & 0o111)


def _plan_agents(plan, root, template, blocks: dict[str, str], old_files, records) -> None:
    rel = "AGENTS.md"
    path = root / rel
    rendered = r.render(template, {f"{name}_block": body for name, body in blocks.items()})
    if not path.is_file():
        plan.actions.append(Action("create", rel, rendered.encode()))
        records[rel] = FileRecord(SEED, sha256(rendered.encode()))
        return
    text = path.read_text(encoding="utf-8")
    updated = text
    for name, body in blocks.items():
        replaced = r.replace_block(updated, name, body)
        if replaced is None:
            plan.warnings.append(f"! AGENTS.md: <!-- yjcli:{name} --> 블록이 없어 갱신하지 않습니다")
        else:
            updated = replaced
    if updated != text:
        plan.actions.append(Action("merge", rel, updated.encode()))
    else:
        plan.kept.append(rel)
    prev = old_files.get(rel)
    records[rel] = FileRecord(SEED, prev.sha256 if prev else sha256(text.encode()))


def _plan_gitignore(plan, root, block_body, records) -> None:
    rel = ".gitignore"
    path = root / rel
    block = r.hash_block("managed", block_body)
    if not path.is_file():
        base = _read(_templates() / "root" / "gitignore").rstrip("\n")
        content = f"{base}\n\n{block}"
    else:
        text = path.read_text(encoding="utf-8")
        replaced = r.replace_block(text, "managed", block_body, style="hash")
        content = replaced if replaced is not None else text.rstrip("\n") + "\n\n" + block
        if content == text:
            plan.kept.append(rel)
            records[rel] = FileRecord(MERGE, sha256(content.encode()))
            return
    plan.actions.append(Action("merge" if path.is_file() else "create", rel, content.encode()))
    records[rel] = FileRecord(MERGE, sha256(content.encode()))

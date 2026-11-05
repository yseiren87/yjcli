"""Target config + repository -> Plan. Reads the disk, never writes it.

The plan has three parts:
  * desired files — code (created once), agent wiring, env values, plugin files,
    each with an ownership policy (managed / seed / merge / code)
  * removals     — folders that belong to what the config dropped, removed whole
  * the manifest — written last by apply
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from yjcli import template as t
from yjcli.catalog import (
    BLOCK, CODE, CORE_SKILL, DATA, LANGUAGE, LANGUAGES, LLM, LLMS, MANAGED, PLATFORM, PLATFORMS, PLUGINS, PROTO, SEED,
    SKILL, routes_for, skills_for,
)
from yjcli.references import stale_references
from yjcli.repo import MANIFEST, Manifest, Record, Repo, dump_manifest, sha256
from yjcli.selection import Config, stored_config

ENVS = ("local-dev", "development", "production")
ADDITIONS = ".yjcli/skills"
NO_TOOLING = ("No run/build/deploy tooling is installed: this repository holds code (and env values, where enabled) only. "
              "Do not add run/build/deploy scripts or Makefiles unless the user asks.")


@dataclass
class Change:
    kind: str  # create | overwrite | merge | chmod | delete | rmtree | mkdir
    path: str
    content: bytes | None = None
    executable: bool = False
    note: str = ""


@dataclass
class Removal:
    path: str
    files: int
    why: str
    code: bool = False  # project code: a service, a platform, proto


@dataclass
class Plan:
    new: bool
    config: Config
    before: Config | None
    skills: list[str]
    added: dict[str, list[str]]  # platform -> new units
    version: str
    previous: str | None
    changes: list[Change] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    removals: list[Removal] = field(default_factory=list)
    review: list[str] = field(default_factory=list)  # to check after applying
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def count(self, *kinds: str) -> int:
        return sum(1 for c in self.changes if c.kind in kinds)

    @property
    def file_changes(self) -> list[Change]:
        return [c for c in self.changes if c.path != MANIFEST]

    @property
    def removes_code(self) -> bool:
        return any(r.code for r in self.removals)


@dataclass
class _Want:
    content: bytes
    policy: str
    executable: bool = False
    introduce: bool = True  # seeds: create when missing
    template: str | None = None


def _read(*parts: str) -> str:
    return DATA.joinpath(*parts).read_text(encoding="utf-8")


# ------------------------------------------------------------------ text pieces


def proto_names(repo_name: str) -> dict[str, str]:
    words = [w for w in re.split(r"[^a-z0-9]+", repo_name.lower()) if w] or ["app"]
    if words[0][0].isdigit():
        words.insert(0, "repo")
    dash, snake = "-".join(words), "_".join(words)
    return {"proto_go_module": f"{dash}/proto", "proto_dart_package": f"{snake}_proto",
            "proto_python_dist": f"{dash}-proto", "proto_python_package": f"{snake}_proto"}


def _env_kinds(platforms: list[str]) -> str:
    kinds: dict[str, list[str]] = {}
    for p in platforms:
        pf = PLATFORM[p]
        if pf.contract:
            continue
        kinds.setdefault(pf.env_kind, []).append(f"`{p}`" + (f" (PORT {pf.port})" if pf.port else ""))
        for v in pf.variants:
            kinds.setdefault(v.env_kind, []).append(f"`{p}/{v.prefix}*`")
    return "\n".join(f"  - `{kind}`: {', '.join(names)}" for kind, names in kinds.items())


def _context(cfg: Config, repo_name: str) -> dict:
    platforms = cfg.platforms
    services = [p for p in platforms if not PLATFORM[p].contract]
    without = [p for p in services if p not in cfg.secrets]
    fragments = [_read("skills", "_shared", f"plugin-{p}.md").rstrip("\n") for p in cfg.plugins]
    ctx = {
        "platform_roots": "\n".join(f"{p + '/':<22}# {', '.join(PLATFORM[p].skills)}" for p in platforms),
        "skill_routes": t.table(("Path", "Platform skill"), routes_for(platforms)),
        "plugins": "\n\n".join(fragments) or NO_TOOLING,
        "tooling": bool(cfg.plugins),
        "platforms": " ".join(services),
        "env_kinds": _env_kinds(platforms),
        "service_list": "\n".join(f"- `{p}/`: " + ", ".join(f"`{s}`" for s in cfg.units[p]) for p in services)
                        or "- (none yet)",
        "proto_languages": ", ".join(f"`{l}`" for l in cfg.units.get(PROTO, [])) or "(none yet)",
        "secrets": bool(cfg.secrets),
        "no_secrets": bool(without),
        "no_secrets_platforms": ", ".join(f"`{p}`" for p in without),
        **proto_names(repo_name),
    }
    ctx.update({p.id: p.id in cfg.plugins for p in PLUGINS})
    ctx.update({"platform_" + p.id.replace("-", "_"): p.id in platforms for p in PLATFORMS})
    ctx.update({f"proto_lang_{l.id}": l.id in cfg.units.get(PROTO, []) for l in LANGUAGES})
    return ctx


def _skills_block(cfg: Config) -> str:
    dirs = "\n".join(f"- `{LLM[l].skills_dir}/` ({LLM[l].label})" for l in cfg.llms)
    return (
        "When creating, modifying, reviewing, or refactoring code:\n\n"
        f"1. Read and follow skill `{CORE_SKILL}`.\n"
        "2. Load **exactly one** matching platform skill for the folder being edited (the first matching row wins):\n\n"
        f"{t.table(('Path', 'Skill'), routes_for(cfg.platforms))}\n\n"
        "Never load all platform skills. Never apply a platform skill outside its folder.\n\n"
        f"Skills are installed under:\n\n{dirs}"
    )


def _layout_block(cfg: Config) -> str:
    rows = [
        ("`AGENTS.md`", "Agent / contributor guide (this file) — source of truth"),
        ("`.gitignore`", "Ignore rules (the `# >>> yjcli:managed` block is managed)"),
        ("`.yjcli/manifest.toml`", "yjcli configuration — do not edit by hand"),
        ("`.yjcli/skills/<skill>.md`", "(optional) project-specific rules appended to that rendered skill"),
    ]
    for l in (LLM[x] for x in cfg.llms):
        if l.instructions:
            rows.append((f"`{l.instructions}`", f"{l.label} entry — imports `AGENTS.md` (`@AGENTS.md`); do not edit"))
        rows.append((f"`{l.skills_dir}/`", f"{l.label} skills (rendered by yjcli)"))
        rows += [(f"`{dest}`", f"{l.label} settings") for _, dest in l.settings]
    for p in cfg.platforms:
        rows.append((f"`{p}/`", f"{PLATFORM[p].role} — skill {', '.join(f'`{s}`' for s in PLATFORM[p].skills)}"))
    if cfg.secrets:
        services = [p for p in cfg.platforms if not PLATFORM[p].contract]
        scope = "" if set(cfg.secrets) >= set(services) else " — " + ", ".join(f"`{p}`" for p in cfg.secrets) + " only"
        rows.append(("`tools/secrets/<platform>/<service>/`",
                     f"Per-service env values (`.env.local-dev`, `.env.<environment>`) — committed in plain text{scope}"))
    for plugin in PLUGINS:
        if plugin.id in cfg.plugins:
            rows += list(plugin.layout)
    return t.table(("Path", "Role"), rows)


def _gitignore_block(cfg: Config) -> str:
    lines = ["# Managed by yjcli — regenerated on every run."]
    if cfg.secrets:
        lines += ["# Env values are committed in plain text (private repositories only).", "!tools/secrets/",
                  "!tools/secrets/**"]
    lines += ["# Build output (tools/builder).", "/dist/"]
    if PROTO in cfg.units:
        lines += ["# Generated proto libraries are committed (consumed by path dependency).", "!proto/dist/"]
    return "\n".join(lines)


def _skill(skill: str, ctx: dict, addition: str | None) -> bytes:
    routes = ", ".join(f"`{pattern}`" for pattern, _ in SKILL[skill].routes)
    text = t.render(_read("skills", skill, "SKILL.md"), {**ctx, "self_routes": routes}, DATA / "skills" / "_shared")
    if left := t.TAG.findall(text):
        raise t.TemplateError(f"{skill}: unrendered tags {left}")
    if addition:
        text = (text.rstrip("\n") + f"\n\n## Project-specific additions\n\n<!-- from {ADDITIONS}/{skill}.md — "
                "edit that file, not this one -->\n\n" + addition + "\n")
    return text.encode()


# ----------------------------------------------------------------------- wanted


def _wanted(cfg: Config, before: Config | None, repo: Repo, plan: Plan) -> tuple[dict[str, _Want], list[str]]:
    files: dict[str, _Want] = {}
    dirs: list[str] = []
    ctx = _context(cfg, repo.root.name)
    old_llms = set(before.llms) if before else set()
    old_plugins = set(before.plugins) if before else set()
    new_platforms = {p for p in cfg.platforms if not before or p not in before.units}
    switched_on = {p for p in cfg.secrets if before and p in before.units and p not in before.secrets}

    # code: only new services and languages
    for pid, names in plan.added.items():
        pf = PLATFORM[pid]
        for name in names:
            if pf.contract:
                manifest = LANGUAGE[name].manifest
                files[f"{pid}/dist/{name}/{manifest}"] = _Want(
                    t.render(_read("templates", "platform", "proto", name, manifest), ctx).encode(), CODE)
                continue
            base = f"{pid}/{name}"
            dirs += [f"{base}/{d}" for d in pf.folders_of(name)]
            files[f"{base}/.env.examples"] = _Want(
                _read("templates", "platform", "envs", pf.env_kind_of(name), "env.examples").encode(), CODE)
            if not pf.variant(name):
                tokens = {"__NAME__": name, "__PORT__": pf.port or ""}
                if pf.stack:
                    for f in sorted((DATA / "templates" / "platform" / pf.stack).iterdir()):
                        files[f"{base}/{f.name}"] = _Want(t.substitute(f.read_text(encoding="utf-8"), tokens).encode(), CODE)
                for path, content in pf.files:
                    files[f"{base}/{path}"] = _Want(content.encode(), CODE)

    # agent wiring
    additions = _additions(repo, plan)
    skills = plan.skills
    for l in (LLM[x] for x in cfg.llms):
        if l.instructions:
            files[l.instructions] = _Want(b"@AGENTS.md\n", MANAGED)
        for tpl, dest in l.settings:
            content = DATA.joinpath("templates", tpl).read_bytes()
            files[dest] = _Want(content, SEED, introduce=l.id not in old_llms, template=sha256(content))
        for s in skills:
            files[f"{l.skills_dir}/{s}/SKILL.md"] = _Want(_skill(s, ctx, additions.get(s)), MANAGED)

    # env values
    for pid in cfg.secrets:
        pf = PLATFORM[pid]
        for s in cfg.units[pid]:
            for env in ENVS:
                tokens = {"__NAME__": s, "__PORT__": pf.port or ""}
                content = t.substitute(_read("templates", "secrets", pf.env_kind_of(s), f"env.{env}"), tokens).encode()
                fresh = s in plan.added.get(pid, []) or pid in switched_on or pid in new_platforms
                files[f"tools/secrets/{pid}/{s}/.env.{env}"] = _Want(content, SEED, introduce=fresh, template=sha256(content))

    # plugins
    if cfg.plugins:
        for name in ("Makefile", "make.ps1"):
            files[name] = _Want(t.render(_read("plugins", "_shared", name), ctx).encode(), MANAGED)
    for plugin in (p for p in PLUGINS if p.id in cfg.plugins):
        fresh_plugin = plugin.id not in old_plugins
        for pf in plugin.files:
            if pf.scope == "root":
                targets = [("", ctx, fresh_plugin)]
            else:
                targets = [
                    (pid, {**ctx, "platform": pid, "needs_proto": PROTO in PLATFORM[pid].requires,
                           "env_files": pid in cfg.secrets}, fresh_plugin or pid in new_platforms)
                    for pid in cfg.platforms if PLATFORM[pid].contract == (pf.scope == "contract")
                ]
            for pid, render_ctx, fresh in targets:
                content = t.render(_read("plugins", pf.template), render_ctx).encode()
                files[pf.dest.format(platform=pid)] = _Want(
                    content, pf.policy, pf.executable, introduce=fresh,
                    template=sha256(content) if pf.policy == SEED else None)
    return files, dirs


def _additions(repo: Repo, plan: Plan) -> dict[str, str]:
    folder = repo.root / ADDITIONS
    out: dict[str, str] = {}
    for f in sorted(folder.glob("*.md")) if folder.is_dir() else []:
        if f.stem not in SKILL:
            plan.warnings.append(f"! {ADDITIONS}/{f.name}: 알 수 없는 스킬 이름이라 무시합니다")
        elif text := f.read_text(encoding="utf-8").strip():
            out[f.stem] = text
    return out


# --------------------------------------------------------------------- removals


def _files_in(path: Path) -> int:
    return 1 if path.is_file() else sum(1 for f in path.rglob("*") if f.is_file())


def _removals(cfg: Config, before: Config | None, repo: Repo, skills: list[str]) -> list[Removal]:
    """Everything that belongs to what the config dropped, folder by folder."""
    if before is None:
        return []
    wanted: list[tuple[str, str, bool]] = []
    staying_dirs = {LLM[l].skills_dir for l in cfg.llms}
    for l in before.llms:
        if l not in cfg.llms and LLM[l].skills_dir not in staying_dirs:
            wanted.append((LLM[l].skills_dir, f"LLM {l}", False))
    for s in skills_for(before.platforms):
        if s not in skills:
            wanted += [(f"{LLM[l].skills_dir}/{s}", f"스킬 {s}", False) for l in cfg.llms]
    wanted += [(f"tools/{p}", f"플러그인 {p}", False) for p in before.plugins if p not in cfg.plugins]
    for pid, units in before.units.items():
        if pid not in cfg.units:
            why = f"플랫폼 {pid}"
            wanted += [(pid, why, True), *((f"tools/{p.id}/{pid}", why, False) for p in PLUGINS),
                       (f"tools/secrets/{pid}", why, False), (f"dist/{pid}", why, False)]
            continue
        for u in units:
            if u in cfg.units[pid]:
                continue
            if PLATFORM[pid].contract:
                wanted.append((f"{pid}/dist/{u}", f"{pid} 언어 {u}", False))
            else:
                why = f"서비스 {pid}/{u}"
                wanted += [(f"{pid}/{u}", why, True), (f"tools/secrets/{pid}/{u}", why, False),
                           (f"dist/{pid}/{u}", why, False)]
        if pid in before.secrets and pid not in cfg.secrets:
            wanted.append((f"tools/secrets/{pid}", f"secrets 끔 ({pid})", False))

    out: list[Removal] = []
    for path, why, code in wanted:
        target = repo.root / path
        if not target.exists() or _under(path, out):
            continue
        out = [r for r in out if not r.path.startswith(path + "/")]
        out.append(Removal(path, _files_in(target), why, code))
    return out


def _under(path: str, removals: list[Removal]) -> bool:
    return any(path == r.path or path.startswith(r.path + "/") for r in removals)


# ------------------------------------------------------------------------- plan


def build_plan(cfg: Config, repo: Repo, *, version: str, force: bool = False, notes: list[str] | None = None) -> Plan:
    m = repo.manifest
    before = stored_config(repo)
    added = {p: [u for u in us if u not in repo.existing(p)] for p, us in cfg.units.items()}
    plan = Plan(new=m is None, config=cfg, before=before, skills=skills_for(cfg.platforms),
                added={p: us for p, us in added.items() if us}, version=version,
                previous=m.version if m else None, notes=list(notes or []))
    plan.removals = _removals(cfg, before, repo, plan.skills)
    wanted, dirs = _wanted(cfg, before, repo, plan)
    root = repo.root
    old = dict(m.files) if m else {}
    records: dict[str, Record] = {}

    plan.changes += [Change("rmtree", r.path, note=r.why) for r in plan.removals]
    plan.changes += [Change("mkdir", d) for d in dirs if not (root / d).is_dir()]
    for rel, want in wanted.items():
        _compare(plan, root, rel, want, old.get(rel), records, force)
    _agents(plan, root, cfg, records)
    _gitignore(plan, root, cfg, records)

    # tracked files yjcli no longer wants, outside the removed folders
    dropped_llm_files = {path for l in (before.llms if before else []) if l not in cfg.llms
                         for path in [LLM[l].instructions, *(d for _, d in LLM[l].settings)] if path}
    for rel, rec in old.items():
        if rel in wanted or rel in records or rel in ("AGENTS.md", ".gitignore") or _under(rel, plan.removals):
            continue
        if (root / rel).is_file() and (rec.policy == MANAGED or rel in dropped_llm_files):
            plan.changes.append(Change("delete", rel))
            plan.removals.append(Removal(rel, 1, "더 이상 쓰지 않는 파일"))
        # a seed whose owner is still selected but that yjcli no longer ships stays the project's

    for pid, units in (m.units if m else {}).items():
        plan.notes += [f"{pid}/{u}: 폴더가 없어 매니페스트에서 정리합니다"
                       for u in units if repo.existing(pid) and u not in repo.existing(pid)]

    if any(c.kind == "create" and c.path.startswith("tools/secrets/") for c in plan.changes):
        plan.warnings.append("tools/secrets/ 는 평문으로 커밋됩니다. private 저장소에서만 사용하세요.")
    gone = {p: [u for u in us if u not in cfg.units.get(p, [])] for p, us in (before.units if before else {}).items()}
    upcoming = {c.path: None if c.kind == "delete" else c.content.decode("utf-8", "replace")
                for c in plan.changes if c.path in ("AGENTS.md", "CLAUDE.md") and (c.kind == "delete" or c.content)}
    if stale := stale_references(root, cfg.llms, cfg.plugins, cfg.platforms, gone, upcoming):
        plan.warnings.append("블록 밖에 남은 참조 — 지금 구성에 없는 경로입니다. 직접 고치세요:")
        plan.warnings += stale

    manifest = Manifest(version, cfg.llms, cfg.plugins, dict(cfg.units),
                        [p for p in cfg.platforms if not PLATFORM[p].contract and p not in cfg.secrets], records)
    text = dump_manifest(manifest)
    path = root / MANIFEST
    if not path.is_file() or path.read_text(encoding="utf-8") != text:
        plan.changes.append(Change("overwrite" if path.is_file() else "create", MANIFEST, text.encode()))
    return plan


def _compare(plan: Plan, root: Path, rel: str, want: _Want, rec: Record | None, records: dict[str, Record],
             force: bool) -> None:
    path = root / rel
    exists = path.is_file()
    if want.policy == CODE:
        if exists:
            plan.kept.append(rel)
        else:
            plan.changes.append(Change("create", rel, want.content, want.executable))
        return
    if want.policy == MANAGED:
        if not exists:
            plan.changes.append(Change("create", rel, want.content, want.executable))
            records[rel] = Record(MANAGED, sha256(want.content))
            return
        disk = path.read_bytes()
        if disk == want.content:
            records[rel] = Record(MANAGED, sha256(disk))
            if want.executable and not path.stat().st_mode & 0o111:
                plan.changes.append(Change("chmod", rel, executable=True))
            else:
                plan.kept.append(rel)
            return
        if rec is None and not force:
            plan.warnings.append(f"! {rel}: yjcli 가 만들지 않은 파일이 이미 있음 — 건너뜀 (--force 로 덮어쓰기)")
            return
        note = ""
        if rec is None or sha256(disk) != rec.sha256:
            note = "로컬 수정 덮어씀"
            if rel.endswith("/SKILL.md"):
                hint = f"스킬 규칙은 {ADDITIONS}/{rel.rsplit('/', 2)[-2]}.md 에 적으세요"
            elif rel.endswith("/GUIDE.md"):
                hint = "프로젝트 메모는 AGENTS.md 에 적으세요"
            else:
                hint = "git diff 로 확인하세요"
            plan.review.append(f"{rel}: 로컬 수정을 덮어썼습니다 — {hint}")
        plan.changes.append(Change("overwrite", rel, want.content, want.executable, note))
        records[rel] = Record(MANAGED, sha256(want.content))
        return
    # seed
    if exists:
        plan.kept.append(rel)
        if rec and rec.template and want.template and rec.template != want.template:
            tool = rel.split("/")[1] if rel.startswith("tools/") and not rel.startswith("tools/secrets/") else None
            guide = f"tools/{tool}/GUIDE.md 기준으로 확인하세요" if tool else "필요하면 직접 반영하세요"
            plan.review.append(f"{rel}: 시작 템플릿이 바뀌었습니다 (프로젝트 파일이라 그대로 둠) — {guide}")
        records[rel] = Record(SEED, rec.sha256 if rec else sha256(path.read_bytes()), want.template)
    elif want.introduce or rec is None:
        plan.changes.append(Change("create", rel, want.content, want.executable))
        records[rel] = Record(SEED, sha256(want.content), want.template)
    else:
        records[rel] = rec  # the project deleted it: remember the opt-out


def _agents(plan: Plan, root: Path, cfg: Config, records: dict[str, Record]) -> None:
    blocks = {"rules": _read("templates", "root", "agents-rules.md").rstrip("\n"), "skills": _skills_block(cfg),
              "layout": _layout_block(cfg)}
    path = root / "AGENTS.md"
    if not path.is_file():
        text = t.render(_read("templates", "root", "AGENTS.md"), {f"{k}_block": v for k, v in blocks.items()})
        plan.changes.append(Change("create", "AGENTS.md", text.encode()))
        records["AGENTS.md"] = Record(BLOCK, sha256(text.encode()))
        return
    current = path.read_text(encoding="utf-8")
    text = current
    for name, body in blocks.items():
        replaced = t.replace_block(text, name, body)
        if replaced is None:
            replaced = text.rstrip("\n") + "\n\n" + t.block(name, body)
            plan.review.append(f"AGENTS.md: <!-- yjcli:{name} --> 블록이 없어 파일 끝에 다시 넣었습니다 — 위치를 확인하세요")
        text = replaced
    if text != current:
        plan.changes.append(Change("merge", "AGENTS.md", text.encode()))
    else:
        plan.kept.append("AGENTS.md")
    records["AGENTS.md"] = Record(BLOCK, sha256(text.encode()))


def _gitignore(plan: Plan, root: Path, cfg: Config, records: dict[str, Record]) -> None:
    body = _gitignore_block(cfg)
    path = root / ".gitignore"
    if not path.is_file():
        text = _read("templates", "root", "gitignore").rstrip("\n") + "\n\n" + t.block("managed", body, "hash")
        plan.changes.append(Change("create", ".gitignore", text.encode()))
    else:
        current = path.read_text(encoding="utf-8")
        text = t.replace_block(current, "managed", body, "hash") or (current.rstrip("\n") + "\n\n" + t.block("managed", body, "hash"))
        if text != current:
            plan.changes.append(Change("merge", ".gitignore", text.encode()))
        else:
            plan.kept.append(".gitignore")
    records[".gitignore"] = Record(BLOCK, sha256(text.encode()))

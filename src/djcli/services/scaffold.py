"""Platform / service scaffold operations (port of .agent/setup.sh)."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import typer

from djcli.modules import paths
from djcli.modules.constants import PLATFORMS, RESERVED_SERVICE_NAMES
from djcli.modules.fsutil import copy_file, write_if_missing
from djcli.modules.prompt import abort, select_existing_platform, select_platforms
from djcli.services import wiring

_SERVICE_NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_-]*$")


def existing_platforms(root: Path) -> list[str]:
    return [p for p in PLATFORMS if (root / p).is_dir()]


def create_platform(root: Path, platform: str) -> None:
    dest = root / platform
    if dest.is_dir():
        typer.echo(f"skip (exists): {dest}/")
        return

    scripts_dir = dest / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    templates = paths.templates_dir()
    run_sh = templates / "platform" / "scripts" / "run.sh"
    run_bat = templates / "platform" / "scripts" / "run.bat"
    if not run_sh.is_file() or not run_bat.is_file():
        abort(f"missing platform scripts under {templates / 'platform' / 'scripts'}")

    shutil.copy2(run_sh, scripts_dir / "run.sh")
    shutil.copy2(run_bat, scripts_dir / "run.bat")
    (scripts_dir / "run.sh").chmod((scripts_dir / "run.sh").stat().st_mode | 0o111)

    if platform == "backend":
        proto = dest / "proto"
        proto_dist = proto / "dist"
        proto_dist.mkdir(parents=True, exist_ok=True)
        write_if_missing(proto / ".gitkeep", "")
        write_if_missing(proto_dist / ".gitkeep", "")

    typer.echo(f"created platform: {dest}/ (scripts from templates)")


def _platform_service_template_dir(platform: str, name: str) -> Path:
    templates = paths.templates_dir()
    if platform == "browser-extension" and name.startswith("native_"):
        return templates / "platform" / "backend-service"
    return templates / "platform" / platform


def _copy_platform_service_files(platform: str, name: str, dest: Path) -> None:
    src = _platform_service_template_dir(platform, name)
    if not src.is_dir():
        abort(f"missing platform template dir: {src}")

    replace = {"__NAME__": name}
    for file in sorted(src.iterdir()):
        if not file.is_file():
            continue
        target = dest / file.name
        if target.exists():
            typer.echo(f"skip (exists): {target}")
            continue
        copy_file(file, target, replace=replace, force=True)


def create_service(root: Path, platform: str, name: str) -> None:
    if not _SERVICE_NAME_RE.match(name):
        abort("invalid name: use letters, numbers, _ or -")
    if name in RESERVED_SERVICE_NAMES:
        abort(f"reserved name: {name}")

    base = root / platform / name
    if base.exists():
        abort(f"already exists: {base}")

    base.mkdir(parents=True, exist_ok=True)
    _copy_platform_service_files(platform, name, base)

    if platform in {"backend", "backend-service"}:
        for sub in ("apps", "services", "domains", "modules"):
            (base / sub).mkdir(exist_ok=True)
    elif platform == "frontend":
        (base / "src").mkdir(exist_ok=True)
    elif platform == "mobile-app":
        (base / "lib").mkdir(exist_ok=True)
    elif platform == "pc-app":
        (base / "main").mkdir(exist_ok=True)
        (base / "preload").mkdir(exist_ok=True)
        (base / "renderer" / "src").mkdir(parents=True, exist_ok=True)
    elif platform == "cli":
        for sub in ("apps", "services", "modules"):
            (base / sub).mkdir(exist_ok=True)
    elif platform == "browser-extension":
        if name.startswith("native_"):
            for sub in ("apps", "services", "modules"):
                (base / sub).mkdir(exist_ok=True)
        else:
            for sub in (
                "src/background",
                "src/content",
                "src/popup",
                "src/lib",
            ):
                (base / sub).mkdir(parents=True, exist_ok=True)
            write_if_missing(base / "manifest.json", "{}\n")

    typer.echo(f"created service: {base}/")


def _resolve_platforms(
    root: Path,
    *,
    mode: str,
    platforms: list[str] | None,
    all_platforms: bool,
) -> list[str]:
    if all_platforms:
        if mode == "add":
            existing = set(existing_platforms(root))
            return [p for p in PLATFORMS if p not in existing]
        return list(PLATFORMS)

    if platforms:
        unknown = [p for p in platforms if p not in PLATFORMS]
        if unknown:
            abort(f"unknown platform(s): {', '.join(unknown)}")
        if mode == "add":
            return [p for p in platforms if p not in set(existing_platforms(root))]
        return list(dict.fromkeys(platforms))

    return select_platforms(mode=mode, root_exists=set(existing_platforms(root)))


def bootstrap(
    root: Path,
    *,
    platforms: list[str] | None = None,
    all_platforms: bool = False,
    force: bool = False,
    mode: str = "init",
) -> None:
    """Wire agent assets, root templates, and create selected platforms."""
    typer.echo("== agent wiring ==")
    wiring.ensure_agent_wiring(root, force=force)
    typer.echo("== root templates ==")
    wiring.ensure_root_from_templates(root, force=force)
    typer.echo("== platforms ==")
    selected = _resolve_platforms(
        root,
        mode=mode,
        platforms=platforms,
        all_platforms=all_platforms,
    )
    if not selected:
        abort("no platforms available to create")
    for platform in selected:
        create_platform(root, platform)
    if mode == "init":
        typer.echo("done. Next: djcli add service")
    else:
        typer.echo("done.")


def add_service_flow(
    root: Path,
    *,
    platform: str | None = None,
    name: str | None = None,
) -> None:
    existing = existing_platforms(root)
    if platform:
        if platform not in PLATFORMS:
            abort(f"unknown platform: {platform}")
        if platform not in existing:
            abort(f"platform does not exist yet: {platform} (run: djcli add platform)")
        chosen = platform
    else:
        chosen = select_existing_platform(existing)

    if not name:
        from djcli.modules.fsutil import is_interactive

        if not is_interactive():
            abort("non-interactive stdin; pass --name")
        name = typer.prompt("Service/app name").strip()
    if not name:
        abort("name required")

    create_service(root, chosen, name)
    typer.echo(f"run: make run PLATFORM={chosen} NAME={name}")
    typer.echo(f"  or: {chosen}/scripts/run.sh {name}")

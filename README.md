# yjcli

CLI that scaffolds YJ platform folders, services, and Cursor/Claude agent wiring.

Templates, skills, and rules ship inside the package (`src/yjcli/data/`) and are **copied** into the target repo (no `.agent` / symlink).

## Develop

```bash
uv sync
uv run yjcli --help
uv run yjcli --version
```

Version: `pyproject.toml` `[project].version` only (`yjcli --version` reads package metadata).

## Commands

```bash
# Bootstrap: AGENTS.md/CLAUDE.md, .cursor/.claude skills+rules,
# root Makefile/.gitignore, selected platform roots.
uv run yjcli init
uv run yjcli init --all
uv run yjcli init -p backend -p frontend
uv run yjcli init --force              # overwrite existing agent assets

uv run yjcli add platform              # interactive: add missing platforms
uv run yjcli add platform --all
uv run yjcli add platform -p cli

uv run yjcli add service               # interactive
uv run yjcli add service -p backend -n api

uv run yjcli doctor                    # packaged asset sanity check
```

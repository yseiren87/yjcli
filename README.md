# djcli

Self-contained CLI (uv + `pyproject.toml`) that scaffolds DJ platform folders, services, and Cursor/Claude agent wiring.

All templates, skills, and rules ship inside the package (`src/djcli/data/`).

## Develop

```bash
cd djcli
uv sync
uv run djcli --help
```

## Commands

```bash
# Bootstrap current directory: AGENTS.md/CLAUDE.md, .cursor/.claude skills+rules,
# root Makefile/.gitignore, then create selected platform roots.
uv run djcli init
uv run djcli init --all
uv run djcli init -p backend -p frontend

uv run djcli add platform              # interactive: add missing platforms
uv run djcli add platform --all
uv run djcli add platform -p cli

uv run djcli add service               # interactive
uv run djcli add service -p backend -n api

uv run djcli doctor                    # packaged asset sanity check
uv run djcli --version
```

Agent assets are **copied** from the package into the target repo (no `.agent` folder).
Re-run `djcli init --force` (or answer overwrite prompts) to refresh skills/rules.

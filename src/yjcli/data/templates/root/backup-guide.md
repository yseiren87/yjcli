# Merge guide — yjcli {{version}}

yjcli ({{change}}) overwrote the files below although they had local edits. This folder holds their previous copies, at the same paths as in the repository. It is git-ignored and exists only to be merged and deleted.

Coding agent: follow these steps when the user asks you to merge this backup.

## Files

{{files}}

## Steps

1. For each row, diff the backup copy with the current file (`diff -u {{backup}}/<path> <path>`). Lines only in the backup are either local edits or text from the older yjcli template. Keep the local edits; drop old template text — the current file is the new template.
2. Move every local edit to the place given in **Move local edits to**, never back into the overwritten file: yjcli overwrites it again on the next run.
   - `SKILL.md` rules → `.yjcli/skills/<skill>.md` (create it; plain Markdown rules). yjcli appends that file to the skill for every LLM.
   - `GUIDE.md` notes → project notes outside the `<!-- yjcli:… -->` blocks of `AGENTS.md`; implementation details → the tool scripts (`tools/<tool>/<platform>/…`).
   - `AGENTS.md` / `.gitignore` → the same file, outside the yjcli blocks. Edits made inside a block belong outside it (e.g. an extra layout row → `### Project-specific paths`).
   - `Makefile` / `make.ps1` logic → the tool scripts they call; `CLAUDE.md` text → `AGENTS.md`.
3. Merge, do not duplicate: if the current file already says the same thing, skip it. Rewrite moved text to fit its new place; do not paste whole sections.
4. Run `yjcli update --dry-run` (and `yjcli update -y` when it lists changes from `.yjcli/skills/`) and check the result reads as intended.
5. Delete this folder (`{{backup}}/`) and report: per file, what was moved where and what was dropped as old template text. Ask the user before dropping anything you are unsure about.

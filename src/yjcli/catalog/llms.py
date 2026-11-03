"""LLM adapters: instruction file + skills directory + extra settings."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Extra:
    """A seed file the adapter installs once (template path under data/templates)."""

    template: str
    dest: str


@dataclass(frozen=True)
class LLM:
    id: str
    label: str
    skills_dir: str
    # File that imports AGENTS.md (None when the tool reads AGENTS.md directly).
    instructions: str | None = None
    extras: tuple[Extra, ...] = field(default_factory=tuple)


LLMS: tuple[LLM, ...] = (
    LLM(id="cursor", label="Cursor", skills_dir=".cursor/skills"),
    LLM(
        id="claude",
        label="Claude Code",
        skills_dir=".claude/skills",
        instructions="CLAUDE.md",
        extras=(Extra("root/claude-settings.json", ".claude/settings.json"),),
    ),
    LLM(id="codex", label="Codex", skills_dir=".agents/skills"),
)

LLM_BY_ID: dict[str, LLM] = {llm.id: llm for llm in LLMS}

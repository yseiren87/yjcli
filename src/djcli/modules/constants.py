"""Shared scaffold constants."""

from __future__ import annotations

PLATFORMS: tuple[str, ...] = (
    "backend",
    "backend-service",
    "frontend",
    "mobile-app",
    "pc-app",
    "cli",
    "browser-extension",
)

RESERVED_SERVICE_NAMES: frozenset[str] = frozenset({"scripts", "proto"})

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

# Env template kinds under templates/platform/envs/<kind>/
ENV_KINDS: tuple[str, ...] = ("listen", "worker", "app")

# platform -> (env kind, extra placeholder replacements)
PLATFORM_ENV: dict[str, tuple[str, dict[str, str]]] = {
    "backend": ("listen", {"__PORT__": "8080"}),
    "frontend": ("listen", {"__PORT__": "5173"}),
    "backend-service": ("worker", {}),
    "cli": ("app", {}),
    "mobile-app": ("app", {}),
    "pc-app": ("app", {}),
    "browser-extension": ("app", {}),
}

"""Codex preflight checks (non-invasive).

Epic 2 / Task 2.2: Security + approvals alignment.

We want actionable errors before attempting to run Codex:
- Codex installed
- user authenticated (ChatGPT OAuth)
- optional: MCP servers configured

Security constraints:
- Never print or log token contents.
- Prefer checks that do not require reading credential content.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import Iterable, Optional


@dataclass(frozen=True)
class PreflightResult:
    ok: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    info: tuple[str, ...] = ()


def _run(cmd: list[str], timeout_sec: int = 10) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        timeout=timeout_sec,
        check=False,
    )


def codex_binary_path() -> Optional[str]:
    return which("codex")


def is_codex_installed() -> bool:
    return codex_binary_path() is not None


def codex_version() -> Optional[str]:
    if not is_codex_installed():
        return None
    proc = _run(["codex", "--version"], timeout_sec=5)
    out = (proc.stdout or "").strip() or (proc.stderr or "").strip()
    return out or None


def codex_login_status_text() -> Optional[str]:
    """Return a short status string from `codex login status`.

    This should not contain secrets; it is a human-readable status.
    """

    if not is_codex_installed():
        return None

    proc = _run(["codex", "login", "status"], timeout_sec=10)
    text = (proc.stdout or "").strip()
    if not text:
        text = (proc.stderr or "").strip()
    return text or None


def codex_home() -> Path:
    # Codex uses CODEX_HOME with default ~/.codex according to docs.
    return Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()


def codex_auth_cache_path() -> Path:
    return codex_home() / "auth.json"


def codex_config_path() -> Path:
    return codex_home() / "config.toml"


def codex_is_logged_in_best_effort() -> bool:
    """Best-effort detection whether Codex is authenticated.

    We prefer `codex login status` (source of truth). As a fallback, we check
    for an auth cache file when file-based storage is used.
    """

    status = (codex_login_status_text() or "").strip().lower()

    # Important: "Not logged in" contains the substring "logged in".
    if "not logged in" in status:
        return False
    if "logged in" in status:
        return True

    # Fallback: presence of auth cache file (does NOT validate token).
    return codex_auth_cache_path().exists()


def codex_preflight(required_mcp_servers: Iterable[str] = ()) -> PreflightResult:
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []

    if not is_codex_installed():
        errors.append(
            "Codex CLI not found. Install with `npm i -g @openai/codex` or `brew install --cask codex`, then re-run."
        )
        return PreflightResult(ok=False, errors=tuple(errors), warnings=tuple(warnings), info=tuple(info))

    ver = codex_version()
    if ver:
        info.append(f"codex: {ver}")

    if not codex_is_logged_in_best_effort():
        errors.append(
            "Codex is not logged in. Run `codex login` (desktop) or `codex login --device-auth` (headless), then retry."
        )

    # MCP requirements are optional for MVP. Only enforce if explicitly requested.
    if required_mcp_servers:
        cfg = codex_config_path()
        if not cfg.exists():
            errors.append(
                f"Codex config not found at {cfg}. Create it and configure required MCP servers: {', '.join(required_mcp_servers)}."
            )
        else:
            # Only check for presence of server names in file text; we do not parse secrets.
            try:
                cfg_text = cfg.read_text(encoding="utf-8")
            except Exception:
                cfg_text = ""
            missing = [
                name
                for name in required_mcp_servers
                if f"[mcp_servers.{name}]" not in cfg_text
            ]
            if missing:
                errors.append(
                    "Missing required MCP server config sections in ~/.codex/config.toml: "
                    + ", ".join(missing)
                )

    ok = len(errors) == 0
    return PreflightResult(ok=ok, errors=tuple(errors), warnings=tuple(warnings), info=tuple(info))

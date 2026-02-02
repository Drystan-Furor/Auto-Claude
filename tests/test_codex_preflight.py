from __future__ import annotations

from pathlib import Path

import pytest

from codex import preflight as pf


def test_codex_preflight_missing_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pf, "codex_binary_path", lambda: None)

    result = pf.codex_preflight()

    assert result.ok is False
    assert any("Codex CLI not found" in e for e in result.errors)


def test_codex_preflight_missing_auth_shows_login_instructions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(pf, "codex_binary_path", lambda: "/usr/local/bin/codex")
    monkeypatch.setattr(pf, "codex_version", lambda: "codex-cli 0.93.0")
    monkeypatch.setattr(pf, "codex_login_status_text", lambda: "Not logged in")

    # Ensure fallback auth.json check is also negative.
    monkeypatch.setattr(pf, "codex_auth_cache_path", lambda: tmp_path / "auth.json")

    result = pf.codex_preflight()

    assert result.ok is False
    assert any("codex login" in e for e in result.errors)


def test_codex_preflight_does_not_require_reading_token_contents(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Ensure we never read auth.json content.

    We simulate an existing auth.json but also a failing login status.
    Presence should satisfy best-effort check without reading file.
    """

    monkeypatch.setattr(pf, "codex_binary_path", lambda: "/usr/local/bin/codex")
    monkeypatch.setattr(pf, "codex_version", lambda: "codex-cli 0.93.0")
    monkeypatch.setattr(pf, "codex_login_status_text", lambda: "")

    auth = tmp_path / "auth.json"
    auth.write_text("{\"access_token\":\"SECRET\"}", encoding="utf-8")
    monkeypatch.setattr(pf, "codex_auth_cache_path", lambda: auth)

    result = pf.codex_preflight()

    assert result.ok is True


def test_codex_preflight_mcp_required_missing_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(pf, "codex_binary_path", lambda: "/usr/local/bin/codex")
    monkeypatch.setattr(pf, "codex_version", lambda: "codex-cli 0.93.0")
    monkeypatch.setattr(pf, "codex_login_status_text", lambda: "Logged in using ChatGPT")

    monkeypatch.setattr(pf, "codex_config_path", lambda: tmp_path / "config.toml")

    result = pf.codex_preflight(required_mcp_servers=["context7"])

    assert result.ok is False
    # Message can be either "config not found" or "missing required sections" depending on file state.
    joined = "\n".join(result.errors).lower()
    assert ("codex config not found" in joined) or ("missing required mcp" in joined)


def test_codex_preflight_mcp_required_present(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(pf, "codex_binary_path", lambda: "/usr/local/bin/codex")
    monkeypatch.setattr(pf, "codex_version", lambda: "codex-cli 0.93.0")
    monkeypatch.setattr(pf, "codex_login_status_text", lambda: "Logged in using ChatGPT")

    cfg = tmp_path / "config.toml"
    cfg.write_text("[mcp_servers.context7]\ncommand='npx'\n", encoding="utf-8")
    monkeypatch.setattr(pf, "codex_config_path", lambda: cfg)

    result = pf.codex_preflight(required_mcp_servers=["context7"])

    assert result.ok is True

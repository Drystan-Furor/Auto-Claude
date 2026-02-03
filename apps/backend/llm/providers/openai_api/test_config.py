from __future__ import annotations

import os

import pytest

from llm.errors import AuthError
from llm.providers.openai_api.config import OpenAIConfig


def test_from_env_missing_key_raises_auth_error(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")

    with pytest.raises(AuthError):
        OpenAIConfig.from_env()


def test_from_env_defaults_model(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    cfg = OpenAIConfig.from_env()
    assert cfg.api_key == "dummy"
    assert cfg.model
    assert cfg.base_url is None


def test_from_env_reads_base_url(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:1234/v1")

    cfg = OpenAIConfig.from_env()
    assert cfg.base_url == "http://localhost:1234/v1"

from __future__ import annotations

import os
from pathlib import Path

import pytest


def _enabled() -> bool:
    return os.environ.get("RUN_GRAPHITI_TESTS", "").lower() in ("1", "true", "yes")


@pytest.fixture
def db_path(tmp_path_factory: pytest.TempPathFactory) -> str:
    # Use a temp location by default; integration tests may override via env.
    return str(tmp_path_factory.mktemp("graphiti_db"))


@pytest.fixture
def database() -> str:
    return "test_graphiti"


@pytest.fixture
def test_db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("graphiti_ollama")


@pytest.fixture
def group_id() -> str:
    return "test_group"

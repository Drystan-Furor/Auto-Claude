"""OpenAI API provider configuration.

Epic 3 / Task 3.2: roadmap/03-backlog-and-tasks-tdd.md

Keep this intentionally small: env parsing + validation.
"""

from __future__ import annotations

from dataclasses import dataclass
import os

from llm.errors import AuthError, ConfigError


@dataclass(frozen=True)
class OpenAIConfig:
    api_key: str
    model: str
    base_url: str | None = None

    @classmethod
    def from_env(cls) -> "OpenAIConfig":
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        model = os.environ.get("OPENAI_MODEL", "").strip() or "gpt-4o-mini"
        base_url = os.environ.get("OPENAI_BASE_URL", "").strip() or None

        if not api_key:
            # Task 3.2: missing key should be an AuthError (not a generic ValueError)
            raise AuthError(
                "Missing OPENAI_API_KEY. Set OPENAI_API_KEY to use provider=openai."
            )

        if not model:
            # Should be unreachable due to defaulting, but keep explicit.
            raise ConfigError("Missing OPENAI_MODEL")

        return cls(api_key=api_key, model=model, base_url=base_url)

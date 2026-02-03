"""OpenAI API provider configuration.

Epic 3 / Task 3.2: roadmap/03-backlog-and-tasks-tdd.md

Keep this intentionally small: env parsing + validation.
"""

from __future__ import annotations

from dataclasses import dataclass
import os


class OpenAIConfigError(ValueError):
    pass


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
            raise OpenAIConfigError(
                "Missing OPENAI_API_KEY. Set OPENAI_API_KEY or choose a different provider."
            )

        return cls(api_key=api_key, model=model, base_url=base_url)

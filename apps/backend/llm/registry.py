"""Engine registry.

For now this is a small indirection layer that lets the rest of the backend
select an engine by name.

Epic 1 / Task 1.4: roadmap/03-backlog-and-tasks-tdd.md
"""

from __future__ import annotations

from dataclasses import dataclass

from .engine import LLMEngine


@dataclass(frozen=True)
class EngineSpec:
    provider: str


def create_engine(provider: str, **kwargs) -> LLMEngine:
    """Factory for engines.

    Notes:
    - We intentionally import provider implementations lazily.
    - kwargs are provider-specific (client, config, etc.).
    """

    if provider in ("claude", "claude_sdk"):
        from .providers.claude_sdk.engine import ClaudeSDKEngine

        client = kwargs.get("client")
        if client is None:
            raise ValueError("ClaudeSDKEngine requires client=<ClaudeSDKClient>")
        return ClaudeSDKEngine(client=client)

    if provider in ("openai", "openai_api"):
        from .providers.openai_api.engine import OpenAIAPIEngine

        # client/config/tools are optional; if client is None, engine loads config
        # from env and constructs an OpenAI SDK client.
        return OpenAIAPIEngine(
            client=kwargs.get("client"),
            config=kwargs.get("config"),
            tools=kwargs.get("tools"),
        )

    raise ValueError(f"Unknown LLM provider: {provider}")

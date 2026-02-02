from __future__ import annotations

from typing import AsyncIterator, List

import pytest

from apps.backend.llm.engine import LLMEngine
from apps.backend.llm.types import StreamEvent, TextEvent, ToolResult


class FakeEngine(LLMEngine):
    def __init__(self) -> None:
        self.prompts: List[str] = []
        self.tool_results: List[ToolResult] = []

    async def start(self, prompt: str) -> None:
        self.prompts.append(prompt)

    async def send_tool_result(self, result: ToolResult) -> None:
        self.tool_results.append(result)

    async def _stream(self) -> AsyncIterator[StreamEvent]:
        yield TextEvent(text="ok")

    def stream(self) -> AsyncIterator[StreamEvent]:
        return self._stream()


@pytest.mark.asyncio
async def test_fake_engine_satisfies_interface() -> None:
    engine: LLMEngine = FakeEngine()

    await engine.start("hello")
    events = [ev async for ev in engine.stream()]

    assert engine is not None
    assert events == [TextEvent(text="ok")]

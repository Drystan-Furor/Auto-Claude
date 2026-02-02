from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, List

import pytest

from agents.session import run_llm_session
from llm.engine import LLMEngine
from llm.types import TextEvent, ToolCall, ToolCallEvent, ToolResultEvent, ToolResult


class FakeEngine(LLMEngine):
    def __init__(self):
        self.started: List[str] = []

    async def start(self, prompt: str) -> None:
        self.started.append(prompt)

    def stream(self) -> AsyncIterator:
        return self._stream()

    async def send_tool_result(self, result: ToolResult) -> None:
        # Not used in this harness; provider-managed tools.
        return None

    async def _stream(self) -> AsyncIterator:
        yield TextEvent(text="hello")
        yield ToolCallEvent(tool_call=ToolCall(id="t1", name="Read", input={"path": "x"}))
        yield ToolResultEvent(tool_result=ToolResult(id="t1", content="ok", is_error=False))
        yield TextEvent(text=" world")


@pytest.mark.asyncio
async def test_run_llm_session_collects_response_text(tmp_path: Path) -> None:
    engine = FakeEngine()

    status, response_text, error = await run_llm_session(
        engine=engine,
        message="do thing",
        spec_dir=tmp_path,
        verbose=False,
    )

    assert engine.started == ["do thing"]
    assert error == {}
    assert response_text == "hello world"
    assert status in ("continue", "complete")

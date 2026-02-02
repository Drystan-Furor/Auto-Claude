"""Engine contract harness (provider-neutral)

Epic 0, Task 0.1 in roadmap/03-backlog-and-tasks-tdd.md

Intent:
- Establish a minimal, provider-neutral streaming + tool-call contract
  that we can keep stable while we refactor the Claude-specific session
  implementation into an LLMEngine abstraction.

Constraints:
- These tests MUST NOT import claude_agent_sdk (or any provider SDK).
- These tests do not change production behavior; they only codify the
  semantics we want to preserve.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional

import pytest


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    input: Dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    id: str
    content: str
    is_error: bool = False


@dataclass(frozen=True)
class StreamEvent:
    """A minimal event stream contract.

    We keep it deliberately small to avoid overfitting to any one provider.
    """

    type: str  # "text" | "tool_call" | "tool_result"
    text: Optional[str] = None
    tool_call: Optional[ToolCall] = None
    tool_result: Optional[ToolResult] = None


class FakeToolRunner:
    def __init__(self, results: Dict[str, ToolResult]):
        self._results = results
        self.calls: List[ToolCall] = []

    async def run(self, call: ToolCall) -> ToolResult:
        self.calls.append(call)
        if call.id not in self._results:
            return ToolResult(id=call.id, content=f"no result configured for {call.id}", is_error=True)
        return self._results[call.id]


class FakeEngine:
    """A fake engine that emits a scripted event sequence."""

    def __init__(self, script: List[StreamEvent]):
        self._script = script
        self.tool_results_received: List[ToolResult] = []

    async def stream(self) -> AsyncIterator[StreamEvent]:
        for ev in self._script:
            yield ev

    async def send_tool_result(self, result: ToolResult) -> None:
        self.tool_results_received.append(result)


async def run_session(engine: FakeEngine, tool_runner: FakeToolRunner) -> List[StreamEvent]:
    """Provider-neutral session loop.

    This mirrors the structure we eventually want in apps/backend/agents/session.py:
    - consume engine stream
    - when a tool is requested, run tool and feed result back
    - keep emitting events in order
    """

    out: List[StreamEvent] = []

    async for ev in engine.stream():
        out.append(ev)

        if ev.type == "tool_call":
            assert ev.tool_call is not None
            result = await tool_runner.run(ev.tool_call)
            await engine.send_tool_result(result)
            out.append(StreamEvent(type="tool_result", tool_result=result))

    return out


@pytest.mark.asyncio
async def test_session_emits_text_events_in_order() -> None:
    engine = FakeEngine(
        script=[
            StreamEvent(type="text", text="hello"),
            StreamEvent(type="text", text=" "),
            StreamEvent(type="text", text="world"),
        ]
    )
    tool_runner = FakeToolRunner(results={})

    events = await run_session(engine, tool_runner)

    assert [e.type for e in events] == ["text", "text", "text"]
    assert "".join(e.text or "" for e in events) == "hello world"
    assert tool_runner.calls == []


@pytest.mark.asyncio
async def test_session_requests_tool_and_receives_result() -> None:
    call = ToolCall(id="t1", name="Read", input={"path": "README.md"})
    engine = FakeEngine(
        script=[
            StreamEvent(type="text", text="need file"),
            StreamEvent(type="tool_call", tool_call=call),
            StreamEvent(type="text", text="thanks"),
        ]
    )
    tool_runner = FakeToolRunner(results={"t1": ToolResult(id="t1", content="ok")})

    events = await run_session(engine, tool_runner)

    assert [e.type for e in events] == ["text", "tool_call", "tool_result", "text"]
    assert tool_runner.calls == [call]
    assert engine.tool_results_received == [ToolResult(id="t1", content="ok")]

    tool_result_events = [e for e in events if e.type == "tool_result"]
    assert tool_result_events[0].tool_result == ToolResult(id="t1", content="ok")


@pytest.mark.asyncio
async def test_session_handles_tool_error() -> None:
    call = ToolCall(id="t_err", name="Bash", input={"command": "rm -rf /"})
    engine = FakeEngine(
        script=[
            StreamEvent(type="tool_call", tool_call=call),
            StreamEvent(type="text", text="continue after error"),
        ]
    )
    tool_runner = FakeToolRunner(
        results={
            "t_err": ToolResult(id="t_err", content="BLOCKED", is_error=True),
        }
    )

    events = await run_session(engine, tool_runner)

    assert [e.type for e in events] == ["tool_call", "tool_result", "text"]
    assert tool_runner.calls == [call]
    assert engine.tool_results_received == [ToolResult(id="t_err", content="BLOCKED", is_error=True)]

    tool_result = next(e.tool_result for e in events if e.type == "tool_result")
    assert tool_result is not None
    assert tool_result.is_error is True
    assert tool_result.content == "BLOCKED"

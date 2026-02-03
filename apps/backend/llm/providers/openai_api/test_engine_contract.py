from __future__ import annotations

import types

import pytest

from llm.providers.openai_api.engine import OpenAIAPIEngine
from llm.providers.openai_api.config import OpenAIConfig
from llm.types import TextEvent, ToolCallEvent, ToolResult


class _Ev:
    def __init__(self, type: str, **kwargs):
        self.type = type
        for k, v in kwargs.items():
            setattr(self, k, v)


class _Resp:
    def __init__(self, id: str):
        self.id = id


class FakeResponses:
    def __init__(self, scripted_streams: list[list[object]]):
        self._streams = scripted_streams
        self._calls: list[dict] = []

    async def create(self, **kwargs):
        self._calls.append(kwargs)
        stream = self._streams.pop(0)

        async def _gen():
            for x in stream:
                yield x

        return _gen()


class FakeOpenAI:
    def __init__(self, scripted_streams: list[list[object]]):
        self.responses = FakeResponses(scripted_streams)


@pytest.mark.asyncio
async def test_openai_engine_streams_text_deltas():
    client = FakeOpenAI(
        scripted_streams=[
            [
                _Ev("response.created", response=_Resp("r1")),
                _Ev("response.output_text.delta", delta="hel"),
                _Ev("response.output_text.delta", delta="lo"),
                _Ev("response.completed", response=_Resp("r1")),
            ]
        ]
    )

    engine = OpenAIAPIEngine(
        client=client,
        config=OpenAIConfig(api_key="dummy", model="gpt-test", base_url=None),
    )
    await engine.start("hi")

    out = []
    async for ev in engine.stream():
        out.append(ev)

    assert [e.text for e in out if isinstance(e, TextEvent)] == ["hel", "lo"]


@pytest.mark.asyncio
async def test_openai_engine_emits_tool_call_roundtrip():
    client = FakeOpenAI(
        scripted_streams=[
            # First turn: model requests a function call
            [
                _Ev("response.created", response=_Resp("r1")),
                _Ev(
                    "response.output_item.added",
                    item=types.SimpleNamespace(
                        type="function_call", id="call_1", name="sum"
                    ),
                ),
                _Ev("response.function_call_arguments.delta", call_id="call_1", delta="{\"a\":1"),
                _Ev("response.function_call_arguments.delta", call_id="call_1", delta=",\"b\":2}"),
                _Ev("response.function_call_arguments.done", call_id="call_1"),
                _Ev("response.completed", response=_Resp("r1")),
            ],
            # Second turn: after tool result, model streams text
            [
                _Ev("response.created", response=_Resp("r2")),
                _Ev("response.output_text.delta", delta="3"),
                _Ev("response.completed", response=_Resp("r2")),
            ],
        ]
    )

    engine = OpenAIAPIEngine(
        client=client,
        config=OpenAIConfig(api_key="dummy", model="gpt-test", base_url=None),
        tools=[{"type": "function", "function": {"name": "sum", "parameters": {"type": "object"}}}],
    )

    await engine.start("add")

    tool_calls = []
    async for ev in engine.stream():
        if isinstance(ev, ToolCallEvent):
            tool_calls.append(ev)

    assert len(tool_calls) == 1
    assert tool_calls[0].tool_call is not None
    assert tool_calls[0].tool_call.id == "call_1"
    assert tool_calls[0].tool_call.name == "sum"
    assert tool_calls[0].tool_call.input == {"a": 1, "b": 2}

    await engine.send_tool_result(ToolResult(id="call_1", content="3"))

    texts = []
    async for ev in engine.stream():
        if isinstance(ev, TextEvent):
            texts.append(ev.text)

    assert "".join(texts) == "3"

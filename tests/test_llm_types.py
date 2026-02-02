from __future__ import annotations

from apps.backend.llm.types import (
    TextEvent,
    ToolCall,
    ToolCallEvent,
    ToolResult,
    ToolResultEvent,
    event_text,
    is_tool_call,
    is_tool_result,
)


def test_event_text_extracts_only_text() -> None:
    assert event_text(TextEvent(text="hi")) == "hi"

    call = ToolCall(id="t1", name="Read", input={"path": "README.md"})
    assert event_text(ToolCallEvent(tool_call=call)) == ""

    result = ToolResult(id="t1", content="ok")
    assert event_text(ToolResultEvent(tool_result=result)) == ""


def test_tool_helpers() -> None:
    call = ToolCall(id="t1", name="Read", input={"path": "README.md"})
    assert is_tool_call(ToolCallEvent(tool_call=call)) is True
    assert is_tool_call(ToolCallEvent(tool_call=None)) is False

    result = ToolResult(id="t1", content="ok")
    assert is_tool_result(ToolResultEvent(tool_result=result)) is True
    assert is_tool_result(ToolResultEvent(tool_result=None)) is False

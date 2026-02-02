from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

from llm.observability import ToolObservationState, observe_event
from llm.types import TextEvent, ToolCall, ToolCallEvent, ToolResult, ToolResultEvent


@dataclass
class LogCall:
    kind: str
    name: Optional[str] = None
    payload: Any = None


class FakeTaskLogger:
    def __init__(self) -> None:
        self.calls: List[LogCall] = []

    def log(self, text: str, entry_type: str, phase: object, print_to_console: bool = False) -> None:
        self.calls.append(LogCall(kind="log", payload={"text": text, "entry_type": entry_type}))

    def tool_start(self, name: str, input_display: Optional[str], phase: object, print_to_console: bool = True) -> None:
        self.calls.append(LogCall(kind="tool_start", name=name, payload={"input_display": input_display}))

    def tool_end(self, name: str, success: bool, result: str | None = None, detail: str | None = None, phase: object | None = None) -> None:
        self.calls.append(LogCall(kind="tool_end", name=name, payload={"success": success, "result": result, "detail": detail}))


def test_observability_emits_tool_start_then_tool_end() -> None:
    logger = FakeTaskLogger()
    state = ToolObservationState()

    observe_event(
        ev=ToolCallEvent(tool_call=ToolCall(id="t1", name="Read", input={"path": "README.md"})),
        state=state,
        task_logger=logger,
        phase="coding",
    )
    observe_event(
        ev=ToolResultEvent(tool_result=ToolResult(id="t1", content="ok", is_error=False)),
        state=state,
        task_logger=logger,
        phase="coding",
    )

    assert [c.kind for c in logger.calls] == ["tool_start", "tool_end"]
    assert logger.calls[0].name == "Read"
    assert logger.calls[1].name == "Read"
    assert logger.calls[1].payload["success"] is True


def test_observability_marks_blocked_as_failure() -> None:
    logger = FakeTaskLogger()
    state = ToolObservationState(current_tool_name="Bash")

    observe_event(
        ev=ToolResultEvent(tool_result=ToolResult(id="t1", content="BLOCKED: nope", is_error=True)),
        state=state,
        task_logger=logger,
        phase="coding",
    )

    assert logger.calls[0].kind == "tool_end"
    assert logger.calls[0].payload["success"] is False
    assert logger.calls[0].payload["result"] == "BLOCKED"


def test_observability_logs_text_without_double_print() -> None:
    logger = FakeTaskLogger()
    state = ToolObservationState()

    observe_event(
        ev=TextEvent(text="hello"),
        state=state,
        task_logger=logger,
        phase="coding",
        text_entry_type="text",
    )

    assert logger.calls and logger.calls[0].kind == "log"
    assert logger.calls[0].payload["entry_type"] == "text"

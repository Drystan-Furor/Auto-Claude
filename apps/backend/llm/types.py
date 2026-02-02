"""Provider-neutral LLM types.

Goal: define minimal, stable data structures for streaming model output and
requesting/executing tools. These types should be independent of any provider
SDK (Claude/OpenAI/Codex).

Epic 1 / Task 1.1: roadmap/03-backlog-and-tasks-tdd.md
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, Union


@dataclass(frozen=True)
class ToolCall:
    """A request from the engine to execute a named tool."""

    id: str
    name: str
    input: Dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    """A tool execution result that can be fed back to the engine."""

    id: str
    content: str
    is_error: bool = False


@dataclass(frozen=True)
class TextEvent:
    type: Literal["text"] = "text"
    text: str = ""


@dataclass(frozen=True)
class ToolCallEvent:
    type: Literal["tool_call"] = "tool_call"
    tool_call: ToolCall | None = None


@dataclass(frozen=True)
class ToolResultEvent:
    type: Literal["tool_result"] = "tool_result"
    tool_result: ToolResult | None = None


StreamEvent = Union[TextEvent, ToolCallEvent, ToolResultEvent]


def event_text(ev: StreamEvent) -> str:
    """Best-effort text extraction.

    Useful for tests and logging.
    """

    if isinstance(ev, TextEvent):
        return ev.text
    return ""


def is_tool_call(ev: StreamEvent) -> bool:
    return isinstance(ev, ToolCallEvent) and ev.tool_call is not None


def is_tool_result(ev: StreamEvent) -> bool:
    return isinstance(ev, ToolResultEvent) and ev.tool_result is not None

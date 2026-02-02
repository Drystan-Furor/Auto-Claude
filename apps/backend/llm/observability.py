"""LLM tool observability helpers.

Epic 2 / Task 2.3:
- We want to surface "what tools were used" to logs/UI without executing tools
  in Python.

This module defines a small adapter that maps StreamEvent objects to TaskLogger
calls in a stable, provider-neutral way.

Notes:
- The current Claude SDK engine already yields ToolCallEvent/ToolResultEvent.
- Future Codex providers should also emit these events so the UI can show tool
  usage consistently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from llm.types import StreamEvent, TextEvent, ToolCallEvent, ToolResultEvent


@dataclass
class ToolObservationState:
    current_tool_name: Optional[str] = None


def _tool_input_display(inp: object) -> Optional[str]:
    if not isinstance(inp, dict) or not inp:
        return None

    if "pattern" in inp:
        return f"pattern: {inp['pattern']}"
    if "file_path" in inp:
        fp = str(inp["file_path"])
        return ("..." + fp[-47:]) if len(fp) > 50 else fp
    if "command" in inp:
        cmd = str(inp["command"])
        return (cmd[:47] + "...") if len(cmd) > 50 else cmd
    if "path" in inp:
        return str(inp["path"])

    return None


def observe_event(
    *,
    ev: StreamEvent,
    state: ToolObservationState,
    task_logger: object | None,
    phase: object,
    verbose: bool = False,
) -> None:
    """Map StreamEvent -> TaskLogger tool/text events.

    We keep `task_logger` typed as object to avoid importing the TaskLogger class
    and creating circular dependencies.

    Expected TaskLogger methods (duck-typed):
    - log(text, entry_type, phase, print_to_console=False)
    - tool_start(name, input_display, phase, print_to_console=True)
    - tool_end(name, success: bool, result: str|None = None, detail: str|None=None, phase=phase)
    """

    if task_logger is None:
        return

    if isinstance(ev, TextEvent):
        text = ev.text
        if text.strip():
            # Avoid double-printing; session loop handles console output.
            task_logger.log(text, "text", phase, print_to_console=False)
        return

    if isinstance(ev, ToolCallEvent) and ev.tool_call is not None:
        state.current_tool_name = ev.tool_call.name
        inp = ev.tool_call.input or {}
        task_logger.tool_start(
            ev.tool_call.name,
            _tool_input_display(inp),
            phase,
            print_to_console=True,
        )
        return

    if isinstance(ev, ToolResultEvent) and ev.tool_result is not None:
        # We may not have a tool name (depends on provider), so fall back to state.
        name = state.current_tool_name or "(unknown)"
        is_error = bool(ev.tool_result.is_error)
        content = str(ev.tool_result.content)

        if is_error and "blocked" in content.lower():
            task_logger.tool_end(
                name,
                success=False,
                result="BLOCKED",
                detail=content,
                phase=phase,
            )
        elif is_error:
            task_logger.tool_end(
                name,
                success=False,
                result=content[:100],
                detail=content,
                phase=phase,
            )
        else:
            # Keep large outputs out of details by default.
            detail = None
            if verbose and len(content) < 50000:
                detail = content
            task_logger.tool_end(
                name,
                success=True,
                detail=detail,
                phase=phase,
            )

        state.current_tool_name = None

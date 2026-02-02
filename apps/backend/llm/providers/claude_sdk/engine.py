"""Claude SDK backed LLMEngine.

NOTE: This is an adapter around the existing claude_agent_sdk streaming model.
It is intentionally lightweight: we map SDK stream messages into provider-neutral
StreamEvent objects.

Epic 1 / Task 1.4: roadmap/03-backlog-and-tasks-tdd.md
"""

from __future__ import annotations

from typing import AsyncIterator, Optional

from ...engine import LLMEngine
from ...types import (
    StreamEvent,
    TextEvent,
    ToolCall,
    ToolCallEvent,
    ToolResult,
    ToolResultEvent,
)


class ClaudeSDKEngine(LLMEngine):
    def __init__(self, client: object):
        # We keep typing loose here to avoid importing claude_agent_sdk at import
        # time in environments that don't have it installed.
        self._client = client
        self._started = False
        self._pending_tool_results: list[ToolResult] = []

    async def start(self, prompt: str) -> None:
        # Claude SDK expects `await client.query(prompt)`.
        await self._client.query(prompt)
        self._started = True

    async def send_tool_result(self, result: ToolResult) -> None:
        # In the current Claude Agent SDK integration, tool execution is handled
        # internally (tools/hooks configured on the SDK client). So we don't have
        # a way to feed tool results back today.
        #
        # We keep this method for forward compatibility (when we externalize tool
        # execution in Epic 2/3).
        self._pending_tool_results.append(result)

    def stream(self) -> AsyncIterator[StreamEvent]:
        return self._stream_impl()

    async def _stream_impl(self) -> AsyncIterator[StreamEvent]:
        if not self._started:
            raise RuntimeError("ClaudeSDKEngine.stream() called before start()")

        async for msg in self._client.receive_response():
            msg_type = type(msg).__name__

            if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    block_type = type(block).__name__

                    if block_type == "TextBlock" and hasattr(block, "text"):
                        yield TextEvent(text=block.text)

                    elif block_type == "ToolUseBlock" and hasattr(block, "name"):
                        tool_id = getattr(block, "id", None) or getattr(
                            block, "tool_use_id", None
                        )
                        if tool_id is None:
                            # Fall back to a stable-ish synthetic id.
                            tool_id = f"tool:{block.name}"

                        tool_input = getattr(block, "input", None)
                        if not isinstance(tool_input, dict):
                            tool_input = {}

                        yield ToolCallEvent(
                            tool_call=ToolCall(
                                id=str(tool_id),
                                name=str(block.name),
                                input=tool_input,
                            )
                        )

            elif msg_type == "UserMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    if type(block).__name__ == "ToolResultBlock":
                        tool_id = getattr(block, "tool_use_id", None) or getattr(
                            block, "id", None
                        )
                        if tool_id is None:
                            tool_id = "tool:unknown"

                        content = getattr(block, "content", "")
                        is_error = bool(getattr(block, "is_error", False))

                        yield ToolResultEvent(
                            tool_result=ToolResult(
                                id=str(tool_id),
                                content=str(content),
                                is_error=is_error,
                            )
                        )

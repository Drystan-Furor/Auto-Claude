"""OpenAI API backed LLMEngine.

Implements the provider-neutral streaming interface using OpenAI's Responses API.

Roadmap: Epic 3 / Task 3.1
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, Optional

from ...engine import LLMEngine
from ...types import StreamEvent, TextEvent, ToolCall, ToolCallEvent, ToolResult
from .config import OpenAIConfig


@dataclass
class _PendingCall:
    name: str
    arguments_json: str = ""


class OpenAIAPIEngine(LLMEngine):
    """LLMEngine adapter for OpenAI HTTP API.

    Notes:
    - We keep the OpenAI SDK import optional by accepting an injected client.
    - For production usage, pass client=None and we will construct AsyncOpenAI.
    """

    def __init__(
        self,
        *,
        client: object | None = None,
        config: OpenAIConfig | None = None,
        tools: list[dict[str, Any]] | None = None,
    ):
        self._config = config
        self._client = client
        self._tools = tools or []

        self._started = False
        self._response_id: str | None = None
        self._stream_iter: Any = None

        # Accumulators for streaming function-call args
        self._pending_calls: dict[str, _PendingCall] = {}

    async def start(self, prompt: str) -> None:
        if self._client is None:
            cfg = self._config or OpenAIConfig.from_env()
            # Import lazily so environments without openai installed can still
            # import the module (as long as they don't instantiate it).
            from openai import AsyncOpenAI  # type: ignore

            self._client = AsyncOpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
            self._config = cfg

        if self._config is None:
            # If caller injects a client, they still should provide config (model).
            self._config = OpenAIConfig.from_env()

        # Responses API: stream events
        # We deliberately keep the "input" structure minimal for now.
        self._stream_iter = await self._client.responses.create(  # type: ignore[attr-defined]
            model=self._config.model,
            input=prompt,
            tools=self._tools or None,
            stream=True,
        )
        self._started = True

    def stream(self) -> AsyncIterator[StreamEvent]:
        return self._stream_impl()

    async def send_tool_result(self, result: ToolResult) -> None:
        if self._client is None or self._config is None:
            raise RuntimeError("OpenAIAPIEngine.send_tool_result() called before start()")

        if not self._response_id:
            # Best-effort: continue without a previous id.
            prev = None
        else:
            prev = self._response_id

        tool_output = {
            "type": "function_call_output",
            "call_id": result.id,
            "output": result.content,
        }

        self._stream_iter = await self._client.responses.create(  # type: ignore[attr-defined]
            model=self._config.model,
            previous_response_id=prev,
            input=[tool_output],
            tools=self._tools or None,
            stream=True,
        )

    async def _stream_impl(self) -> AsyncIterator[StreamEvent]:
        if not self._started:
            raise RuntimeError("OpenAIAPIEngine.stream() called before start()")

        async for ev in self._stream_iter:
            ev_type = getattr(ev, "type", None)

            # Track response id when available.
            if ev_type in ("response.created", "response.in_progress", "response.completed"):
                rid = getattr(getattr(ev, "response", None), "id", None) or getattr(ev, "response_id", None)
                if isinstance(rid, str) and rid:
                    self._response_id = rid

            # Text deltas
            if ev_type == "response.output_text.delta":
                delta = getattr(ev, "delta", "")
                if delta:
                    yield TextEvent(text=str(delta))
                continue

            # Function call discovered
            if ev_type == "response.output_item.added":
                item = getattr(ev, "item", None)
                if getattr(item, "type", None) == "function_call":
                    call_id = str(getattr(item, "id", ""))
                    name = str(getattr(item, "name", ""))
                    if call_id and name:
                        self._pending_calls[call_id] = _PendingCall(name=name)
                continue

            # Function-call args streaming
            if ev_type == "response.function_call_arguments.delta":
                call_id = str(getattr(ev, "call_id", ""))
                delta = str(getattr(ev, "delta", ""))
                if call_id and call_id in self._pending_calls and delta:
                    self._pending_calls[call_id].arguments_json += delta
                continue

            # Function-call args completed => emit ToolCallEvent
            if ev_type == "response.function_call_arguments.done":
                call_id = str(getattr(ev, "call_id", ""))
                pending = self._pending_calls.get(call_id)
                if not pending:
                    continue

                raw = pending.arguments_json.strip() or "{}"
                try:
                    parsed = json.loads(raw)
                except Exception:
                    parsed = {}

                if not isinstance(parsed, dict):
                    parsed = {}

                yield ToolCallEvent(
                    tool_call=ToolCall(id=call_id, name=pending.name, input=parsed)
                )
                continue

            # Ignore the rest for now (status, logs, etc.)

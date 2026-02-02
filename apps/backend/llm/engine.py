"""Engine interface.

This defines the minimal async interface that an LLM provider implementation
must satisfy.

Epic 1 / Task 1.2: roadmap/03-backlog-and-tasks-tdd.md
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator

from .types import StreamEvent, ToolResult


class LLMEngine(ABC):
    """Provider-neutral engine interface."""

    @abstractmethod
    async def start(self, prompt: str) -> None:
        """Start a new request (or turn) with the given prompt."""

    @abstractmethod
    def stream(self) -> AsyncIterator[StreamEvent]:
        """Yield StreamEvent objects for the current turn."""

    @abstractmethod
    async def send_tool_result(self, result: ToolResult) -> None:
        """Feed a tool result back to the engine to continue execution."""

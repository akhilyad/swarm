"""Tests for tool-calling integration in the agent loop.

Uses LiteLLM native function-calling — fake LLM functions return
``LLMResponse`` objects with ``tool_calls`` instead of raw text.
"""

from __future__ import annotations

import pytest

from src.communication.bus import MessageBus
from src.communication.message import create_goal_message
from src.core.node import NodeHandle
from src.core.types import GoalStatus, Message, MessageType, Role, SwarmNode
from src.llm.client import LLMResponse, ToolCall
from src.runtime.agent_loop import AgentLoop
from src.tools.base import BaseTool, ToolRegistry, ToolResult


class _CalculatorTool(BaseTool):
    """Simple arithmetic tool for testing."""
    name = "calculate"
    description = "Perform arithmetic"
    parameters = {
        "type": "object",
        "properties": {
            "expr": {"type": "string", "description": "Expression"},
        },
        "required": ["expr"],
    }

    async def execute(self, **kwargs: str) -> ToolResult:
        expr = kwargs.get("expr", "")
        try:
            result = eval(expr, {"__builtins__": {}}, {})  # noqa: PGH001
            return ToolResult(success=True, output=str(result))
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class _NoopTool(BaseTool):
    name = "noop"
    description = "Does nothing"
    parameters = {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs: str) -> ToolResult:
        return ToolResult(success=True, output="done")


class TestAgentLoopToolIntegration:
    @pytest.fixture
    def bus(self) -> MessageBus:
        return MessageBus()

    @pytest.fixture
    def registry(self) -> ToolRegistry:
        reg = ToolRegistry()
        reg.register(_CalculatorTool())
        reg.register(_NoopTool())
        return reg

    async def test_worker_uses_tool_when_llm_calls_it(self, bus: MessageBus, registry: ToolRegistry) -> None:
        """LLM returns a tool call, tool executes, result is included in response."""
        node = SwarmNode(node_id="worker", name="Worker", role=Role.WORKER)
        handle = NodeHandle(node=node)

        call_count = 0

        async def fake_llm(prompt: str, ctx: dict, **kwargs) -> LLMResponse:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return LLMResponse(
                    content="",
                    tool_calls=[ToolCall(name="calculate", arguments={"expr": "2+2"})],
                )
            return LLMResponse(content="The result is 4.", tool_calls=[])

        loop = AgentLoop(handle=handle, bus=bus, llm_func=fake_llm, tool_registry=registry)

        results: list[str] = []

        async def collect(msg: object) -> None:
            if hasattr(msg, "type") and msg.type in (MessageType.RESULT, MessageType.ERROR):
                results.append(msg.content)

        bus.subscribe("ceo", collect)
        await loop.start()

        msg = create_goal_message(sender="ceo", recipient="worker", goal_description="Calculate 2+2")
        await bus.publish(msg)

        import asyncio
        await asyncio.sleep(0.3)

        assert len(results) == 1
        assert "The result is 4." in results[0]
        assert call_count == 2
        await loop.stop()

    async def test_worker_reports_unavailable_tool(self, bus: MessageBus) -> None:
        """LLM calls a tool not in the registry — worker sends CLARIFY upward."""
        node = SwarmNode(node_id="worker", name="Worker", role=Role.WORKER)
        handle = NodeHandle(node=node)
        registry = ToolRegistry()

        async def fake_llm(prompt: str, ctx: dict, **kwargs) -> LLMResponse:
            return LLMResponse(
                content="",
                tool_calls=[ToolCall(name="nonexistent_tool", arguments={"arg": "val"})],
            )

        loop = AgentLoop(
            handle=handle, bus=bus, llm_func=fake_llm, tool_registry=registry,
            max_tool_iterations=3,
        )

        clarify_messages: list[str] = []

        async def collect(msg: object) -> None:
            if hasattr(msg, "type") and msg.type == MessageType.CLARIFY:
                clarify_messages.append(
                    msg.content if hasattr(msg, "content") else ""
                )

        bus.subscribe("ceo", collect)
        await loop.start()

        msg = create_goal_message(sender="ceo", recipient="worker", goal_description="Test")
        await bus.publish(msg)

        import asyncio
        await asyncio.sleep(0.5)

        # Worker should send a CLARIFY about the missing tool
        assert len(clarify_messages) >= 1
        await loop.stop()

    async def test_max_iterations_limit(self, bus: MessageBus, registry: ToolRegistry) -> None:
        """LLM keeps calling tools — loop stops at max_tool_iterations (and sends CLARIFY)."""
        node = SwarmNode(node_id="worker", name="Worker", role=Role.WORKER)
        handle = NodeHandle(node=node)

        async def fake_llm(prompt: str, ctx: dict, **kwargs) -> LLMResponse:
            return LLMResponse(
                content="",
                tool_calls=[ToolCall(name="noop", arguments={})],
            )

        loop = AgentLoop(
            handle=handle, bus=bus,
            llm_func=fake_llm, tool_registry=registry,
            max_tool_iterations=3,
        )

        results: list[str] = []
        clarify_received = False

        async def collect(msg: object) -> None:
            nonlocal clarify_received
            if hasattr(msg, "type"):
                if msg.type == MessageType.CLARIFY:
                    clarify_received = True
                elif msg.type in (MessageType.RESULT, MessageType.ERROR):
                    results.append(msg.content)

        bus.subscribe("ceo", collect)
        await loop.start()

        msg = create_goal_message(sender="ceo", recipient="worker", goal_description="Loop test")
        await bus.publish(msg)

        import asyncio
        await asyncio.sleep(0.5)

        # Worker should send CLARIFY, not fail
        assert clarify_received, "Worker should send CLARIFY on max iterations"
        await loop.stop()

    async def test_worker_no_tools_still_works(self, bus: MessageBus) -> None:
        """AgentLoop without tools behaves like original _execute_goal."""
        node = SwarmNode(node_id="worker", name="Worker", role=Role.WORKER)
        handle = NodeHandle(node=node)

        async def fake_llm(prompt: str, ctx: dict, **kwargs) -> LLMResponse:
            return LLMResponse(content="Just a text response.", tool_calls=[])

        loop = AgentLoop(handle=handle, bus=bus, llm_func=fake_llm)

        results: list[str] = []

        async def collect(msg: object) -> None:
            if hasattr(msg, "type") and msg.type in (MessageType.RESULT, MessageType.ERROR):
                results.append(msg.content)

        bus.subscribe("ceo", collect)
        await loop.start()

        msg = create_goal_message(sender="ceo", recipient="worker", goal_description="Test no tools")
        await bus.publish(msg)

        import asyncio
        await asyncio.sleep(0.3)

        assert len(results) == 1
        assert results[0] == "Just a text response."
        await loop.stop()

    async def test_tool_in_prompt_when_registry_has_tools(self, bus: MessageBus, registry: ToolRegistry) -> None:
        """Tool descriptions appear in the LLM prompt."""
        node = SwarmNode(node_id="worker", name="Worker", role=Role.WORKER)
        handle = NodeHandle(node=node)

        prompts: list[str] = []

        async def fake_llm(prompt: str, ctx: dict, **kwargs) -> LLMResponse:
            prompts.append(prompt)
            return LLMResponse(content="final answer", tool_calls=[])

        loop = AgentLoop(handle=handle, bus=bus, llm_func=fake_llm, tool_registry=registry)
        await loop.start()

        msg = create_goal_message(sender="ceo", recipient="worker", goal_description="Show tools")
        await bus.publish(msg)

        import asyncio
        await asyncio.sleep(0.3)

        assert len(prompts) >= 1
        combined = " ".join(prompts)
        assert "calculate" in combined
        assert "noop" in combined
        await loop.stop()

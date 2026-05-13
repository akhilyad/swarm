"""Tests for tool-calling integration in the agent loop."""

from __future__ import annotations

import pytest

from src.communication.bus import MessageBus
from src.communication.message import create_goal_message
from src.core.node import NodeHandle
from src.core.types import GoalStatus, MessageType, Role, SwarmNode
from src.runtime.agent_loop import AgentLoop, _parse_tool_call
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


class TestParseToolCall:
    def test_parse_simple(self) -> None:
        result = _parse_tool_call('TOOL_CALL: read_file(file_path="test.txt")')
        assert result is not None
        name, args = result
        assert name == "read_file"
        assert args == {"file_path": "test.txt"}

    def test_parse_multiple_args(self) -> None:
        result = _parse_tool_call(
            'TOOL_CALL: write_file(file_path="out.txt", content="hello")'
        )
        assert result is not None
        name, args = result
        assert name == "write_file"
        assert args == {"file_path": "out.txt", "content": "hello"}

    def test_parse_with_integer_arg(self) -> None:
        result = _parse_tool_call('TOOL_CALL: calculate(expr="1+2")')
        assert result is not None
        name, args = result
        assert name == "calculate"
        assert args == {"expr": "1+2"}

    def test_no_tool_call_returns_none(self) -> None:
        assert _parse_tool_call("This is a final answer.") is None

    def test_tool_call_in_middle_of_text(self) -> None:
        text = (
            "I need to read a file first.\n"
            'TOOL_CALL: read_file(file_path="data.txt")\n'
            "Then I can process it."
        )
        result = _parse_tool_call(text)
        assert result is not None
        name, args = result
        assert name == "read_file"
        assert args == {"file_path": "data.txt"}

    def test_parse_with_float_arg(self) -> None:
        result = _parse_tool_call('TOOL_CALL: bash(command="sleep 0.5", timeout=10.0)')
        assert result is not None
        name, args = result
        assert name == "bash"

    def test_invalid_format_returns_none(self) -> None:
        assert _parse_tool_call("TOOL_CALL") is None
        assert _parse_tool_call("TOOL_CALL: ") is None
        assert _parse_tool_call("") is None


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
        """LLM returns a TOOL_CALL, tool executes, result is included in response."""
        node = SwarmNode(node_id="worker", name="Worker", role=Role.WORKER)
        handle = NodeHandle(node=node)

        call_count = 0

        async def fake_llm(prompt: str, ctx: dict) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return 'TOOL_CALL: calculate(expr="2+2")'
            return "The result is 4."

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
        """LLM calls a tool not in the registry."""
        node = SwarmNode(node_id="worker", name="Worker", role=Role.WORKER)
        handle = NodeHandle(node=node)
        registry = ToolRegistry()

        async def fake_llm(prompt: str, ctx: dict) -> str:
            return 'TOOL_CALL: nonexistent_tool(arg="val")'

        loop = AgentLoop(handle=handle, bus=bus, llm_func=fake_llm, tool_registry=registry)

        results: list[str] = []

        async def collect(msg: object) -> None:
            if hasattr(msg, "type") and msg.type in (MessageType.RESULT, MessageType.ERROR):
                results.append(msg.content)

        bus.subscribe("ceo", collect)
        await loop.start()

        msg = create_goal_message(sender="ceo", recipient="worker", goal_description="Test")
        await bus.publish(msg)

        import asyncio
        await asyncio.sleep(0.3)

        assert len(results) == 1
        assert "nonexistent_tool" in results[0]
        assert "not available" in results[0]
        await loop.stop()

    async def test_max_iterations_limit(self, bus: MessageBus, registry: ToolRegistry) -> None:
        """LLM keeps calling tools — loop stops at max_tool_iterations."""
        node = SwarmNode(node_id="worker", name="Worker", role=Role.WORKER)
        handle = NodeHandle(node=node)

        async def fake_llm(prompt: str, ctx: dict) -> str:
            return 'TOOL_CALL: noop()'

        loop = AgentLoop(
            handle=handle, bus=bus,
            llm_func=fake_llm, tool_registry=registry,
            max_tool_iterations=3,
        )

        results: list[str] = []

        async def collect(msg: object) -> None:
            if hasattr(msg, "type") and msg.type in (MessageType.RESULT, MessageType.ERROR):
                results.append(msg.content)

        bus.subscribe("ceo", collect)
        await loop.start()

        msg = create_goal_message(sender="ceo", recipient="worker", goal_description="Loop test")
        await bus.publish(msg)

        import asyncio
        await asyncio.sleep(0.5)

        assert len(results) == 1
        assert "max tool iterations" in results[0]
        await loop.stop()

    async def test_worker_no_tools_still_works(self, bus: MessageBus) -> None:
        """AgentLoop without tools behaves like original _execute_goal."""
        node = SwarmNode(node_id="worker", name="Worker", role=Role.WORKER)
        handle = NodeHandle(node=node)

        async def fake_llm(prompt: str, ctx: dict) -> str:
            return "Just a text response."

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

        async def fake_llm(prompt: str, ctx: dict) -> str:
            prompts.append(prompt)
            return "final answer"

        loop = AgentLoop(handle=handle, bus=bus, llm_func=fake_llm, tool_registry=registry)
        await loop.start()

        msg = create_goal_message(sender="ceo", recipient="worker", goal_description="Show tools")
        await bus.publish(msg)

        import asyncio
        await asyncio.sleep(0.3)

        assert len(prompts) >= 1
        combined = " ".join(prompts)
        assert "TOOL_CALL" in combined
        assert "calculate" in combined
        assert "noop" in combined
        await loop.stop()

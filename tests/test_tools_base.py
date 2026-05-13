"""Tests for the tool plugin base classes."""

from __future__ import annotations

import pytest

from src.tools.base import BaseTool, ToolRegistry, ToolResult


class TestToolResult:
    def test_frozen_dataclass(self) -> None:
        r = ToolResult(success=True, output="hello")
        assert r.success is True
        assert r.output == "hello"
        assert r.error == ""
        assert r.execution_time == 0.0

    def test_error_result(self) -> None:
        r = ToolResult(success=False, error="something broke")
        assert r.success is False
        assert r.error == "something broke"


class _EchoTool(BaseTool):
    name = "echo"
    description = "Echoes the input back"
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to echo"},
        },
        "required": ["text"],
    }

    async def execute(self, **kwargs: str) -> ToolResult:
        text = kwargs.get("text", "")
        return ToolResult(success=True, output=text)


class _FailTool(BaseTool):
    name = "fail"
    description = "Always fails"
    parameters = {"type": "object", "properties": {}, "required": []}

    async def execute(self, **kwargs: str) -> ToolResult:
        return ToolResult(success=False, error="intentional failure")


class TestBaseTool:
    async def test_execute_returns_tool_result(self) -> None:
        tool = _EchoTool()
        result = await tool.execute(text="hello")
        assert result.success is True
        assert result.output == "hello"

    async def test_to_llm_description_includes_name_and_description(self) -> None:
        tool = _EchoTool()
        desc = tool.to_llm_description()
        assert "## echo" in desc
        assert "Echoes the input back" in desc
        assert "text" in desc
        assert "(required)" in desc


class TestToolRegistry:
    def test_register_and_get(self) -> None:
        registry = ToolRegistry()
        tool = _EchoTool()
        registry.register(tool)
        assert registry.get_tool("echo") is tool
        assert registry.tool_count == 1

    def test_register_duplicate_raises(self) -> None:
        registry = ToolRegistry()
        registry.register(_EchoTool())
        with pytest.raises(ValueError, match="already registered"):
            registry.register(_EchoTool())

    def test_unregister(self) -> None:
        registry = ToolRegistry()
        registry.register(_EchoTool())
        registry.unregister("echo")
        assert registry.get_tool("echo") is None
        assert registry.tool_count == 0

    def test_unregister_nonexistent_is_noop(self) -> None:
        registry = ToolRegistry()
        registry.unregister("nonexistent")  # should not raise
        assert registry.tool_count == 0

    def test_get_all_tools(self) -> None:
        registry = ToolRegistry()
        echo = _EchoTool()
        fail = _FailTool()
        registry.register(echo)
        registry.register(fail)
        tools = registry.get_all_tools()
        assert len(tools) == 2
        assert echo in tools
        assert fail in tools

    def test_list_capabilities_no_tools(self) -> None:
        registry = ToolRegistry()
        cap = registry.list_capabilities()
        assert "No tools available" in cap

    def test_list_capabilities_includes_tool_info(self) -> None:
        registry = ToolRegistry()
        registry.register(_EchoTool())
        cap = registry.list_capabilities()
        assert "echo" in cap
        assert "Echoes" in cap
        assert "text" in cap

    def test_tool_count(self) -> None:
        registry = ToolRegistry()
        assert registry.tool_count == 0
        registry.register(_EchoTool())
        assert registry.tool_count == 1

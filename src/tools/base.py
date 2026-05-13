"""Base abstractions for the tool plugin system.

Defines the contract all tools must follow plus a registry for
discovery and capability listing.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolResult:
    """Immutable result of a single tool execution."""

    success: bool
    output: str = ""
    error: str = ""
    execution_time: float = 0.0


class BaseTool(ABC):
    """Abstract base for every tool an agent can call.

    Subclasses must set *name*, *description* and *parameters* as
    instance attributes and implement :meth:`execute`.
    """

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Run the tool with the given keyword arguments."""

    def to_llm_description(self) -> str:
        """Format this tool's schema for LLM consumption.

        Returns a prompt-friendly block the LLM can use to decide
        which tool to call and how to fill its arguments.
        """
        lines = [f"## {self.name}", f"Description: {self.description}", ""]

        if self.parameters:
            lines.append("Parameters:")
            for name, schema in self.parameters.get("properties", {}).items():
                required = name in self.parameters.get("required", [])
                tag = " (required)" if required else ""
                ptype = schema.get("type", "string")
                desc = schema.get("description", "")
                lines.append(f"  - {name}: {ptype}{tag}")
                if desc:
                    lines.append(f"      {desc}")

        return "\n".join(lines)

    def to_openai_tool(self) -> dict:
        """Return this tool as an OpenAI-compatible function tool definition."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """Registry of available tools.

    Tools are registered by name (unique) and can be listed or looked
    up by the runtime when constructing LLM prompts.
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance.

        Raises ``ValueError`` if a tool with the same name is already
        registered.
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """Remove a previously registered tool by name."""
        self._tools.pop(name, None)

    def get_tool(self, name: str) -> BaseTool | None:
        """Look up a tool by name."""
        return self._tools.get(name)

    def get_all_tools(self) -> list[BaseTool]:
        """Return all registered tools."""
        return list(self._tools.values())

    def list_capabilities(self) -> str:
        """Return a formatted string of all registered tool capabilities."""
        if not self._tools:
            return "No tools available."

        parts = ["Available tools:\n"]
        for tool in self._tools.values():
            parts.append(tool.to_llm_description())
            parts.append("")
        return "\n".join(parts)

    def get_openai_tools(self) -> list[dict]:
        """Return all tools as OpenAI-compatible tool definitions."""
        return [tool.to_openai_tool() for tool in self._tools.values()]

    @property
    def tool_count(self) -> int:
        return len(self._tools)

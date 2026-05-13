from __future__ import annotations

from .base import BaseTool, ToolRegistry, ToolResult
from .builtin import BashTool, PythonExecTool, ReadFileTool, WebFetchTool, WriteFileTool


def register_all_tools(
    registry: ToolRegistry,
    allowed_root: str | None = None,
    bash_timeout: float = 30.0,
    fetch_timeout: float = 15.0,
    python_timeout: float = 15.0,
) -> ToolRegistry:
    """Register all built-in tools into *registry* and return it."""
    registry.register(ReadFileTool(allowed_root=allowed_root))
    registry.register(WriteFileTool(allowed_root=allowed_root))
    registry.register(BashTool(timeout=bash_timeout))
    registry.register(WebFetchTool(timeout=fetch_timeout))
    registry.register(PythonExecTool(timeout=python_timeout))
    return registry


__all__ = [
    "BaseTool",
    "ToolRegistry",
    "ToolResult",
    "register_all_tools",
    "BashTool",
    "PythonExecTool",
    "ReadFileTool",
    "WebFetchTool",
    "WriteFileTool",
]


"""MCP stdio client for tool execution.

Spawns the local MCP server as a subprocess and communicates via
the MCP protocol over its stdin/stdout. Falls back to direct
subprocess execution if the server cannot be started.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sys
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

logger = logging.getLogger(__name__)

_MCP_SESSION: ClientSession | None = None
_MCP_EXIT_STACK: contextlib.AsyncExitStack | None = None
_MCP_STARTUP_LOCK = asyncio.Lock()


class McpClientError(Exception):
    """Raised when MCP communication fails."""


async def _ensure_session() -> ClientSession:
    """Start the MCP server and return an initialized client session (singleton)."""
    global _MCP_SESSION, _MCP_EXIT_STACK

    if _MCP_SESSION is not None:
        return _MCP_SESSION

    async with _MCP_STARTUP_LOCK:
        if _MCP_SESSION is not None:
            return _MCP_SESSION

        logger.info("Starting MCP server subprocess")

        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "src.tools.mcp_server"],
        )

        _MCP_EXIT_STACK = contextlib.AsyncExitStack()
        try:
            transports = await _MCP_EXIT_STACK.enter_async_context(
                stdio_client(server_params)
            )
            read_stream, write_stream = transports
            session = await _MCP_EXIT_STACK.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await session.initialize()
            _MCP_SESSION = session
            logger.info("MCP server session initialized")
        except Exception:
            await _MCP_EXIT_STACK.aclose()
            _MCP_EXIT_STACK = None
            raise

        return _MCP_SESSION


async def _call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Call a tool via the MCP session."""
    session = await _ensure_session()
    try:
        result = await session.call_tool(name, arguments)
        content = result.content if hasattr(result, "content") else []
        text = " ".join(
            item.text for item in content if hasattr(item, "text") and item.text
        )
        is_error = getattr(result, "isError", False) or text.startswith("Error: ")
        return {
            "success": not is_error,
            "output": text[7:] if is_error and text.startswith("Error: ") else text,
            "error": text[7:] if is_error and text.startswith("Error: ") else (text if is_error else ""),
        }
    except Exception as e:
        raise McpClientError(str(e))


async def call_bash(command: str, timeout: float = 30.0) -> dict[str, Any]:
    """Call the bash tool via MCP.

    Returns a dict with ``success``, ``output``, ``error`` keys.
    """
    try:
        return await _call_tool("bash", {"command": command, "timeout": timeout})
    except McpClientError as e:
        return {"success": False, "output": "", "error": str(e)}


async def call_python(code: str, timeout: float = 15.0) -> dict[str, Any]:
    """Call the python_exec tool via MCP.

    Returns a dict with ``success``, ``output``, ``error`` keys.
    """
    try:
        return await _call_tool("python_exec", {"code": code, "timeout": timeout})
    except McpClientError as e:
        return {"success": False, "output": "", "error": str(e)}


async def shutdown() -> None:
    """Terminate the MCP server subprocess."""
    global _MCP_SESSION, _MCP_EXIT_STACK
    if _MCP_EXIT_STACK is not None:
        try:
            await _MCP_EXIT_STACK.aclose()
        except Exception:
            pass
        _MCP_SESSION = None
        _MCP_EXIT_STACK = None

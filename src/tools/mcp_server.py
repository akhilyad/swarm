"""MCP server that exposes bash and python execution as tools.

Replaces Docker-based tool execution with a persistent local MCP server.
The server runs as a subprocess, eliminating container boot overhead.

Usage:
    python -m src.tools.mcp_server [--port 8100]
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import mcp.server
import mcp.server.stdio
import mcp.types as types


def _exec_bash(command: str, timeout: float) -> dict[str, Any]:
    """Run a shell command and return result."""
    with tempfile.TemporaryDirectory(prefix="hyrex-bash-") as tmpdir:
        try:
            result = subprocess.run(
                ["sh", "-c", command],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmpdir,
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": f"Exit code {result.returncode}\n{result.stderr}" if result.returncode != 0 else "",
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "", "error": f"Command timed out after {timeout}s"}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}


def _exec_python(code: str, timeout: float) -> dict[str, Any]:
    """Run a Python snippet and return result."""
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "error": f"Exit code {result.returncode}\n{result.stderr}" if result.returncode != 0 else "",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "output": "", "error": f"Execution timed out after {timeout}s"}
    except Exception as e:
        return {"success": False, "output": "", "error": str(e)}


async def serve() -> None:
    """Run the MCP server over stdin/stdout transport."""
    server = mcp.server.Server("hyrex-tools")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        return [
            types.Tool(
                name="bash",
                description="Execute a shell command and return its output.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "The shell command to execute."},
                        "timeout": {"type": "number", "description": "Maximum execution time in seconds (default 30)."},
                    },
                    "required": ["command"],
                },
            ),
            types.Tool(
                name="python_exec",
                description="Execute Python code and return its stdout/stderr.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "The Python code to execute."},
                        "timeout": {"type": "number", "description": "Maximum execution time in seconds (default 15)."},
                    },
                    "required": ["code"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(
        name: str,
        arguments: dict[str, Any] | None,
    ) -> list[types.TextContent]:
        if arguments is None:
            raise ValueError("No arguments provided")

        if name == "bash":
            command = arguments.get("command", "")
            if not command:
                return [types.TextContent(type="text", text="Error: command is required")]
            timeout = float(arguments.get("timeout", 30))
            result = await asyncio.to_thread(_exec_bash, command, timeout)
        elif name == "python_exec":
            code = arguments.get("code", "")
            if not code:
                return [types.TextContent(type="text", text="Error: code is required")]
            timeout = float(arguments.get("timeout", 15))
            result = await asyncio.to_thread(_exec_python, code, timeout)
        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

        if result["success"]:
            return [types.TextContent(type="text", text=result["output"])]
        else:
            msg = result.get("error", "Unknown error")
            if result.get("output"):
                msg = f"{result['output']}\n{msg}"
            return [types.TextContent(type="text", text=f"Error: {msg}")]

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    """Entry point for ``python -m src.tools.mcp_server``."""
    asyncio.run(serve())


if __name__ == "__main__":
    main()

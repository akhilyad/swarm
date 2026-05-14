"""Tool that executes Python code via local subprocess.

Replaces the Docker-based execution with a direct subprocess call.
The MCP server (``src.tools.mcp_server``) wraps this same logic as a
long-running service for distributed setups.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import time

from ..base import BaseTool, ToolResult


class PythonExecTool(BaseTool):
    """Execute a Python snippet locally and return its stdout/stderr.

    Security: code runs in an isolated subprocess with no special
    permissions. Use the MCP server for remote/containerized execution.
    """

    name = "python_exec"
    description = "Execute Python code and return its stdout/stderr."
    parameters = {
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "The Python code to execute.",
            },
            "timeout": {
                "type": "number",
                "description": "Maximum execution time in seconds (default 15).",
            },
        },
        "required": ["code"],
    }

    def __init__(self, timeout: float = 15.0) -> None:
        self._default_timeout = timeout

    async def execute(self, **kwargs: str | float) -> ToolResult:
        code = kwargs.get("code", "")
        if not code:
            return ToolResult(success=False, error="code is required")

        cmd_timeout = float(kwargs.get("timeout", self._default_timeout))
        start = time.monotonic()

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    subprocess.run,
                    [sys.executable, "-c", code],
                    capture_output=True,
                    text=True,
                ),
                timeout=cmd_timeout,
            )

            elapsed = time.monotonic() - start
            if result.returncode == 0:
                return ToolResult(success=True, output=result.stdout, execution_time=elapsed)
            else:
                msg = f"Exit code {result.returncode}"
                if result.stderr:
                    msg += f"\n{result.stderr}"
                return ToolResult(
                    success=False,
                    output=result.stdout,
                    error=msg,
                    execution_time=elapsed,
                )

        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                error=f"Execution timed out after {cmd_timeout}s",
                execution_time=time.monotonic() - start,
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=str(exc),
                execution_time=time.monotonic() - start,
            )

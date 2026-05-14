"""Tool that executes a shell command via local subprocess.

Replaces the Docker-based execution with a direct subprocess call.
The MCP server (``src.tools.mcp_server``) wraps this same logic as a
long-running service for distributed setups.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import time
import tempfile

from ..base import BaseTool, ToolResult


class BashTool(BaseTool):
    """Execute a shell command locally and return its output.

    Security: commands run in an isolated temp directory with no special
    permissions. Use the MCP server for remote/containerized execution.
    """

    name = "bash"
    description = "Execute a shell command and return its output."
    parameters = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute.",
            },
            "timeout": {
                "type": "number",
                "description": "Maximum execution time in seconds (default 30).",
            },
        },
        "required": ["command"],
    }

    def __init__(self, timeout: float = 30.0) -> None:
        self._default_timeout = timeout

    async def execute(self, **kwargs: str | float) -> ToolResult:
        command = kwargs.get("command", "")
        if not command:
            return ToolResult(success=False, error="command is required")

        cmd_timeout = float(kwargs.get("timeout", self._default_timeout))
        start = time.monotonic()

        try:
            with tempfile.TemporaryDirectory(prefix="hyrex-bash-") as tmpdir:
                result = await asyncio.wait_for(
                    asyncio.to_thread(
                        subprocess.run,
                        ["sh", "-c", command],
                        capture_output=True,
                        text=True,
                        cwd=tmpdir,
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
                error=f"Command timed out after {cmd_timeout}s",
                execution_time=time.monotonic() - start,
            )
        except FileNotFoundError:
            return ToolResult(
                success=False,
                error="sh not found — this tool requires a POSIX shell",
                execution_time=time.monotonic() - start,
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=str(exc),
                execution_time=time.monotonic() - start,
            )

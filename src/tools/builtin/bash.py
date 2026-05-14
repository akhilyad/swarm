"""Tool that executes a shell command via local subprocess.

No Docker dependency — runs directly on the host. For distributed
setups, use the MCP client (``src.tools.mcp_client``) instead.
"""

from __future__ import annotations

import asyncio
import subprocess
import tempfile
import time

from ..base import BaseTool, ToolResult


class BashTool(BaseTool):
    """Execute a shell command and return its output.

    Commands run in an isolated temp directory. No container overhead.
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
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["sh", "-c", "--", command],
                    capture_output=True,
                    text=True,
                    cwd=tmpdir,
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

        except subprocess.TimeoutExpired:
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

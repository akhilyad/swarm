"""Tool that executes a shell command."""

from __future__ import annotations

import asyncio
import time

from ..base import BaseTool, ToolResult


class BashTool(BaseTool):
    """Execute a shell command with a configurable timeout.

    WARNING: This tool provides arbitrary shell access. Use with
    caution in untrusted environments.
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
            proc = await asyncio.create_subprocess_shell(
                str(command),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=cmd_timeout
            )
            elapsed = time.monotonic() - start
            out = stdout.decode(errors="replace") if stdout else ""
            err = stderr.decode(errors="replace") if stderr else ""

            if proc.returncode == 0:
                return ToolResult(success=True, output=out, execution_time=elapsed)
            else:
                msg = f"Exit code {proc.returncode}"
                if err:
                    msg += f"\n{err}"
                return ToolResult(success=False, output=out, error=msg, execution_time=elapsed)

        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                error=f"Command timed out after {cmd_timeout}s",
                execution_time=time.monotonic() - start,
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=str(exc),
                execution_time=time.monotonic() - start,
            )

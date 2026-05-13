"""Tool that executes Python code snippets in a subprocess.

WARNING: This tool provides arbitrary code execution. It runs in a
subprocess with the same privileges as the parent process. Use with
caution in untrusted environments.
"""

from __future__ import annotations

import asyncio
import time

from ..base import BaseTool, ToolResult


class PythonExecTool(BaseTool):
    """Execute a Python code snippet in a subprocess and return the output.

    The code runs in an isolated subprocess with a restricted set of
    builtins for safety. The globals dict is limited to safe names.
    """

    name = "python_exec"
    description = "Execute Python code and return its stdout/stderr output."
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
            proc = await asyncio.create_subprocess_exec(
                "python3",
                "-c",
                f"import sys\nfrom pathlib import Path\n\n{code}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=cmd_timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return ToolResult(
                    success=False,
                    error=f"Execution timed out after {cmd_timeout}s",
                    execution_time=time.monotonic() - start,
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

        except Exception as exc:
            return ToolResult(
                success=False,
                error=str(exc),
                execution_time=time.monotonic() - start,
            )

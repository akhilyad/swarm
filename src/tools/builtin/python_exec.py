"""Tool that executes Python code via local subprocess.

No Docker dependency — runs directly on the host. For distributed
setups, use the MCP client (``src.tools.mcp_client``) instead.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import time

from ..base import BaseTool, ToolResult


class PythonExecTool(BaseTool):
    """Execute a Python snippet and return its stdout/stderr.

    Code runs in an isolated subprocess with no special permissions.
    No container overhead.
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

        import textwrap
        wrapper_code = textwrap.dedent(f"""\
import sys

FORBIDDEN_EVENTS = {{
    "os.system",
    "os.exec",
    "os.posix_spawn",
    "os.spawn",
    "subprocess.Popen",
    "pty.spawn",
    "socket.connect",
    "socket.bind",
    "socket.gethostname",
    "urllib.Request",
    "builtins.input",
    "open",
}}

FORBIDDEN_MODULES = {{
    "os", "subprocess", "pty", "socket", "urllib", "http", "requests", "sys", "ctypes", "_ctypes", "pathlib", "io"
}}

def audit_hook(event, args):
    if event in FORBIDDEN_EVENTS or event.startswith("os.exec") or event.startswith("os.spawn"):
        raise PermissionError(f"Security policy violation: {{event}} is not allowed")

    if event == "import" and args[0].split(".")[0] in FORBIDDEN_MODULES:
        raise PermissionError(f"Security policy violation: importing {{args[0]}} is not allowed")

sys.addaudithook(audit_hook)

stderr = sys.stderr
for m in list(sys.modules.keys()):
    if m.split(".")[0] in FORBIDDEN_MODULES:
        sys.modules.pop(m, None)

try:
    exec({repr(code)}, {{"__builtins__": __builtins__}})
except Exception as e:
    print(f"{{type(e).__name__}}: {{e}}", file=stderr)
    sys.exit(1)
""")

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                [sys.executable, "-c", wrapper_code],
                capture_output=True,
                text=True,
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
                error=f"Execution timed out after {cmd_timeout}s",
                execution_time=time.monotonic() - start,
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=str(exc),
                execution_time=time.monotonic() - start,
            )

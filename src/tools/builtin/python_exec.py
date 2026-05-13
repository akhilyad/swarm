"""Tool that executes Python code inside an isolated Docker container.

Every invocation spins up an ephemeral container running the code snippet.
No host access, no network, destroyed immediately after execution.
"""

from __future__ import annotations

import time
import uuid

import docker
from docker.errors import DockerException, ImageNotFound

from ..base import BaseTool, ToolResult


_IMAGE = "python:3.11-alpine"
_CONTAINER_MEMORY_LIMIT = "256m"
_CONTAINER_CPU_LIMIT = 0.5


class PythonExecTool(BaseTool):
    """Execute a Python snippet inside an ephemeral Docker container.

    Each call creates a fresh Python container, runs the code, captures
    output, and destroys the container. No network, no host mounts.
    """

    name = "python_exec"
    description = "Execute Python code in an isolated Docker container and return its stdout/stderr."
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
        self._client = docker.from_env()

    async def execute(self, **kwargs: str | float) -> ToolResult:
        code = kwargs.get("code", "")
        if not code:
            return ToolResult(success=False, error="code is required")

        cmd_timeout = float(kwargs.get("timeout", self._default_timeout))
        start = time.monotonic()

        try:
            try:
                self._client.images.get(_IMAGE)
            except ImageNotFound:
                self._client.images.pull(_IMAGE)

            container_name = f"hyrex-py-{uuid.uuid4().hex[:12]}"

            container = self._client.containers.create(
                _IMAGE,
                ["python3", "-c", f"import sys\nfrom pathlib import Path\n\n{code}"],
                name=container_name,
                mem_limit=_CONTAINER_MEMORY_LIMIT,
                cpu_quota=int(_CONTAINER_CPU_LIMIT * 100000),
                network_disabled=True,
                auto_remove=False,
                read_only=True,
            )

            container.start()

            exit_code = container.wait(timeout=cmd_timeout).get("StatusCode", -1)

            stdout_raw = container.logs(stdout=True, stderr=False).decode(errors="replace")
            stderr_raw = container.logs(stdout=False, stderr=True).decode(errors="replace")

            container.remove(force=True)

            elapsed = time.monotonic() - start

            if exit_code == 0:
                return ToolResult(success=True, output=stdout_raw, execution_time=elapsed)
            else:
                msg = f"Exit code {exit_code}"
                if stderr_raw:
                    msg += f"\n{stderr_raw}"
                return ToolResult(success=False, output=stdout_raw, error=msg, execution_time=elapsed)

        except docker.errors.TimeoutError:
            try:
                container.remove(force=True)
            except Exception:
                pass
            return ToolResult(
                success=False,
                error=f"Execution timed out after {cmd_timeout}s",
                execution_time=time.monotonic() - start,
            )
        except DockerException as exc:
            return ToolResult(
                success=False,
                error=f"Docker execution failed: {exc}",
                execution_time=time.monotonic() - start,
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=str(exc),
                execution_time=time.monotonic() - start,
            )

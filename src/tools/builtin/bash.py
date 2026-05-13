"""Tool that executes a shell command inside an isolated Docker container.

Every command gets its own ephemeral container — no host filesystem
access, no network, destroyed immediately after execution.
"""

from __future__ import annotations

import time
import uuid

import docker
from docker.errors import DockerException, ImageNotFound

from ..base import BaseTool, ToolResult


# Lightweight base image with common shell utilities
_IMAGE = "alpine:latest"
_CONTAINER_MEMORY_LIMIT = "256m"
_CONTAINER_CPU_LIMIT = 0.5


class BashTool(BaseTool):
    """Execute a shell command inside an ephemeral Docker container.

    Each invocation creates a fresh container, runs the command inside it,
    captures stdout/stderr, and destroys the container. The container has
    no network access and no host-mounted volumes.
    """

    name = "bash"
    description = "Execute a shell command in an isolated Docker container and return its output."
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
        self._client = docker.from_env()

    async def execute(self, **kwargs: str | float) -> ToolResult:
        command = kwargs.get("command", "")
        if not command:
            return ToolResult(success=False, error="command is required")

        cmd_timeout = float(kwargs.get("timeout", self._default_timeout))
        start = time.monotonic()

        try:
            # Ensure the image is available
            try:
                self._client.images.get(_IMAGE)
            except ImageNotFound:
                self._client.images.pull(_IMAGE)

            container_name = f"hyrex-bash-{uuid.uuid4().hex[:12]}"

            container = self._client.containers.create(
                _IMAGE,
                ["sh", "-c", str(command)],
                name=container_name,
                mem_limit=_CONTAINER_MEMORY_LIMIT,
                cpu_quota=int(_CONTAINER_CPU_LIMIT * 100000),
                network_disabled=True,          # Block all network access
                auto_remove=False,
                read_only=True,                  # Read-only filesystem
            )

            container.start()

            # Wait with timeout
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

        except docker.errors.DockerException as exc:
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

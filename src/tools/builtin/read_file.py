"""Tool that reads a file from the local filesystem."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from ..base import BaseTool, ToolResult


class ReadFileTool(BaseTool):
    """Read the contents of a file at the given path.

    Security: the path is resolved and checked to stay within the
    project root, preventing simple path-traversal attacks.
    """

    name = "read_file"
    description = "Read the contents of a file from the filesystem."
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute or project-relative path to the file.",
            },
        },
        "required": ["file_path"],
    }

    def __init__(self, allowed_root: str | None = None) -> None:
        self._allowed_root = Path(allowed_root).resolve() if allowed_root else None

    async def execute(self, **kwargs: str) -> ToolResult:
        raw = kwargs.get("file_path", "")
        if not raw:
            return ToolResult(success=False, error="file_path is required")

        start = time.monotonic()

        try:
            path = self._resolve(raw)
            if not await asyncio.to_thread(path.exists):
                return ToolResult(
                    success=False,
                    error=f"File not found: {path}",
                    execution_time=time.monotonic() - start,
                )
            content = await asyncio.to_thread(path.read_text, encoding="utf-8")
            return ToolResult(
                success=True,
                output=content,
                execution_time=time.monotonic() - start,
            )
        except PermissionError:
            return ToolResult(
                success=False,
                error=f"Permission denied: {raw}",
                execution_time=time.monotonic() - start,
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=str(exc),
                execution_time=time.monotonic() - start,
            )

    def _resolve(self, raw: str) -> Path:
        p = Path(raw)
        if not p.is_absolute():
            p = Path.cwd() / p
        p = p.resolve()
        if self._allowed_root is not None:
            try:
                p.relative_to(self._allowed_root)
            except ValueError:
                raise PermissionError(
                    f"Path '{raw}' resolves outside the allowed root "
                    f"'{self._allowed_root}'"
                )
        return p

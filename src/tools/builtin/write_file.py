"""Tool that writes content to a file on the local filesystem."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from ..base import BaseTool, ToolResult


class WriteFileTool(BaseTool):
    """Write content to a file.

    Will create parent directories if they do not exist.
    Security: path is resolved and checked against an allowed root.
    """

    name = "write_file"
    description = "Write content to a file. Creates parent directories if needed."
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path where the file should be written.",
            },
            "content": {
                "type": "string",
                "description": "The content to write.",
            },
        },
        "required": ["file_path", "content"],
    }

    def __init__(self, allowed_root: str | None = None) -> None:
        self._allowed_root = Path(allowed_root).resolve() if allowed_root else None

    async def execute(self, **kwargs: str) -> ToolResult:
        raw = kwargs.get("file_path", "")
        content = kwargs.get("content", "")
        if not raw:
            return ToolResult(success=False, error="file_path is required")

        start = time.monotonic()

        try:
            path = self._resolve(raw)

            def _write():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            await asyncio.to_thread(_write)
            return ToolResult(
                success=True,
                output=f"Wrote {len(content)} bytes to {path}",
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

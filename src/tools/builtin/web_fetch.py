"""Tool that fetches content from a URL."""

from __future__ import annotations

import asyncio
import time

from ..base import BaseTool, ToolResult


class WebFetchTool(BaseTool):
    """Fetch content from a URL.

    Uses asyncio-based HTTP calls. Only supports HTTPS URLs by
    default for security.
    """

    name = "web_fetch"
    description = "Fetch content from a URL and return the response text."
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to fetch (must be http or https).",
            },
            "timeout": {
                "type": "number",
                "description": "Request timeout in seconds (default 15).",
            },
        },
        "required": ["url"],
    }

    def __init__(self, timeout: float = 15.0) -> None:
        self._default_timeout = timeout

    async def execute(self, **kwargs: str | float) -> ToolResult:
        url = kwargs.get("url", "")
        if not url:
            return ToolResult(success=False, error="url is required")

        if not url.startswith(("http://", "https://")):
            return ToolResult(
                success=False,
                error="Only http/https URLs are supported",
            )

        request_timeout = float(kwargs.get("timeout", self._default_timeout))
        start = time.monotonic()

        try:
            import urllib.request

            req = urllib.request.Request(
                url,
                headers={"User-Agent": "SwarmOfSwarms/0.1"},
            )

            loop = asyncio.get_running_loop()

            def _fetch() -> tuple[int, str]:
                with urllib.request.urlopen(req, timeout=int(request_timeout)) as resp:
                    return resp.status, resp.read().decode(errors="replace")

            status, body = await asyncio.wait_for(
                loop.run_in_executor(None, _fetch), timeout=request_timeout + 5
            )

            elapsed = time.monotonic() - start
            if 200 <= status < 300:
                return ToolResult(success=True, output=body, execution_time=elapsed)
            else:
                return ToolResult(
                    success=False,
                    error=f"HTTP {status}",
                    output=body,
                    execution_time=elapsed,
                )

        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                error=f"Request timed out after {request_timeout}s",
                execution_time=time.monotonic() - start,
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=str(exc),
                execution_time=time.monotonic() - start,
            )

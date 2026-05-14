"""LiteLLM wrapper with rate limiting, automatic retries, and cost tracking."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections import namedtuple
from typing import Any

import tenacity
from tenacity import retry, stop_after_attempt, wait_exponential

from ..core.errors import LLMError

# Structured response when the LLM calls a tool via native function-calling.
ToolCall = namedtuple("ToolCall", ["name", "arguments"])
LLMResponse = namedtuple("LLMResponse", ["content", "tool_calls"])

logger = logging.getLogger(__name__)

# Cap concurrent API requests to avoid provider rate limits
_DEFAULT_MAX_CONCURRENT = 5


class LLMClient:
    """Async LLM client wrapping LiteLLM with rate limiting and retries.

    Features:
    - Multi-provider support via LiteLLM (OpenAI, Anthropic, Google, local)
    - Per-request model override (agent-specific models)
    - ``asyncio.Semaphore`` to cap concurrent API requests
    - Exponential-backoff retries via ``tenacity`` for 429/503 errors
    - Cost tracking and budget enforcement
    """

    def __init__(
        self,
        default_model: str | None = None,
        budget_usd: float | None = None,
        max_concurrent: int = _DEFAULT_MAX_CONCURRENT,
    ) -> None:
        self.default_model = default_model or os.environ.get(
            "SWARM_DEFAULT_MODEL", "gpt-4o"
        )
        self.budget_usd = budget_usd
        self.total_cost = 0.0
        self.request_count = 0
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def generate(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Generate a response from the LLM with rate limiting and retries.

        Args:
            prompt: The prompt to send.
            context: Optional context (role, children, etc.) for system prompt.
            model: Override the default model for this request.
            max_tokens: Maximum tokens in the response.
            temperature: Sampling temperature.
            tools: Optional list of OpenAI-compatible tool definitions. When
                   provided the LLM may return structured tool calls instead
                   of plain text.

        Returns:
            An ``LLMResponse(content, tool_calls)``. If the LLM chose to
            call a tool, ``tool_calls`` is a list of ``ToolCall`` namedtuples
            and ``content`` is the optional text part. Otherwise ``tool_calls``
            is empty.
        """
        actual_model = model or self.default_model
        system_prompt = self._build_system_prompt(context or {})

        async with self._semaphore:
            self.request_count += 1
            response = await self._request_with_retry(
                actual_model, system_prompt, prompt, max_tokens, temperature, tools
            )
            self._check_budget()
            return response

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
        retry=tenacity.retry_if_exception_type(
            (LLMError, ConnectionError, TimeoutError)
        ),
        before_sleep=lambda retry_state: logger.info(
            "LLM request failed (attempt %d), retrying in %.1fs ...",
            retry_state.attempt_number,
            retry_state.next_action.sleep if retry_state.next_action else 0,
        ),
    )
    async def _request_with_retry(
        self,
        model: str,
        system_prompt: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Make the actual LiteLLM call, wrapped with tenacity retry logic."""
        try:
            import litellm

            kwargs = dict(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            if tools:
                kwargs["tools"] = tools

            response = await litellm.acompletion(**kwargs)

            choice = response.choices[0]
            message = choice.message
            content = message.content or ""

            tool_calls: list[ToolCall] = []
            if message.tool_calls:
                for tc in message.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}
                    tool_calls.append(ToolCall(name=tc.function.name, arguments=args))

            if hasattr(response, "usage") and hasattr(response.usage, "cost"):
                self.total_cost += response.usage.cost or 0.0

            return LLMResponse(content=content, tool_calls=tool_calls)

        except ImportError:
            raise LLMError("LiteLLM is not installed. Run: pip install litellm")
        except Exception as e:
            error_str = str(e).lower()
            if "rate" in error_str or "429" in error_str or "503" in error_str or "too many" in error_str:
                logger.warning("Rate-limited by provider: %s", e)
            raise LLMError(f"LLM generation failed: {e}")

    def _build_system_prompt(self, context: dict[str, Any]) -> str:
        """Build a system prompt from context."""
        role = context.get("role", "agent")
        children = context.get("children", [])

        parts = [f"You are an AI agent with role: {role}."]

        if children:
            parts.append(
                f"You have team members: {', '.join(children)}. "
                "You can delegate tasks to them."
            )

        if role == "CEO":
            parts.append(
                "You are the CEO. Break down strategic goals into actionable "
                "sub-goals for your managers. Synthesize their results."
            )
        elif role == "MANAGER":
            parts.append(
                "You are a department manager. Decompose assigned goals into "
                "concrete tasks for your workers. Collect and summarize results."
            )
        elif role == "WORKER":
            parts.append(
                "You are a worker agent. Execute assigned tasks directly "
                "and report the results clearly."
            )

        parts.append("Be concise and direct. Always complete the assigned goal.")
        return "\n".join(parts)

    def _check_budget(self) -> None:
        """Check if we've exceeded the budget."""
        if self.budget_usd is not None and self.total_cost > self.budget_usd:
            logger.warning(
                "Budget exceeded: $%.2f / $%.2f",
                self.total_cost,
                self.budget_usd,
            )

    @property
    def cost_summary(self) -> str:
        return f"Requests: {self.request_count}, Total cost: ${self.total_cost:.4f}"

    def reset_costs(self) -> None:
        self.total_cost = 0.0
        self.request_count = 0

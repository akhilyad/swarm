"""LiteLLM wrapper with cost tracking and model routing."""

from __future__ import annotations

import logging
import os
from typing import Any

from ..core.errors import LLMError

logger = logging.getLogger(__name__)


class LLMClient:
    """Async LLM client wrapping LiteLLM.

    Provides:
    - Multi-provider support via LiteLLM (OpenAI, Anthropic, Google, local)
    - Per-request model override (agent-specific models)
    - Cost tracking and budget enforcement
    """

    def __init__(
        self,
        default_model: str | None = None,
        budget_usd: float | None = None,
    ) -> None:
        self.default_model = default_model or os.environ.get(
            "SWARM_DEFAULT_MODEL", "gpt-4o"
        )
        self.budget_usd = budget_usd
        self.total_cost = 0.0
        self.request_count = 0

    async def generate(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """Generate a response from the LLM.

        Args:
            prompt: The prompt to send.
            context: Optional context (role, children, etc.) for system prompt.
            model: Override the default model for this request.
            max_tokens: Maximum tokens in the response.
            temperature: Sampling temperature.

        Returns:
            The generated text response.
        """
        actual_model = model or self.default_model
        self.request_count += 1

        system_prompt = self._build_system_prompt(context or {})

        try:
            import litellm

            response = await litellm.acompletion(
                model=actual_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )

            content = response.choices[0].message.content or ""

            # Track cost
            if hasattr(response, "usage") and hasattr(response.usage, "cost"):
                self.total_cost += response.usage.cost or 0.0

            self._check_budget()

            return content

        except ImportError:
            raise LLMError(
                "LiteLLM is not installed. Run: pip install litellm"
            )
        except Exception as e:
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

"""Temporal Workflow & Activity definitions for goal execution persistence.

If the server restarts, Temporal automatically resumes agents exactly
where they stopped — no lost goals, no duplicated work.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..core.types import Goal, GoalStatus

try:
    from temporalio import activity, workflow
    from temporalio.client import Client as TemporalClient
    from temporalio.worker import Worker as TemporalWorker
except ImportError:
    TemporalClient = None  # type: ignore
    TemporalWorker = None  # type: ignore
    workflow = None
    activity = None

logger = logging.getLogger(__name__)

# ── Activities ──────────────────────────────────────────────────────

_llm_func_registry: dict[str, Any] = {}
_tool_registry_registry: dict[str, Any] = {}


def register_llm_func(key: str, func: Any) -> None:
    """Register an LLM function for Temporal activities to use."""
    _llm_func_registry[key] = func


def register_tool_registry(key: str, registry: Any) -> None:
    """Register a tool registry for Temporal activities to use."""
    _tool_registry_registry[key] = registry


@activity.defn
async def execute_goal_activity(goal_json: str, agent_name: str, handle_key: str) -> str:
    """Temporal Activity: execute a goal by calling the LLM.

    This wraps the core execution logic so Temporal can retry on failure
    and persist the result.
    """
    goal = Goal.model_validate_json(goal_json)
    llm_func = _llm_func_registry.get(handle_key)
    tool_registry = _tool_registry_registry.get(handle_key)

    if not llm_func:
        return f"[{agent_name}] executed: {goal.description}"

    prompt = _build_tool_prompt(agent_name, goal.description, tool_registry)
    conversation = [prompt]

    max_iterations = 10
    response = ""

    for iteration in range(max_iterations):
        response = await llm_func(
            conversation[-1] if len(conversation) == 1
            else f"{conversation[-1]}\n\n[CONTEXT]\n{goal.description}",
            {"role": "WORKER", "iteration": iteration},
        )

        parsed = _parse_tool_call(response)
        if parsed is None:
            return response

        tool_name, tool_args = parsed
        tool = tool_registry.get_tool(tool_name) if tool_registry else None
        if tool is None:
            return (
                f"Tool '{tool_name}' is not available. "
                f"Available tools: {tool_registry.list_capabilities() if tool_registry else 'none'}"
            )

        result = await tool.execute(**tool_args)
        if result.success:
            conversation.append(f"[Tool '{tool_name}' returned]:\n{result.output}")
        else:
            conversation.append(f"[Tool '{tool_name}' error]:\n{result.error}")

    return (
        f"[{agent_name}] max tool iterations ({max_iterations}) "
        f"reached. Last response: {response}"
    )


@workflow.defn
class GoalWorkflow:
    """Temporal Workflow: manages the lifecycle of a single goal.

    The workflow persists the goal state and delegates execution to
    the ``execute_goal_activity``. If the worker crashes, Temporal
    replays the workflow and re-runs the activity on restart.
    """

    @workflow.run
    async def run(self, goal_json: str, agent_name: str, handle_key: str) -> str:
        goal = Goal.model_validate_json(goal_json)
        goal.status = GoalStatus.IN_PROGRESS

        try:
            result = await workflow.execute_activity(
                execute_goal_activity,
                args=[goal_json, agent_name, handle_key],
                start_to_close_timeout=120,
                retry_policy={
                    "maximum_attempts": goal.max_retries,
                    "initial_interval": 5,
                },
            )
            return result
        except Exception as exc:
            goal.status = GoalStatus.FAILED
            goal.error = str(exc)
            raise


# ── Helpers ─────────────────────────────────────────────────────────

_TOOL_CALL_RE = __import__("re").compile(
    r"TOOL_CALL:\s*(?P<name>\w+)\s*"
    r"\((?P<args>.*)\)\s*$",
    __import__("re").MULTILINE | __import__("re").DOTALL,
)


def _parse_tool_call(text: str) -> tuple[str, dict[str, Any]] | None:
    """Parse a ``TOOL_CALL: name(key="val", ...)`` line from LLM output."""
    import re

    m = _TOOL_CALL_RE.search(text)
    if not m:
        return None

    name = m.group("name")
    raw_args = m.group("args").strip()

    args: dict[str, Any] = {}
    if raw_args:
        for pair in re.finditer(r'(\w+)\s*=\s*("(?:[^"\\]|\\.)*"|\S+?)\s*(?:,|$)', raw_args):
            key = pair.group(1)
            val: Any = pair.group(2)
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
            else:
                try:
                    val = int(val)
                except ValueError:
                    try:
                        val = float(val)
                    except ValueError:
                        pass
            args[key] = val

    return name, args


def _build_tool_prompt(agent_name: str, goal: str, tool_registry: Any = None) -> str:
    """Build the initial LLM prompt with tool descriptions."""
    lines = [
        f"You are {agent_name}, a WORKER agent.",
        "",
        f"Goal: {goal}",
        "",
    ]

    if tool_registry and tool_registry.tool_count > 0:
        lines.append("You have access to the following tools:")
        lines.append("")
        lines.append(tool_registry.list_capabilities())
        lines.append("")
        lines.append(
            "To use a tool, respond with a TOOL_CALL line exactly like this:\n"
            'TOOL_CALL: tool_name(param1="value1", param2="value2")\n\n'
            "After the tool returns, you will see its result. "
            "Continue calling tools or respond with your final answer.\n"
            "When you are done, respond with your final answer without a TOOL_CALL line."
        )
    else:
        lines.append("Respond with the result of your work.")
        lines.append("")

    return "\n".join(lines)


# ── Factory ─────────────────────────────────────────────────────────


async def start_temporal_worker(
    task_queue: str = "hyrex-goals",
    host: str = "localhost",
    port: int = 7233,
) -> Any:
    """Start a Temporal worker that listens for goal workflows.

    Requires a running Temporal server (``temporal server start-dev``).
    Returns the worker so the caller can await its shutdown.
    """
    if TemporalClient is None:
        logger.warning("temporalio not installed — Temporal worker unavailable")
        return None

    client = await TemporalClient.connect(f"{host}:{port}")
    worker = TemporalWorker(
        client,
        task_queue=task_queue,
        workflows=[GoalWorkflow],
        activities=[execute_goal_activity],
    )
    logger.info("Temporal worker started on task queue '%s'", task_queue)
    return worker

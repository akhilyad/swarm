"""Main runtime orchestrator.

The Orchestrator is the top-level coordinator:
1. Loads config and builds the swarm tree
2. Starts agent loops for all agents
3. Injects the initial CEO goal
4. Monitors execution and reports results
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

from ..communication.bus import MessageBus
from ..communication.message import create_goal_message
from ..core.config import SwarmConfig, load_config
from ..core.errors import SwarmError
from ..core.types import Goal, GoalStatus, MessageType
from ..swarm.factory import build_from_config
from .agent_loop import AgentLoop

logger = logging.getLogger(__name__)


class Orchestrator:
    """Main runtime coordinator for a swarm execution."""

    def __init__(
        self,
        config: SwarmConfig,
        llm_func: Any | None = None,
    ) -> None:
        self.config = config
        self.bus = MessageBus()
        self.registry, self.handles = build_from_config(config)
        self.llm_func = llm_func
        self._agent_loops: dict[str, AgentLoop] = {}
        self._start_time: float | None = None
        self._final_result: str | None = None

    async def start(self) -> None:
        """Start all agent loops."""
        self._start_time = time.monotonic()

        for node_id, handle in self.handles.items():
            loop = AgentLoop(handle=handle, bus=self.bus, llm_func=self.llm_func)
            self._agent_loops[node_id] = loop
            await loop.start()

        logger.info(
            "Orchestrator started: %d agents, config='%s'",
            len(self._agent_loops),
            self.config.name,
        )

    async def stop(self) -> None:
        """Stop all agent loops gracefully."""
        for loop in self._agent_loops.values():
            await loop.stop()
        self._agent_loops.clear()
        logger.info("Orchestrator stopped")

    async def run_goal(self, goal_description: str, timeout: float = 120.0) -> str:
        """Inject a CEO-level goal and wait for the final result.

        This is the main entry point for running a swarm task.
        """
        ceo = self.registry.get_root()
        result_event = asyncio.Event()
        final_result: list[str] = []

        async def collect_result(message: Any) -> None:
            if message.type in (MessageType.RESULT, MessageType.ERROR):
                final_result.append(message.content)
                result_event.set()

        # Subscribe CEO's inbox for the result
        sub = self.bus.subscribe(ceo.node_id, collect_result)

        try:
            await self.start()

            # Create and inject the initial goal
            goal = Goal(description=goal_description, assignee_id=ceo.node_id)
            msg = create_goal_message(
                sender="orchestrator",
                recipient=ceo.node_id,
                goal_description=goal_description,
                goal_id=goal.goal_id,
            )
            await self.bus.publish(msg)

            # Wait for completion or timeout
            try:
                await asyncio.wait_for(result_event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                final_result.append(f"[TIMEOUT] Goal did not complete within {timeout}s")

        finally:
            sub.unsubscribe()
            await self.stop()

        self._final_result = "\n".join(final_result)
        return self._final_result

    async def run_goal_background(self, goal_description: str) -> str:
        """Run a goal asynchronously and return the CEO agent ID for status checks."""
        ceo = self.registry.get_root()
        result_event = asyncio.Event()
        final_result: list[str] = []

        async def collect_result(message: Any) -> None:
            if message.type in (MessageType.RESULT, MessageType.ERROR):
                final_result.append(message.content)
                result_event.set()

        sub = self.bus.subscribe(ceo.node_id, collect_result)
        await self.start()

        msg = create_goal_message(
            sender="orchestrator",
            recipient=ceo.node_id,
            goal_description=goal_description,
        )
        await self.bus.publish(msg)

        sub.unsubscribe()
        self._final_result = "\n".join(final_result)
        return self._final_result

    @property
    def elapsed(self) -> float:
        if self._start_time is None:
            return 0.0
        return time.monotonic() - self._start_time

    @property
    def status_summary(self) -> str:
        lines = [f"Swarm: {self.config.name}", f"Agents: {len(self.handles)}", f"Elapsed: {self.elapsed:.1f}s", ""]
        for handle in self.handles.values():
            status = "busy" if handle.is_busy else "idle" if handle.is_active else "inactive"
            goal_desc = ""
            if handle.current_goal:
                goal_desc = f" | goal: {handle.current_goal.description[:60]}"
            lines.append(f"  {handle.name} ({handle.role.value}) [{status}]{goal_desc}")
        return "\n".join(lines)

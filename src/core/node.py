"""Runtime wrapper for a swarm agent node."""

from __future__ import annotations

from typing import Any

from .types import Goal, Role, SwarmNode


class NodeHandle:
    """Runtime handle for a swarm agent node.

    Wraps a SwarmNode with runtime state: the agent's current goal,
    status, and accumulated context. This is what the agent loop operates on.
    """

    def __init__(
        self,
        node: SwarmNode,
        current_goal: Goal | None = None,
        is_active: bool = False,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.node = node
        self.current_goal = current_goal
        self.is_active = is_active
        self.context = context or {}

    @property
    def node_id(self) -> str:
        return self.node.node_id

    @property
    def name(self) -> str:
        return self.node.name

    @property
    def role(self) -> Role:
        return self.node.role

    @property
    def is_busy(self) -> bool:
        return self.is_active and self.current_goal is not None

    @property
    def model(self) -> str | None:
        return self.node.model

    def assign_goal(self, goal: Goal) -> None:
        self.current_goal = goal
        self.is_active = True

    def complete_goal(self, result: str) -> None:
        if self.current_goal:
            self.current_goal.result = result
            self.current_goal.status = "completed"
        self.is_active = False
        self.current_goal = None

    def fail_goal(self, error: str) -> None:
        if self.current_goal:
            self.current_goal.error = error
            self.current_goal.status = "failed"
        self.is_active = False
        self.current_goal = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "node": self.node.to_dict(),
            "is_active": self.is_active,
            "current_goal": self.current_goal.to_dict() if self.current_goal else None,
        }

    def __repr__(self) -> str:
        status = "busy" if self.is_busy else "idle" if self.is_active else "inactive"
        return f"NodeHandle({self.name}, role={self.role.value}, status={status})"

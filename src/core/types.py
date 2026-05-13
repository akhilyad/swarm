"""Core data models for the Hyrex platform.

All models use Pydantic for strict validation — invalid data is rejected
at the boundary before it ever reaches the runtime.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Role(str, Enum):
    """Agent role in the swarm hierarchy."""

    CEO = "CEO"
    MANAGER = "MANAGER"
    WORKER = "WORKER"


class GoalStatus(str, Enum):
    """Status of a goal in the system."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MessageType(str, Enum):
    """Types of messages exchanged between agents."""

    GOAL = "goal"
    RESULT = "result"
    QUERY = "query"
    RESPONSE = "response"
    ACK = "ack"
    ERROR = "error"
    CANCEL = "cancel"
    STATUS = "status"
    DELEGATE = "delegate"
    SYNTHESIS = "synthesis"
    CLARIFY = "clarify"


class SwarmNode(BaseModel):
    """An agent node in the swarm tree.

    Each node has a role (CEO, MANAGER, WORKER) and can have children,
    forming a holarchy where every manager IS also a sub-swarm.
    """

    node_id: str
    name: str
    role: Role
    parent_id: str | None = None
    child_ids: list[str] = Field(default_factory=list)
    model: str | None = None
    system_prompt_override: str | None = None
    sub_swarm_config: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_leaf(self) -> bool:
        return len(self.child_ids) == 0

    @property
    def is_root(self) -> bool:
        return self.parent_id is None


class Goal(BaseModel):
    """A goal assigned to an agent.

    Goals flow down the hierarchy: CEO decomposes strategic goals into
    sub-goals for Managers, who further decompose into tasks for Workers.
    Results flow back up.
    """

    description: str
    goal_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    status: GoalStatus = GoalStatus.PENDING
    assignee_id: str | None = None
    parent_goal_id: str | None = None
    sub_goal_ids: list[str] = Field(default_factory=list)
    result: str | None = None
    error: str | None = None
    priority: int = 0
    max_retries: int = 3
    retry_count: int = 0
    timeout_seconds: float | None = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        if self.updated_at is None:
            self.updated_at = self.created_at


class Message(BaseModel):
    """A message sent between agents via the message bus.

    Messages are the sole communication mechanism — agents never call
    each other directly. This enables distributed, restarted, or swapped
    agents without breaking the system.
    """

    type: MessageType
    sender: str
    content: str
    recipient: str | None = None
    recipients: list[str] | None = None
    correlation_id: str | None = None
    message_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    in_reply_to: str | None = None
    goal_id: str | None = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryEntry(BaseModel):
    """A single memory entry stored in the vector database for an agent."""

    agent_id: str
    content: str
    entry_type: str = "experience"
    embedding: list[float] | None = None
    entry_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

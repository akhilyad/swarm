"""Core data models for the Swarm of Swarms platform."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any


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


class SwarmNode:
    """Represents an agent node in the swarm tree.

    Each node has a role (CEO, MANAGER, WORKER) and can have children,
    forming a holarchy where every manager IS also a sub-swarm.
    """

    def __init__(
        self,
        node_id: str,
        name: str,
        role: Role,
        parent_id: str | None = None,
        child_ids: list[str] | None = None,
        model: str | None = None,
        system_prompt_override: str | None = None,
        sub_swarm_config: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.node_id = node_id
        self.name = name
        self.role = role
        self.parent_id = parent_id
        self.child_ids = child_ids or []
        self.model = model
        self.system_prompt_override = system_prompt_override
        self.sub_swarm_config = sub_swarm_config
        self.metadata = metadata or {}

    @property
    def is_leaf(self) -> bool:
        return len(self.child_ids) == 0

    @property
    def is_root(self) -> bool:
        return self.parent_id is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.name,
            "role": self.role.value,
            "parent_id": self.parent_id,
            "child_ids": list(self.child_ids),
            "model": self.model,
            "is_leaf": self.is_leaf,
            "is_root": self.is_root,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SwarmNode:
        return cls(
            node_id=data["node_id"],
            name=data["name"],
            role=Role(data["role"]),
            parent_id=data.get("parent_id"),
            child_ids=data.get("child_ids", []),
            model=data.get("model"),
            system_prompt_override=data.get("system_prompt_override"),
            sub_swarm_config=data.get("sub_swarm_config"),
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        return f"SwarmNode(id={self.node_id}, name={self.name}, role={self.role.value})"


class Goal:
    """A goal assigned to an agent.

    Goals flow down the hierarchy: CEO decomposes strategic goals into
    sub-goals for Managers, who further decompose into tasks for Workers.
    Results flow back up.
    """

    def __init__(
        self,
        description: str,
        goal_id: str | None = None,
        status: GoalStatus = GoalStatus.PENDING,
        assignee_id: str | None = None,
        parent_goal_id: str | None = None,
        sub_goal_ids: list[str] | None = None,
        result: str | None = None,
        error: str | None = None,
        priority: int = 0,
        max_retries: int = 3,
        retry_count: int = 0,
        timeout_seconds: float | None = None,
        created_at: str | None = None,
        updated_at: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.goal_id = goal_id or uuid.uuid4().hex
        self.description = description
        self.status = status
        self.assignee_id = assignee_id
        self.parent_goal_id = parent_goal_id
        self.sub_goal_ids = sub_goal_ids or []
        self.result = result
        self.error = error
        self.priority = priority
        self.max_retries = max_retries
        self.retry_count = retry_count
        self.timeout_seconds = timeout_seconds
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.updated_at = updated_at or self.created_at
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "description": self.description,
            "status": self.status.value,
            "assignee_id": self.assignee_id,
            "parent_goal_id": self.parent_goal_id,
            "sub_goal_ids": list(self.sub_goal_ids),
            "result": self.result,
            "error": self.error,
            "priority": self.priority,
            "max_retries": self.max_retries,
            "retry_count": self.retry_count,
            "timeout_seconds": self.timeout_seconds,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Goal:
        return cls(
            goal_id=data.get("goal_id"),
            description=data["description"],
            status=GoalStatus(data.get("status", "pending")),
            assignee_id=data.get("assignee_id"),
            parent_goal_id=data.get("parent_goal_id"),
            sub_goal_ids=data.get("sub_goal_ids", []),
            result=data.get("result"),
            error=data.get("error"),
            priority=data.get("priority", 0),
            max_retries=data.get("max_retries", 3),
            retry_count=data.get("retry_count", 0),
            timeout_seconds=data.get("timeout_seconds"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        return f"Goal(id={self.goal_id}, status={self.status.value}, assignee={self.assignee_id})"


class Message:
    """A message sent between agents via the message bus.

    Messages are the sole communication mechanism — agents never call
    each other directly. This enables distributed, restarted, or swapped
    agents without breaking the system.
    """

    def __init__(
        self,
        type: MessageType,
        sender: str,
        content: str,
        recipient: str | None = None,
        recipients: list[str] | None = None,
        correlation_id: str | None = None,
        message_id: str | None = None,
        in_reply_to: str | None = None,
        goal_id: str | None = None,
        timestamp: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.message_id = message_id or uuid.uuid4().hex
        self.type = type
        self.sender = sender
        self.content = content
        self.recipient = recipient  # Single recipient or None for broadcast
        self.recipients = recipients  # Explicit list for fan-out
        self.correlation_id = correlation_id  # Links replies to original messages
        self.in_reply_to = in_reply_to
        self.goal_id = goal_id
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "type": self.type.value,
            "sender": self.sender,
            "content": self.content,
            "recipient": self.recipient,
            "recipients": self.recipients,
            "correlation_id": self.correlation_id,
            "in_reply_to": self.in_reply_to,
            "goal_id": self.goal_id,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Message:
        return cls(
            message_id=data.get("message_id"),
            type=MessageType(data["type"]),
            sender=data["sender"],
            content=data["content"],
            recipient=data.get("recipient"),
            recipients=data.get("recipients"),
            correlation_id=data.get("correlation_id"),
            in_reply_to=data.get("in_reply_to"),
            goal_id=data.get("goal_id"),
            timestamp=data.get("timestamp"),
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        return f"Message(id={self.message_id}, type={self.type.value}, from={self.sender})"


class MemoryEntry:
    """A single memory entry stored in the vector database for an agent."""

    def __init__(
        self,
        agent_id: str,
        content: str,
        entry_type: str = "experience",
        embedding: list[float] | None = None,
        entry_id: str | None = None,
        timestamp: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.entry_id = entry_id or uuid.uuid4().hex
        self.agent_id = agent_id
        self.content = content
        self.entry_type = entry_type
        self.embedding = embedding
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "agent_id": self.agent_id,
            "content": self.content,
            "entry_type": self.entry_type,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryEntry:
        return cls(
            entry_id=data.get("entry_id"),
            agent_id=data["agent_id"],
            content=data["content"],
            entry_type=data.get("entry_type", "experience"),
            embedding=data.get("embedding"),
            timestamp=data.get("timestamp"),
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        return f"MemoryEntry(id={self.entry_id}, agent={self.agent_id}, type={self.entry_type})"

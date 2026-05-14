"""NATS-backed pub/sub message bus for inter-agent communication.

Replaces the in-memory bus with NATS JetStream, enabling agents to run on
different processes, machines, or containers. The public API
(``subscribe``, ``unsubscribe``, ``publish``, ``publish_to_many``)
is identical to the original in-memory bus — existing code continues
to work unchanged.

Every published message is persisted to a JetStream stream so active goals
survive a process restart.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

from ..core.types import Goal, GoalStatus, Message

try:
    import nats as _nats
    from nats.js import JetStreamContext
except ImportError:
    _nats = None  # type: ignore[assignment]
    JetStreamContext = None  # type: ignore[assignment, misc]

logger = logging.getLogger(__name__)

MessageHandler = Callable[[Message], Awaitable[None]]
SubscriptionId = int

_STREAM_NAME = "swarm_messages"
_STREAM_MAX_AGE = 7 * 24 * 3600  # 7 days in seconds
_CONSUMER_PREFIX = "swarm-sub-"


class Subscription:
    """A registered subscription that can be unsubscribed."""

    def __init__(self, sub_id: SubscriptionId, topic: str, handler: MessageHandler, bus: MessageBus) -> None:
        self.sub_id = sub_id
        self.topic = topic
        self.handler = handler
        self._bus = bus

    def unsubscribe(self) -> None:
        self._bus.unsubscribe(self.sub_id)


class MessageBus:
    """Async pub/sub message bus backed by NATS JetStream.

    Each agent subscribes on its agent-ID topic for direct messages.
    Topics enable group communication: broadcast, department, role-based.

    Messages are persisted in a JetStream stream for crash recovery.

    Usage::

        bus = MessageBus()
        await bus.connect()
        sub = bus.subscribe("agent-123", my_handler)
        await bus.publish(Message(type="goal", sender="ceo", content="...", recipient="agent-123"))
        sub.unsubscribe()
        await bus.disconnect()
    """

    def __init__(self, nats_url: str = "nats://localhost:4222") -> None:
        self._nats_url = nats_url
        self._nc: Any = None
        self._js: Any = None
        self._local_subscriptions: dict[str, dict[SubscriptionId, MessageHandler]] = {}
        self._nats_subs: list[Any] = []
        self._next_id: SubscriptionId = 0
        self._pending_messages: dict[str, list[Message]] = {}

    def get_active_goals(self) -> list[Goal]:
        """Re-hydrate pending goal messages tracked in memory.

        Call this at startup to restore goals that were in-flight when
        the process last crashed.
        """
        from datetime import datetime, timezone

        goals: list[Goal] = []
        for msg in self._pending_messages.get("goal", []):
            goals.append(
                Goal(
                    description=msg.content,
                    goal_id=msg.goal_id or "",
                    assignee_id=msg.recipient or msg.sender,
                    status=GoalStatus.PENDING,
                    created_at=datetime.now(timezone.utc).isoformat(),
                )
            )
        return goals

    async def get_kv_store(self, bucket: str = "agent_state") -> Any | None:
        """Get (or create) a JetStream KV bucket for state persistence.

        Returns ``None`` when NATS is not connected — callers should
        fall back to local file storage in that case.
        """
        if not self._js:
            return None
        try:
            return await self._js.create_key_value(bucket=bucket)
        except Exception:
            return None

    async def connect(self) -> None:
        """Connect to the NATS server and set up a JetStream context.

        Ensures the ``swarm_messages`` stream exists.
        """
        if _nats is None:
            logger.warning("nats-py is not installed — install with: pip install nats-py")
            return
        try:
            self._nc = await _nats.connect(self._nats_url, connect_timeout=2)
            self._js = self._nc.jetstream()

            # Ensure the stream exists (create-if-not-exists)
            try:
                await self._js.add_stream(
                    name=_STREAM_NAME,
                    subjects=[f"{_STREAM_NAME}.>"],
                    max_age=_STREAM_MAX_AGE,
                )
            except Exception:
                # Stream likely already exists
                pass

            logger.info("Connected to NATS JetStream at %s", self._nats_url)
        except Exception as exc:
            logger.warning("NATS not available, falling back to local-only bus: %s", exc)
            self._nc = None
            self._js = None

    async def disconnect(self) -> None:
        """Disconnect from NATS and clean up."""
        for sub in self._nats_subs:
            try:
                await sub.unsubscribe()
            except Exception:
                pass
        self._nats_subs.clear()
        if self._nc:
            try:
                await self._nc.drain()
            except Exception:
                pass
            self._nc = None
            self._js = None
        logger.info("Disconnected from NATS")

    def subscribe(self, topic: str, handler: MessageHandler) -> Subscription:
        """Register a handler for messages on a given topic.

        Topics can be agent IDs (for direct messages) or group names
        (for department/role broadcasts).

        Returns a ``Subscription`` that can be unsubscribed later.
        """
        sub_id = self._next_id
        self._next_id += 1

        self._local_subscriptions.setdefault(topic, {})[sub_id] = handler

        if self._nc and self._js:
            async def nats_handler(msg) -> None:
                try:
                    data = json.loads(msg.data.decode())
                    message = Message(**data)
                    await handler(message)
                except Exception as exc:
                    logger.error("NATS message handler error on topic %s: %s", topic, exc)

            async def _subscribe() -> None:
                subject = f"{_STREAM_NAME}.{topic}"
                try:
                    # Durable consumer so messages survive disconnects
                    consumer_name = f"{_CONSUMER_PREFIX}{topic}"
                    sub = await self._js.subscribe(
                        subject=subject,
                        durable=consumer_name,
                        cb=nats_handler,
                        stream=_STREAM_NAME,
                    )
                    self._nats_subs.append(sub)
                except Exception as exc:
                    logger.warning(
                        "JetStream subscribe failed for %s, falling back to core NATS: %s",
                        subject, exc,
                    )

            asyncio.ensure_future(_subscribe())

        return Subscription(sub_id, topic, handler, self)

    def unsubscribe(self, sub_id: SubscriptionId) -> None:
        """Remove a local subscription by ID."""
        for topic in list(self._local_subscriptions.keys()):
            self._local_subscriptions[topic].pop(sub_id, None)
            if not self._local_subscriptions[topic]:
                del self._local_subscriptions[topic]

    async def publish(self, message: Message) -> int:
        """Publish a message to its recipients via NATS JetStream.

        Dispatches to:
        - The specific recipient's topic (if ``message.recipient`` is set)
        - All listed recipients (if ``message.recipients`` is set)
        - All subscribers on the message type topic (e.g. ``type:goal``)

        Every message is persisted to the JetStream stream so active goals
        survive a process restart.

        Returns the number of locally-dispatched handlers called.
        """
        # Track pending goals for crash recovery
        if message.type.value == "goal":
            self._pending_messages.setdefault("goal", []).append(message)
        elif message.type.value in ("result", "error", "cancel"):
            # Remove completed/resolved goals from pending
            if message.goal_id:
                self._pending_messages["goal"] = [
                    m for m in self._pending_messages.get("goal", [])
                    if m.goal_id != message.goal_id
                ]

        targets: list[str] = []

        if message.recipient:
            targets.append(message.recipient)
        if message.recipients:
            targets.extend(message.recipients)

        type_topic = f"type:{message.type.value}"
        payload = json.dumps(message.model_dump()).encode()

        if self._js:
            for target in targets:
                subject = f"{_STREAM_NAME}.{target}"
                try:
                    await self._js.publish(subject, payload)
                except Exception as exc:
                    logger.error("JetStream publish to %s failed: %s", subject, exc)
            # Also publish to type topic
            type_subject = f"{_STREAM_NAME}.{type_topic}"
            try:
                await self._js.publish(type_subject, payload)
            except Exception:
                pass
        elif self._nc:
            for target in targets:
                try:
                    await self._nc.publish(target, payload)
                except Exception:
                    pass
            try:
                await self._nc.publish(type_topic, payload)
            except Exception:
                pass

        to_call: list[MessageHandler] = []
        seen: set[SubscriptionId] = set()

        for target in targets:
            for sub_id, handler in self._local_subscriptions.get(target, {}).items():
                if sub_id not in seen:
                    seen.add(sub_id)
                    to_call.append(handler)

        for sub_id, handler in self._local_subscriptions.get(type_topic, {}).items():
            if sub_id not in seen:
                seen.add(sub_id)
                to_call.append(handler)

        count = 0
        for handler in to_call:
            try:
                await handler(message)
                count += 1
            except Exception:
                pass

        return count

    async def publish_to_many(self, message: Message, recipients: list[str]) -> int:
        """Convenience: publish to an explicit list of recipients."""
        original_recipient = message.recipient
        original_recipients = message.recipients

        message.recipient = None
        message.recipients = recipients
        try:
            return await self.publish(message)
        finally:
            message.recipient = original_recipient
            message.recipients = original_recipients

    @property
    def topic_count(self) -> int:
        return len(self._local_subscriptions)

    @property
    def subscription_count(self) -> int:
        return sum(len(handlers) for handlers in self._local_subscriptions.values())

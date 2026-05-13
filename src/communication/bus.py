"""Async pub/sub message bus for inter-agent communication.

Agents communicate exclusively through this bus — they never call each
other directly. This decoupling means agents can be distributed across
processes/machines, restarted, or swapped without affecting the system.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Awaitable, Callable

from ..core.errors import CommunicationError
from ..core.types import Message

MessageHandler = Callable[[Message], Awaitable[None]]
SubscriptionId = int


class Subscription:
    """A registered message handler that can be unsubscribed."""

    def __init__(self, sub_id: SubscriptionId, topic: str, handler: MessageHandler, bus: MessageBus) -> None:
        self.sub_id = sub_id
        self.topic = topic
        self.handler = handler
        self._bus = bus

    def unsubscribe(self) -> None:
        self._bus.unsubscribe(self.sub_id)


class MessageBus:
    """Async pub/sub message bus with topic-based routing.

    Each agent has an inbox (topic = agent_id) for direct messages.
    Topics enable group communication: broadcast, department, role-based.

    Usage:
        bus = MessageBus()
        sub = bus.subscribe("agent-123", my_handler)
        await bus.publish(Message(type="goal", sender="ceo", content="...", recipient="agent-123"))
        sub.unsubscribe()
    """

    def __init__(self) -> None:
        self._subscriptions: dict[str, dict[SubscriptionId, MessageHandler]] = defaultdict(dict)
        self._next_id: SubscriptionId = 0
        self._lock = asyncio.Lock()

    def subscribe(self, topic: str, handler: MessageHandler) -> Subscription:
        """Register a handler for messages on a given topic.

        Topics can be agent IDs (for direct messages) or group names
        (for department/role broadcasts).
        """
        sub_id = self._next_id
        self._next_id += 1
        self._subscriptions[topic][sub_id] = handler
        return Subscription(sub_id, topic, handler, self)

    def unsubscribe(self, sub_id: SubscriptionId) -> None:
        """Remove a subscription by ID."""
        for topic in list(self._subscriptions.keys()):
            self._subscriptions[topic].pop(sub_id, None)
            if not self._subscriptions[topic]:
                del self._subscriptions[topic]

    async def publish(self, message: Message) -> int:
        """Publish a message to its recipients.

        Dispatches to:
        - The specific recipient's topic (if ``message.recipient`` is set)
        - All listed recipients (if ``message.recipients`` is set)
        - All subscribers on the message type topic (e.g. "type:goal")

        Returns the number of handlers called.
        """
        targets: list[str] = []

        if message.recipient:
            targets.append(message.recipient)
        if message.recipients:
            targets.extend(message.recipients)

        # Also publish to type-based topic for monitoring/logging
        type_topic = f"type:{message.type.value}"

        # Collect handlers under lock, call them outside to avoid deadlock
        # when handlers publish replies.
        to_call: list[MessageHandler] = []
        async with self._lock:
            seen: set[SubscriptionId] = set()
            for target in targets:
                for sub_id, handler in self._subscriptions.get(target, {}).items():
                    if sub_id not in seen:
                        seen.add(sub_id)
                        to_call.append(handler)

            for sub_id, handler in self._subscriptions.get(type_topic, {}).items():
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
        return len(self._subscriptions)

    @property
    def subscription_count(self) -> int:
        return sum(len(handlers) for handlers in self._subscriptions.values())

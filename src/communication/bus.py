"""NATS-backed pub/sub message bus for inter-agent communication.

Replaces the in-memory bus with NATS, enabling agents to run on
different processes, machines, or containers. The public API
(``subscribe``, ``unsubscribe``, ``publish``, ``publish_to_many``)
is identical to the original in-memory bus — existing code continues
to work unchanged.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Awaitable, Callable

from ..core.types import Message

try:
    import nats as _nats
except ImportError:
    _nats = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

MessageHandler = Callable[[Message], Awaitable[None]]
SubscriptionId = int


class Subscription:
    """A registered NATS subscription that can be unsubscribed."""

    def __init__(self, sub_id: SubscriptionId, topic: str, handler: MessageHandler, bus: MessageBus) -> None:
        self.sub_id = sub_id
        self.topic = topic
        self.handler = handler
        self._bus = bus

    def unsubscribe(self) -> None:
        self._bus.unsubscribe(self.sub_id)


class MessageBus:
    """Async pub/sub message bus backed by NATS.

    Each agent subscribes on its agent-ID topic for direct messages.
    Topics enable group communication: broadcast, department, role-based.

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
        self._local_subscriptions: dict[str, dict[SubscriptionId, MessageHandler]] = {}
        self._nats_subs: list[Any] = []
        self._next_id: SubscriptionId = 0

    async def connect(self) -> None:
        """Connect to the NATS server.

        NATS is optional — the bus also works fully in-process without
        connecting. Call this only when you need cross-process routing.
        """
        if _nats is None:
            logger.warning("nats-py is not installed — install with: pip install nats-py")
            return
        try:
            self._nc = await _nats.connect(self._nats_url, connect_timeout=2)
            logger.info("Connected to NATS at %s", self._nats_url)
        except Exception as exc:
            logger.warning("NATS not available, falling back to local-only bus: %s", exc)
            self._nc = None

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

        if self._nc:
            async def nats_handler(msg) -> None:
                try:
                    data = json.loads(msg.data.decode())
                    message = Message(**data)
                    await handler(message)
                except Exception as exc:
                    logger.error("NATS message handler error on topic %s: %s", topic, exc)

            async def _subscribe() -> None:
                sub = await self._nc.subscribe(topic, cb=nats_handler)
                self._nats_subs.append(sub)

            import asyncio
            asyncio.ensure_future(_subscribe())

        return Subscription(sub_id, topic, handler, self)

    def unsubscribe(self, sub_id: SubscriptionId) -> None:
        """Remove a local subscription by ID."""
        for topic in list(self._local_subscriptions.keys()):
            self._local_subscriptions[topic].pop(sub_id, None)
            if not self._local_subscriptions[topic]:
                del self._local_subscriptions[topic]

    async def publish(self, message: Message) -> int:
        """Publish a message to its recipients via NATS.

        Dispatches to:
        - The specific recipient's topic (if ``message.recipient`` is set)
        - All listed recipients (if ``message.recipients`` is set)
        - All subscribers on the message type topic (e.g. ``type:goal``)

        Returns the number of locally-dispatched handlers called.
        """
        targets: list[str] = []

        if message.recipient:
            targets.append(message.recipient)
        if message.recipients:
            targets.extend(message.recipients)

        type_topic = f"type:{message.type.value}"
        payload = json.dumps(message.model_dump()).encode()

        if self._nc:
            for target in targets:
                await self._nc.publish(target, payload)
            await self._nc.publish(type_topic, payload)

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

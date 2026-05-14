"""Higher-level communication patterns built on the message bus.

Provides common interaction patterns:
- fan_out: send a message to all children of a node
- fan_in: collect results from multiple agents
- request_response: send a message and wait for a correlated reply
"""

from __future__ import annotations

import asyncio

from ..core.errors import CommunicationError
from ..core.types import Message
from .bus import MessageBus


async def fan_out(
    bus: MessageBus,
    message: Message,
    recipients: list[str],
    timeout: float = 30.0,
) -> list[Message]:
    """Send a message to multiple recipients and collect their replies.

    Subscribes on the sender's topic since replies are addressed back to
    the original sender.
    """
    replies: list[Message] = []
    reply_event = asyncio.Event()

    async def collector(msg: Message) -> None:
        if msg.correlation_id == message.message_id:
            replies.append(msg)
            reply_event.set()

    # Replies come back to the sender — listen there
    sender_topic = message.sender
    sub = bus.subscribe(sender_topic, collector)

    try:
        message.correlation_id = message.message_id
        await bus.publish_to_many(message, recipients)

        try:
            await asyncio.wait_for(reply_event.wait(), timeout=timeout)
            await asyncio.sleep(0.1)
        except asyncio.TimeoutError:
            pass
    finally:
        sub.unsubscribe()

    return replies


async def fan_in(
    bus: MessageBus,
    message: Message,
    recipients: list[str],
    min_replies: int = 1,
    timeout: float = 30.0,
) -> list[Message]:
    """Fan-out and wait until min_replies are collected or timeout."""
    replies: list[Message] = []
    received_event = asyncio.Event()

    async def collector(msg: Message) -> None:
        if msg.correlation_id == message.message_id:
            replies.append(msg)
            if len(replies) >= min_replies:
                received_event.set()

    # Replies come back to the sender — listen there
    sender_topic = message.sender
    sub = bus.subscribe(sender_topic, collector)

    try:
        message.correlation_id = message.message_id
        await bus.publish_to_many(message, recipients)

        try:
            await asyncio.wait_for(received_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass
    finally:
        sub.unsubscribe()

    return replies


async def request_response(
    bus: MessageBus,
    message: Message,
    recipient: str,
    timeout: float = 60.0,
) -> Message:
    """Send a message to a single recipient and wait for a reply.

    Raises CommunicationError on timeout.
    """
    response: Message | None = None
    response_event = asyncio.Event()

    async def collector(msg: Message) -> None:
        nonlocal response
        if msg.correlation_id == message.message_id:
            response = msg
            response_event.set()

    # Reply comes back to the sender — listen there
    sender_topic = message.sender
    sub = bus.subscribe(sender_topic, collector)

    try:
        message.correlation_id = message.message_id
        await bus.publish(message)

        try:
            await asyncio.wait_for(response_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            raise CommunicationError(
                f"No response from '{recipient}' within {timeout}s"
            )

        if response is None:
            raise CommunicationError(f"Empty response from '{recipient}'")

        return response
    finally:
        sub.unsubscribe()

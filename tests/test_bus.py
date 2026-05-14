"""Tests for the async message bus.

All tests now run against the in-memory/local NATS fallback mode
(SQLite dependency removed).
"""

import pytest

from src.communication.bus import MessageBus
from src.communication.message import create_goal_message, create_reply, create_result_message
from src.communication.protocol import fan_in, fan_out, request_response
from src.core.errors import CommunicationError
from src.core.types import Message, MessageType


@pytest.fixture
def bus() -> MessageBus:
    return MessageBus()


class TestMessageBus:
    async def test_subscribe_and_publish(self, bus: MessageBus) -> None:
        received: list[Message] = []

        async def handler(msg: Message) -> None:
            received.append(msg)

        sub = bus.subscribe("agent-1", handler)
        msg = Message(type=MessageType.GOAL, sender="ceo", content="hello", recipient="agent-1")
        count = await bus.publish(msg)

        assert count >= 1
        assert len(received) == 1
        assert received[0].content == "hello"
        sub.unsubscribe()

    async def test_unsubscribe(self, bus: MessageBus) -> None:
        received: list[Message] = []

        async def handler(msg: Message) -> None:
            received.append(msg)

        sub = bus.subscribe("agent-1", handler)
        sub.unsubscribe()

        msg = Message(type=MessageType.GOAL, sender="ceo", content="hello", recipient="agent-1")
        await bus.publish(msg)
        assert len(received) == 0

    async def test_publish_to_many(self, bus: MessageBus) -> None:
        received: dict[str, list[Message]] = {"a": [], "b": []}

        async def handler_a(msg: Message) -> None:
            received["a"].append(msg)

        async def handler_b(msg: Message) -> None:
            received["b"].append(msg)

        bus.subscribe("a", handler_a)
        bus.subscribe("b", handler_b)

        msg = Message(type=MessageType.GOAL, sender="ceo", content="broadcast")
        await bus.publish_to_many(msg, ["a", "b"])

        assert len(received["a"]) == 1
        assert len(received["b"]) == 1

    async def test_type_subscription(self, bus: MessageBus) -> None:
        received: list[Message] = []

        async def handler(msg: Message) -> None:
            received.append(msg)

        bus.subscribe("type:goal", handler)
        msg = Message(type=MessageType.GOAL, sender="ceo", content="test", recipient="some-agent")
        await bus.publish(msg)

        assert len(received) == 1

    async def test_get_active_goals_returns_pending_goals(self, bus: MessageBus) -> None:
        msg = create_goal_message(sender="ceo", recipient="worker", goal_description="test goal")
        await bus.publish(msg)
        goals = bus.get_active_goals()
        assert len(goals) == 1
        assert goals[0].description == "test goal"


class TestMessageFactory:
    def test_create_goal_message(self) -> None:
        msg = create_goal_message(sender="ceo", recipient="pm", goal_description="Build feature")
        assert msg.type == MessageType.GOAL
        assert msg.sender == "ceo"
        assert msg.recipient == "pm"
        assert "Build feature" in msg.content

    def test_create_result_message(self) -> None:
        msg = create_result_message(sender="worker", recipient="manager", result="Done")
        assert msg.type == MessageType.RESULT
        assert msg.content == "Done"

    def test_create_reply(self) -> None:
        original = Message(type=MessageType.QUERY, sender="a", content="ping", recipient="b")
        reply = create_reply(original, sender="b", content="pong")
        assert reply.recipient == "a"
        assert reply.in_reply_to == original.message_id


class TestProtocolPatterns:
    async def test_request_response_success(self, bus: MessageBus) -> None:
        async def handler(msg: Message) -> None:
            reply = Message(
                type=MessageType.RESPONSE,
                sender="responder",
                recipient=msg.sender,
                content="pong",
                correlation_id=msg.message_id,
            )
            await bus.publish(reply)

        bus.subscribe("responder", handler)
        msg = Message(type=MessageType.QUERY, sender="asker", content="ping", recipient="responder")
        response = await request_response(bus, msg, "responder", timeout=5.0)
        assert response.content == "pong"

    async def test_request_response_timeout(self, bus: MessageBus) -> None:
        msg = Message(type=MessageType.QUERY, sender="asker", content="ping", recipient="silent-agent")
        with pytest.raises(CommunicationError, match="No response"):
            await request_response(bus, msg, "silent-agent", timeout=0.1)

    async def test_fan_out(self, bus: MessageBus) -> None:
        async def handler_1(msg: Message) -> None:
            reply = Message(
                type=MessageType.RESPONSE, sender="r1", recipient=msg.sender,
                content="from 1", correlation_id=msg.message_id,
            )
            await bus.publish(reply)

        async def handler_2(msg: Message) -> None:
            reply = Message(
                type=MessageType.RESPONSE, sender="r2", recipient=msg.sender,
                content="from 2", correlation_id=msg.message_id,
            )
            await bus.publish(reply)

        bus.subscribe("r1", handler_1)
        bus.subscribe("r2", handler_2)

        msg = Message(type=MessageType.QUERY, sender="asker", content="fan-out")
        replies = await fan_out(bus, msg, ["r1", "r2"], timeout=5.0)
        assert len(replies) >= 2

    async def test_fan_in(self, bus: MessageBus) -> None:
        async def handler(msg: Message) -> None:
            reply = Message(
                type=MessageType.RESPONSE, sender="r1", recipient=msg.sender,
                content="data", correlation_id=msg.message_id,
            )
            await bus.publish(reply)

        bus.subscribe("r1", handler)
        msg = Message(type=MessageType.QUERY, sender="asker", content="fan-in")
        replies = await fan_in(bus, msg, ["r1", "silent"], min_replies=1, timeout=5.0)
        assert len(replies) >= 1

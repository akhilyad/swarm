"""Tests for the agent event loop."""

import pytest

from src.communication.bus import MessageBus
from src.communication.message import create_goal_message
from src.core.node import NodeHandle
from src.core.types import MessageType, Role, SwarmNode
from src.runtime.agent_loop import AgentLoop


@pytest.fixture
def bus() -> MessageBus:
    return MessageBus()


class TestAgentLoop:
    async def test_worker_executes_goal(self, bus: MessageBus) -> None:
        node = SwarmNode(node_id="worker", name="Worker", role=Role.WORKER)
        handle = NodeHandle(node=node)
        loop = AgentLoop(handle=handle, bus=bus)

        results: list[str] = []

        async def collect(msg: object) -> None:
            if hasattr(msg, "type") and msg.type in (MessageType.RESULT, MessageType.ERROR):
                results.append(msg.content)

        bus.subscribe("ceo", collect)
        await loop.start()

        msg = create_goal_message(sender="ceo", recipient="worker", goal_description="Do the thing")
        await bus.publish(msg)

        import asyncio
        await asyncio.sleep(0.2)

        assert len(results) == 1
        assert "Do the thing" in results[0]
        await loop.stop()

    async def test_manager_delegates_to_children(self, bus: MessageBus) -> None:
        worker_node = SwarmNode(node_id="child", name="Child", role=Role.WORKER, parent_id="manager")
        manager_node = SwarmNode(
            node_id="manager", name="Manager", role=Role.MANAGER,
            child_ids=["child"],
        )
        manager_handle = NodeHandle(node=manager_node)
        manager_loop = AgentLoop(handle=manager_handle, bus=bus)

        worker_handle = NodeHandle(node=worker_node)
        worker_loop = AgentLoop(handle=worker_handle, bus=bus)

        results: list[str] = []

        async def collect(msg: object) -> None:
            if hasattr(msg, "type") and msg.type in (MessageType.RESULT, MessageType.ERROR):
                results.append(msg.content)

        bus.subscribe("ceo", collect)
        await manager_loop.start()
        await worker_loop.start()

        msg = create_goal_message(sender="ceo", recipient="manager", goal_description="Coordinate work")
        await bus.publish(msg)

        import asyncio
        await asyncio.sleep(0.5)

        assert len(results) >= 1
        assert "Child" in results[0]
        await manager_loop.stop()
        await worker_loop.stop()

    async def test_cancel_goal(self, bus: MessageBus) -> None:
        node = SwarmNode(node_id="worker", name="Worker", role=Role.WORKER)
        handle = NodeHandle(node=node)
        loop = AgentLoop(handle=handle, bus=bus)

        from src.core.types import Message

        await loop.start()

        goal_msg = create_goal_message(sender="ceo", recipient="worker", goal_description="Task")
        await bus.publish(goal_msg)
        import asyncio
        await asyncio.sleep(0.1)

        cancel_msg = Message(
            type=MessageType.CANCEL, sender="ceo", recipient="worker",
            content="cancel", goal_id=goal_msg.goal_id,
        )
        await bus.publish(cancel_msg)
        await asyncio.sleep(0.1)

        await loop.stop()

    async def test_status_query(self, bus: MessageBus) -> None:
        node = SwarmNode(node_id="worker", name="Worker", role=Role.WORKER)
        handle = NodeHandle(node=node)
        loop = AgentLoop(handle=handle, bus=bus)

        await loop.start()

        from src.core.types import Message

        status_msg = Message(
            type=MessageType.STATUS, sender="ceo", recipient="worker", content="status?"
        )

        replies: list[str] = []

        async def collect(msg: object) -> None:
            if hasattr(msg, "type") and msg.type == MessageType.RESPONSE:
                replies.append(msg.content)

        bus.subscribe("ceo", collect)
        await bus.publish(status_msg)

        import asyncio
        await asyncio.sleep(0.2)

        assert len(replies) >= 1
        assert "Worker" in replies[0]
        await loop.stop()

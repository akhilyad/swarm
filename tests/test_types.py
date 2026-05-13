"""Tests for core data models."""

from src.core.types import Goal, GoalStatus, MemoryEntry, Message, MessageType, Role, SwarmNode


class TestRole:
    def test_role_values(self) -> None:
        assert Role.CEO.value == "CEO"
        assert Role.MANAGER.value == "MANAGER"
        assert Role.WORKER.value == "WORKER"


class TestSwarmNode:
    def test_create_ceo(self) -> None:
        node = SwarmNode(node_id="ceo", name="CEO", role=Role.CEO)
        assert node.is_root
        assert node.is_leaf
        assert node.parent_id is None
        assert node.child_ids == []

    def test_create_manager(self) -> None:
        node = SwarmNode(
            node_id="pm", name="PM", role=Role.MANAGER,
            parent_id="ceo", child_ids=["w1", "w2"],
        )
        assert not node.is_root
        assert not node.is_leaf
        assert node.parent_id == "ceo"

    def test_create_worker(self) -> None:
        node = SwarmNode(node_id="w1", name="Worker", role=Role.WORKER, parent_id="pm")
        assert not node.is_root
        assert node.is_leaf

    def test_to_dict_roundtrip(self) -> None:
        original = SwarmNode(
            node_id="test", name="Test", role=Role.MANAGER,
            parent_id="root", child_ids=["a", "b"],
            model="gpt-4o",
        )
        data = original.to_dict()
        restored = SwarmNode.from_dict(data)
        assert restored.node_id == original.node_id
        assert restored.name == original.name
        assert restored.role == original.role
        assert restored.parent_id == original.parent_id
        assert restored.child_ids == original.child_ids


class TestGoal:
    def test_create_goal(self) -> None:
        goal = Goal(description="Build a feature")
        assert goal.status == GoalStatus.PENDING
        assert goal.retry_count == 0

    def test_goal_with_parent(self) -> None:
        parent = Goal(description="Parent", goal_id="parent-1")
        child = Goal(description="Child", parent_goal_id=parent.goal_id)
        assert child.parent_goal_id == "parent-1"

    def test_to_dict_roundtrip(self) -> None:
        original = Goal(
            description="Test goal",
            priority=2,
            max_retries=5,
            timeout_seconds=60.0,
        )
        data = original.to_dict()
        restored = Goal.from_dict(data)
        assert restored.description == original.description
        assert restored.priority == original.priority
        assert restored.max_retries == original.max_retries


class TestMessage:
    def test_create_message(self) -> None:
        msg = Message(type=MessageType.GOAL, sender="ceo", content="Do something", recipient="pm")
        assert msg.type == MessageType.GOAL
        assert msg.recipient == "pm"

    def test_message_with_correlation(self) -> None:
        original = Message(type=MessageType.QUERY, sender="a", content="ping", recipient="b")
        reply = Message(
            type=MessageType.RESPONSE,
            sender="b", content="pong", recipient="a",
            correlation_id=original.message_id,
            in_reply_to=original.message_id,
        )
        assert reply.correlation_id == original.message_id
        assert reply.in_reply_to == original.message_id

    def test_to_dict_roundtrip(self) -> None:
        original = Message(
            type=MessageType.GOAL, sender="ceo", content="test",
            recipient="worker", recipients=["w1", "w2"],
        )
        data = original.to_dict()
        restored = Message.from_dict(data)
        assert restored.type == original.type
        assert restored.sender == original.sender
        assert restored.content == original.content


class TestMemoryEntry:
    def test_create_entry(self) -> None:
        entry = MemoryEntry(agent_id="ceo", content="Important fact")
        assert entry.agent_id == "ceo"
        assert entry.entry_type == "experience"

    def test_to_dict_roundtrip(self) -> None:
        original = MemoryEntry(agent_id="w1", content="data", entry_type="observation")
        data = original.to_dict()
        restored = MemoryEntry.from_dict(data)
        assert restored.agent_id == original.agent_id
        assert restored.content == original.content
        assert restored.entry_type == original.entry_type

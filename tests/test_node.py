"""Tests for NodeHandle."""

from src.core.node import NodeHandle
from src.core.types import Goal, Role, SwarmNode


class TestNodeHandle:
    def test_create_handle(self) -> None:
        node = SwarmNode(node_id="w1", name="Worker", role=Role.WORKER)
        handle = NodeHandle(node=node)
        assert not handle.is_active
        assert not handle.is_busy

    def test_assign_goal(self) -> None:
        node = SwarmNode(node_id="w1", name="Worker", role=Role.WORKER)
        handle = NodeHandle(node=node)
        goal = Goal(description="Do something")
        handle.assign_goal(goal)
        assert handle.is_active
        assert handle.is_busy

    def test_complete_goal(self) -> None:
        node = SwarmNode(node_id="w1", name="Worker", role=Role.WORKER)
        handle = NodeHandle(node=node)
        goal = Goal(description="Do something")
        handle.assign_goal(goal)
        handle.complete_goal("Done!")
        assert not handle.is_active
        assert not handle.is_busy
        assert goal.result == "Done!"

    def test_fail_goal(self) -> None:
        node = SwarmNode(node_id="w1", name="Worker", role=Role.WORKER)
        handle = NodeHandle(node=node)
        goal = Goal(description="Do something")
        handle.assign_goal(goal)
        handle.fail_goal("Something broke")
        assert not handle.is_active
        assert goal.error == "Something broke"

    def test_role_and_name_properties(self) -> None:
        node = SwarmNode(node_id="ceo", name="CEO", role=Role.CEO)
        handle = NodeHandle(node=node)
        assert handle.name == "CEO"
        assert handle.role == Role.CEO
        assert handle.node_id == "ceo"

    def test_model_property(self) -> None:
        node = SwarmNode(node_id="test", name="Test", role=Role.WORKER, model="gpt-4o")
        handle = NodeHandle(node=node)
        assert handle.model == "gpt-4o"

    def test_handle_with_context(self) -> None:
        node = SwarmNode(node_id="test", name="Test", role=Role.WORKER)
        handle = NodeHandle(node=node, context={"key": "value"})
        assert handle.context["key"] == "value"

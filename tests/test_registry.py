"""Tests for the swarm registry."""

import pytest

from src.core.types import Role, SwarmNode
from src.swarm.registry import SwarmRegistry
from src.core.errors import RegistryError


@pytest.fixture
def populated_registry() -> SwarmRegistry:
    reg = SwarmRegistry()
    reg.register(SwarmNode(node_id="ceo", name="CEO", role=Role.CEO, child_ids=["pm", "eng"]))
    reg.register(SwarmNode(node_id="pm", name="PM", role=Role.MANAGER, parent_id="ceo", child_ids=["w1"]))
    reg.register(SwarmNode(node_id="eng", name="Eng", role=Role.MANAGER, parent_id="ceo", child_ids=["w2"]))
    reg.register(SwarmNode(node_id="w1", name="Worker1", role=Role.WORKER, parent_id="pm"))
    reg.register(SwarmNode(node_id="w2", name="Worker2", role=Role.WORKER, parent_id="eng"))
    return reg


class TestSwarmRegistry:
    def test_get_node(self, populated_registry: SwarmRegistry) -> None:
        node = populated_registry.get("ceo")
        assert node.name == "CEO"

    def test_get_missing_node(self, populated_registry: SwarmRegistry) -> None:
        with pytest.raises(RegistryError, match="not found"):
            populated_registry.get("nonexistent")

    def test_find_node(self, populated_registry: SwarmRegistry) -> None:
        node = populated_registry.find("ceo")
        assert node is not None
        assert populated_registry.find("nonexistent") is None

    def test_get_by_role(self, populated_registry: SwarmRegistry) -> None:
        workers = populated_registry.get_by_role(Role.WORKER)
        assert len(workers) == 2
        managers = populated_registry.get_by_role(Role.MANAGER)
        assert len(managers) == 2

    def test_get_children(self, populated_registry: SwarmRegistry) -> None:
        children = populated_registry.get_children("ceo")
        assert len(children) == 2
        assert {c.node_id for c in children} == {"pm", "eng"}

    def test_get_descendants(self, populated_registry: SwarmRegistry) -> None:
        descendants = populated_registry.get_descendants("ceo")
        assert len(descendants) == 4  # pm, eng, w1, w2

        pm_descendants = populated_registry.get_descendants("pm")
        assert len(pm_descendants) == 1  # w1 only

    def test_get_ancestors(self, populated_registry: SwarmRegistry) -> None:
        ancestors = populated_registry.get_ancestors("w1")
        assert len(ancestors) == 2  # pm, ceo
        assert ancestors[0].node_id == "pm"

        ceo_ancestors = populated_registry.get_ancestors("ceo")
        assert len(ceo_ancestors) == 0

    def test_get_leaves(self, populated_registry: SwarmRegistry) -> None:
        leaves = populated_registry.get_leaves()
        assert len(leaves) == 2
        assert {n.node_id for n in leaves} == {"w1", "w2"}

    def test_get_root(self, populated_registry: SwarmRegistry) -> None:
        root = populated_registry.get_root()
        assert root.node_id == "ceo"

    def test_get_subtree(self, populated_registry: SwarmRegistry) -> None:
        subtree = populated_registry.get_subtree("pm")
        ids = {n.node_id for n in subtree}
        assert ids == {"pm", "w1"}

    def test_get_siblings(self, populated_registry: SwarmRegistry) -> None:
        siblings = populated_registry.get_siblings("pm")
        assert len(siblings) == 1
        assert siblings[0].node_id == "eng"

        ceo_siblings = populated_registry.get_siblings("ceo")
        assert len(ceo_siblings) == 0

    def test_size(self, populated_registry: SwarmRegistry) -> None:
        assert populated_registry.size == 5

    def test_empty_registry(self) -> None:
        reg = SwarmRegistry()
        assert reg.size == 0
        with pytest.raises(RegistryError, match="No root"):
            reg.get_root()

    def test_register_many(self) -> None:
        reg = SwarmRegistry()
        nodes = [
            SwarmNode(node_id="a", name="A", role=Role.CEO),
            SwarmNode(node_id="b", name="B", role=Role.WORKER, parent_id="a"),
        ]
        reg.register_many(nodes)
        assert reg.size == 2

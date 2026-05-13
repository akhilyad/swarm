"""Swarm registry for node lookups by ID, role, and tree position."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ..core.errors import RegistryError
from ..core.types import Role, SwarmNode


class SwarmRegistry:
    """Registry for all agent nodes in the swarm tree.

    Provides efficient lookups by node ID, role, and tree relationships
    (children, descendants, ancestors). Built once from config and used
    throughout the runtime for routing and queries.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, SwarmNode] = {}
        self._by_role: defaultdict[str, list[SwarmNode]] = defaultdict(list)
        self._by_parent: defaultdict[str, list[SwarmNode]] = defaultdict(list)

    def register(self, node: SwarmNode) -> None:
        """Register a single node in the registry."""
        self._nodes[node.node_id] = node
        self._by_role[node.role.value].append(node)
        if node.parent_id:
            self._by_parent[node.parent_id].append(node)

    def register_many(self, nodes: list[SwarmNode]) -> None:
        """Register multiple nodes at once."""
        for node in nodes:
            self.register(node)

    def get(self, node_id: str) -> SwarmNode:
        """Look up a node by its ID. Raises RegistryError if not found."""
        node = self._nodes.get(node_id)
        if node is None:
            raise RegistryError(f"Node '{node_id}' not found in registry")
        return node

    def find(self, node_id: str) -> SwarmNode | None:
        """Look up a node by ID, returning None if not found."""
        return self._nodes.get(node_id)

    def get_by_role(self, role: Role) -> list[SwarmNode]:
        """Get all nodes with a specific role."""
        return list(self._by_role.get(role.value, []))

    def get_children(self, node_id: str) -> list[SwarmNode]:
        """Get direct children of a node."""
        return list(self._by_parent.get(node_id, []))

    def get_descendants(self, node_id: str) -> list[SwarmNode]:
        """Get all descendants of a node (recursive)."""
        result: list[SwarmNode] = []
        stack = list(self._by_parent.get(node_id, []))
        while stack:
            node = stack.pop()
            result.append(node)
            stack.extend(self._by_parent.get(node.node_id, []))
        return result

    def get_ancestors(self, node_id: str) -> list[SwarmNode]:
        """Get all ancestors of a node (parent, grandparent, ...)."""
        result: list[SwarmNode] = []
        node = self._nodes.get(node_id)
        while node and node.parent_id:
            parent = self._nodes.get(node.parent_id)
            if parent:
                result.append(parent)
                node = parent
            else:
                break
        return result

    def get_leaves(self) -> list[SwarmNode]:
        """Get all leaf nodes (WORKERs with no children)."""
        return [n for n in self._nodes.values() if n.is_leaf and n.role == Role.WORKER]

    def get_root(self) -> SwarmNode:
        """Get the root node (CEO). Raises RegistryError if not found."""
        for node in self._nodes.values():
            if node.is_root:
                return node
        raise RegistryError("No root node found in registry")

    def get_subtree(self, node_id: str) -> list[SwarmNode]:
        """Get a node and all its descendants."""
        node = self.get(node_id)
        return [node] + self.get_descendants(node_id)

    def get_siblings(self, node_id: str) -> list[SwarmNode]:
        """Get siblings of a node (same parent)."""
        node = self.get(node_id)
        if not node.parent_id:
            return []
        return [n for n in self._by_parent.get(node.parent_id, []) if n.node_id != node_id]

    @property
    def size(self) -> int:
        return len(self._nodes)

    @property
    def all_nodes(self) -> list[SwarmNode]:
        return list(self._nodes.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "size": self.size,
            "root": self.get_root().model_dump() if self._nodes else None,
            "nodes": {n.node_id: n.model_dump() for n in self._nodes.values()},
        }

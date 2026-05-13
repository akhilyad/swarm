"""Build the swarm tree from configuration."""

from __future__ import annotations

from ..core.config import SwarmConfig
from ..core.node import NodeHandle
from ..core.types import SwarmNode
from .registry import SwarmRegistry


def build_swarm(config: SwarmConfig) -> SwarmRegistry:
    """Build a SwarmRegistry from a loaded SwarmConfig.

    Creates the full node tree, validates all relationships,
    and returns a ready-to-use registry.
    """
    registry = SwarmRegistry()
    for node in config.agents.values():
        registry.register(node)
    return registry


def build_handles(registry: SwarmRegistry) -> dict[str, NodeHandle]:
    """Create NodeHandle wrappers for all nodes in the registry.

    Returns a dict mapping node_id -> NodeHandle with initial inactive state.
    """
    return {
        n.node_id: NodeHandle(node=registry.get(n.node_id))
        for n in registry.all_nodes
    }


def build_from_config(config: SwarmConfig) -> tuple[SwarmRegistry, dict[str, NodeHandle]]:
    """Convenience: build both registry and handles from config."""
    registry = build_swarm(config)
    handles = build_handles(registry)
    return registry, handles

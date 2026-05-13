"""YAML configuration loader with validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .errors import ConfigError
from .types import Role, SwarmNode


class SwarmConfig:
    """Loaded and validated swarm configuration."""

    def __init__(
        self,
        name: str,
        model: str,
        budget_usd: float | None = None,
        agents: dict[str, SwarmNode] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self.model = model
        self.budget_usd = budget_usd
        self.agents = agents or {}
        self.metadata = metadata or {}

    @property
    def root_agent(self) -> SwarmNode | None:
        """Return the CEO (root) agent."""
        for agent in self.agents.values():
            if agent.is_root:
                return agent
        return None

    def get_agent(self, node_id: str) -> SwarmNode:
        agent = self.agents.get(node_id)
        if agent is None:
            raise ConfigError(f"Agent '{node_id}' not found in config")
        return agent

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "model": self.model,
            "budget_usd": self.budget_usd,
            "agents": {k: v.to_dict() for k, v in self.agents.items()},
        }


def load_config(path: str | Path) -> SwarmConfig:
    """Load and validate a swarm YAML configuration."""
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ConfigError("Config must be a YAML mapping")

    name = raw.get("name", "Unnamed Swarm")
    model = raw.get("model", "gpt-4o")
    budget_usd = raw.get("budget_usd")
    raw_agents = raw.get("agents", {})

    if not raw_agents:
        raise ConfigError("Config must define at least one agent under 'agents'")

    agents: dict[str, SwarmNode] = {}
    parent_to_children: dict[str, list[str]] = {}

    # First pass: create all nodes
    for node_id, agent_data in raw_agents.items():
        if not isinstance(agent_data, dict):
            raise ConfigError(f"Agent '{node_id}' must be a mapping")

        role_str = agent_data.get("role", "WORKER")
        try:
            role = Role(role_str)
        except ValueError:
            raise ConfigError(f"Invalid role '{role_str}' for agent '{node_id}'")

        node = SwarmNode(
            node_id=node_id,
            name=agent_data.get("name", node_id),
            role=role,
            parent_id=None,  # Set in second pass
            child_ids=agent_data.get("children", []),
            model=agent_data.get("model"),
            system_prompt_override=agent_data.get("system_prompt_override"),
            sub_swarm_config=agent_data.get("sub_swarm_config"),
            metadata=agent_data.get("metadata", {}),
        )
        agents[node_id] = node

        # Track parent-child relationships
        parent_id = agent_data.get("parent")
        if parent_id:
            parent_to_children.setdefault(parent_id, []).append(node_id)
            node.parent_id = parent_id

    # Validate parent references
    for parent_id in parent_to_children:
        if parent_id not in agents:
            raise ConfigError(f"Parent agent '{parent_id}' not found for child")

    # Validate exactly one root (CEO)
    roots = [n for n in agents.values() if n.is_root]
    if len(roots) != 1:
        raise ConfigError(f"Config must have exactly one root agent (CEO), found {len(roots)}")

    # Validate CEO role for root
    if roots[0].role != Role.CEO:
        raise ConfigError(f"Root agent '{roots[0].node_id}' must have role CEO, got {roots[0].role.value}")

    # Validate children references
    for node in agents.values():
        for child_id in node.child_ids:
            if child_id not in agents:
                raise ConfigError(f"Agent '{node.node_id}' references unknown child '{child_id}'")

    return SwarmConfig(name=name, model=model, budget_usd=budget_usd, agents=agents)

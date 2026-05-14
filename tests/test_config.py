"""Tests for YAML config loading and validation."""

from pathlib import Path

import pytest
import yaml

from src.core.config import load_config
from src.core.errors import ConfigError
from src.core.types import Role


@pytest.fixture
def valid_config_path(tmp_path: Path) -> Path:
    """Create a valid config file for testing."""
    data = {
        "name": "Test Swarm",
        "model": "gpt-4o",
        "budget_usd": 50.0,
        "agents": {
            "ceo": {
                "name": "CEO",
                "role": "CEO",
                "children": ["manager"],
            },
            "manager": {
                "name": "Manager",
                "role": "MANAGER",
                "parent": "ceo",
                "children": ["worker"],
            },
            "worker": {
                "name": "Worker",
                "role": "WORKER",
                "parent": "manager",
            },
        },
    }
    path = tmp_path / "valid.yaml"
    with open(path, "w") as f:
        yaml.dump(data, f)
    return path


class TestLoadConfig:
    def test_load_valid_config(self, valid_config_path: Path) -> None:
        config = load_config(valid_config_path)
        assert config.name == "Test Swarm"
        assert config.model == "gpt-4o"
        assert config.budget_usd == 50.0
        assert len(config.agents) == 3

    def test_root_agent_is_ceo(self, valid_config_path: Path) -> None:
        config = load_config(valid_config_path)
        root = config.root_agent
        assert root is not None
        assert root.node_id == "ceo"
        assert root.role == Role.CEO

    def test_missing_config_file(self) -> None:
        with pytest.raises(ConfigError, match="not found"):
            load_config(Path("/nonexistent/config.yaml"))

    def test_empty_agents(self, tmp_path: Path) -> None:
        data = {"name": "Empty", "model": "gpt-4o", "agents": {}}
        path = tmp_path / "empty.yaml"
        with open(path, "w") as f:
            yaml.dump(data, f)
        with pytest.raises(ConfigError, match="at least one agent"):
            load_config(path)

    def test_no_root(self, tmp_path: Path) -> None:
        data = {
            "name": "No Root",
            "agents": {
                "a": {"name": "A", "role": "WORKER"},
                "b": {"name": "B", "role": "WORKER", "parent": "a"},
            },
        }
        path = tmp_path / "no_root.yaml"
        with open(path, "w") as f:
            yaml.dump(data, f)
        with pytest.raises(ConfigError, match="must have role CEO"):
            load_config(path)

    def test_multiple_roots(self, tmp_path: Path) -> None:
        data = {
            "name": "Multi Root",
            "agents": {
                "ceo": {"name": "CEO", "role": "CEO"},
                "another": {"name": "Another", "role": "CEO"},
            },
        }
        path = tmp_path / "multi_root.yaml"
        with open(path, "w") as f:
            yaml.dump(data, f)
        with pytest.raises(ConfigError, match="exactly one root"):
            load_config(path)

    def test_invalid_role(self, tmp_path: Path) -> None:
        data = {
            "name": "Bad Role",
            "agents": {
                "ceo": {"name": "CEO", "role": "CEO"},
                "bad": {"name": "Bad", "role": "INVALID", "parent": "ceo"},
            },
        }
        path = tmp_path / "bad_role.yaml"
        with open(path, "w") as f:
            yaml.dump(data, f)
        with pytest.raises(ConfigError, match="Invalid role"):
            load_config(path)

    def test_bad_parent_ref(self, tmp_path: Path) -> None:
        data = {
            "name": "Bad Parent",
            "agents": {
                "ceo": {"name": "CEO", "role": "CEO"},
                "orphan": {"name": "Orphan", "role": "WORKER", "parent": "nonexistent"},
            },
        }
        path = tmp_path / "bad_parent.yaml"
        with open(path, "w") as f:
            yaml.dump(data, f)
        with pytest.raises(ConfigError, match="not found"):
            load_config(path)

    def test_root_must_be_ceo(self, tmp_path: Path) -> None:
        data = {
            "name": "Wrong Root",
            "agents": {
                "worker": {"name": "Worker", "role": "WORKER"},
            },
        }
        path = tmp_path / "wrong_root.yaml"
        with open(path, "w") as f:
            yaml.dump(data, f)
        with pytest.raises(ConfigError, match="must have role CEO"):
            load_config(path)

    def test_get_agent(self, valid_config_path: Path) -> None:
        config = load_config(valid_config_path)
        agent = config.get_agent("ceo")
        assert agent.name == "CEO"

    def test_get_agent_not_found(self, valid_config_path: Path) -> None:
        config = load_config(valid_config_path)
        with pytest.raises(ConfigError, match="not found"):
            config.get_agent("nonexistent")

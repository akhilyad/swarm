"""Abstract vector store interface for agent memory."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..core.types import MemoryEntry


class MemoryStore(ABC):
    """Abstract base for vector memory backends."""

    @abstractmethod
    async def store(self, entry: MemoryEntry) -> str:
        """Store a memory entry and return its ID."""

    @abstractmethod
    async def search(
        self,
        agent_id: str,
        query: str,
        n_results: int = 5,
    ) -> list[MemoryEntry]:
        """Search memories by semantic similarity."""

    @abstractmethod
    async def get_recent(
        self,
        agent_id: str,
        n: int = 10,
    ) -> list[MemoryEntry]:
        """Get the most recent memory entries for an agent."""

    @abstractmethod
    async def delete(self, entry_id: str) -> None:
        """Delete a memory entry."""

    @abstractmethod
    async def clear(self, agent_id: str) -> None:
        """Clear all memory entries for an agent."""

    @abstractmethod
    async def store_many(self, entries: list[MemoryEntry]) -> list[str]:
        """Store multiple entries at once."""

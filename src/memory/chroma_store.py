"""ChromaDB-backed memory store implementation.

Supports both local (PersistentClient) and centralized (HttpClient)
deployment. Defaults to HttpClient pointed at ``CHROMA_HOST`` /
``CHROMA_PORT`` env vars for distributed setups.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from ..core.errors import MemoryError
from ..core.types import MemoryEntry
from .store import MemoryStore

logger = logging.getLogger(__name__)


class ChromaMemoryStore(MemoryStore):
    """Memory store backed by ChromaDB — centralized or local."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        persist_directory: str | Path | None = None,
    ) -> None:
        """Initialize the ChromaDB memory store.

        Defaults to centralized ``HttpClient`` mode pointed at
        ``CHROMA_HOST`` / ``CHROMA_PORT`` env vars (or ``localhost:8000``).
        Pass ``persist_directory`` to use a local ``PersistentClient``
        instead.
        """
        self._host = host or os.environ.get("CHROMA_HOST", "localhost")
        self._port = port or int(os.environ["CHROMA_PORT"]) if "CHROMA_PORT" in os.environ else 8000
        self.persist_directory = Path(persist_directory) if persist_directory else None
        self._client = None
        self._collection = None
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Lazy-init ChromaDB client and collection."""
        if self._initialized:
            return

        try:
            import chromadb

            if self.persist_directory is not None:
                # Local mode — persist to disk
                self.persist_directory.mkdir(parents=True, exist_ok=True)
                self._client = chromadb.PersistentClient(
                    path=str(self.persist_directory),
                )
                logger.info(
                    "ChromaMemoryStore using local PersistentClient at %s",
                    self.persist_directory,
                )
            else:
                # Centralized mode — connect to a remote ChromaDB server
                self._client = chromadb.HttpClient(
                    host=self._host,
                    port=self._port,
                )
                logger.info(
                    "ChromaMemoryStore connected to remote ChromaDB at %s:%s",
                    self._host, self._port,
                )

            self._collection = self._client.get_or_create_collection(
                name="swarm_memories",
                metadata={"hnsw:space": "cosine"},
            )
            self._initialized = True
        except ImportError:
            raise MemoryError(
                "ChromaDB is not installed. Run: pip install chromadb"
            )
        except Exception as e:
            raise MemoryError(f"Failed to initialize ChromaDB: {e}")

    async def store(self, entry: MemoryEntry) -> str:
        """Store a memory entry in ChromaDB."""
        await self._ensure_initialized()
        entry_id = entry.entry_id

        try:
            await asyncio.to_thread(
                self._collection.add,
                ids=[entry_id],
                documents=[entry.content],
                metadatas=[
                    {
                        "agent_id": entry.agent_id,
                        "entry_type": entry.entry_type,
                        "timestamp": entry.timestamp,
                        **(entry.metadata or {}),
                    }
                ],
            )
            return entry_id
        except Exception as e:
            raise MemoryError(f"Failed to store memory entry: {e}")

    async def store_many(self, entries: list[MemoryEntry]) -> list[str]:
        """Store multiple entries at once."""
        await self._ensure_initialized()

        ids = []
        documents = []
        metadatas = []
        for e in entries:
            ids.append(e.entry_id)
            documents.append(e.content)
            metadatas.append(
                {
                    "agent_id": e.agent_id,
                    "entry_type": e.entry_type,
                    "timestamp": e.timestamp,
                    **(e.metadata or {}),
                }
            )

        try:
            await asyncio.to_thread(
                self._collection.add, ids=ids, documents=documents, metadatas=metadatas
            )
            return ids
        except Exception as e:
            raise MemoryError(f"Failed to store memory entries: {e}")

    async def search(
        self,
        agent_id: str,
        query: str,
        n_results: int = 5,
    ) -> list[MemoryEntry]:
        """Search memories by semantic similarity, filtered by agent."""
        await self._ensure_initialized()

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=n_results,
                where={"agent_id": agent_id},
            )

            entries = []
            if results["ids"] and results["documents"]:
                for i in range(len(results["ids"][0])):
                    entry = MemoryEntry(
                        entry_id=results["ids"][0][i],
                        agent_id=agent_id,
                        content=results["documents"][0][i],
                        metadata=(
                            results["metadatas"][0][i]
                            if results.get("metadatas")
                            else {}
                        ),
                    )
                    entries.append(entry)
            return entries
        except Exception as e:
            raise MemoryError(f"Failed to search memory: {e}")

    async def get_recent(
        self,
        agent_id: str,
        n: int = 10,
    ) -> list[MemoryEntry]:
        """Get recent entries for an agent (by timestamp metadata)."""
        await self._ensure_initialized()

        try:
            results = self._collection.get(
                where={"agent_id": agent_id},
                limit=n,
            )

            entries = []
            if results["ids"]:
                for i in range(len(results["ids"])):
                    entry = MemoryEntry(
                        entry_id=results["ids"][i],
                        agent_id=agent_id,
                        content=results["documents"][i],
                        metadata=(
                            results["metadatas"][i]
                            if results.get("metadatas")
                            else {}
                        ),
                    )
                    entries.append(entry)
            return entries
        except Exception as e:
            raise MemoryError(f"Failed to get recent memory: {e}")

    async def delete(self, entry_id: str) -> None:
        """Delete a single memory entry."""
        await self._ensure_initialized()
        try:
            self._collection.delete(ids=[entry_id])
        except Exception as e:
            raise MemoryError(f"Failed to delete memory entry: {e}")

    async def clear(self, agent_id: str) -> None:
        """Clear all entries for an agent."""
        await self._ensure_initialized()
        try:
            results = self._collection.get(where={"agent_id": agent_id})
            if results["ids"]:
                self._collection.delete(ids=results["ids"])
        except Exception as e:
            raise MemoryError(f"Failed to clear memory for agent {agent_id}: {e}")

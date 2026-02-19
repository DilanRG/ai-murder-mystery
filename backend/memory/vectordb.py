"""
ChromaDB vector database wrapper for NPC memory and knowledge retrieval.
"""
import logging
from typing import Any, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

logger = logging.getLogger(__name__)


class VectorDB:
    """
    ChromaDB wrapper providing per-NPC knowledge isolation.

    Each NPC gets their own collection so memory retrieval
    is automatically scoped to what that character knows.
    """

    def __init__(self, persist_dir: str = "") -> None:
        """
        Initialize ChromaDB.

        Args:
            persist_dir: Directory for persistent storage.
                         Empty string = in-memory only.
        """
        if persist_dir:
            self._client = chromadb.PersistentClient(
                path=persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        else:
            self._client = chromadb.EphemeralClient(
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        self._collections: dict[str, chromadb.Collection] = {}
        logger.info(
            "ChromaDB initialized (%s)",
            "persistent" if persist_dir else "in-memory",
        )

    def get_or_create_collection(self, name: str) -> chromadb.Collection:
        """Get or create a named collection."""
        safe_name = name.lower().replace(" ", "_").replace("'", "")[:63]
        if safe_name not in self._collections:
            self._collections[safe_name] = self._client.get_or_create_collection(
                name=safe_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collections[safe_name]

    def add_documents(
        self,
        collection_name: str,
        documents: list[str],
        ids: list[str],
        metadatas: Optional[list[dict[str, Any]]] = None,
    ) -> None:
        """Add documents to a collection."""
        collection = self.get_or_create_collection(collection_name)
        collection.add(
            documents=documents,
            ids=ids,
            metadatas=metadatas,
        )
        logger.debug(
            "Added %d docs to collection '%s'",
            len(documents), collection_name,
        )

    def query(
        self,
        collection_name: str,
        query_text: str,
        n_results: int = 5,
        where: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """
        Query a collection for similar documents.

        Returns:
            List of dicts with 'document', 'id', 'distance', and 'metadata'.
        """
        collection = self.get_or_create_collection(collection_name)

        if collection.count() == 0:
            return []

        results = collection.query(
            query_texts=[query_text],
            n_results=min(n_results, collection.count()),
            where=where,
        )

        parsed: list[dict[str, Any]] = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                parsed.append({
                    "document": doc,
                    "id": results["ids"][0][i] if results["ids"] else "",
                    "distance": results["distances"][0][i] if results["distances"] else 0.0,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                })

        return parsed

    def initialize_npc_memory(
        self,
        npc_name: str,
        base_knowledge: list[str],
        secrets: list[str],
    ) -> None:
        """
        Initialize an NPC's memory collection with their base knowledge.

        Args:
            npc_name: The NPC's name (used as collection name).
            base_knowledge: Facts the NPC knows from the start.
            secrets: The NPC's personal secrets.
        """
        docs: list[str] = []
        ids: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for i, fact in enumerate(base_knowledge):
            docs.append(fact)
            ids.append(f"{npc_name}_base_{i}")
            metadatas.append({"type": "base_knowledge", "turn": 0})

        for i, secret in enumerate(secrets):
            docs.append(secret)
            ids.append(f"{npc_name}_secret_{i}")
            metadatas.append({"type": "secret", "turn": 0})

        if docs:
            self.add_documents(npc_name, docs, ids, metadatas)
            logger.info("Initialized memory for %s: %d items", npc_name, len(docs))

    def add_event_memory(
        self,
        npc_name: str,
        event: str,
        turn: int,
        event_type: str = "witnessed",
    ) -> None:
        """Add an event to an NPC's memory."""
        self.add_documents(
            collection_name=npc_name,
            documents=[event],
            ids=[f"{npc_name}_event_t{turn}_{event_type}"],
            metadatas=[{"type": event_type, "turn": turn}],
        )

    def recall_relevant(
        self,
        npc_name: str,
        context: str,
        n_results: int = 5,
    ) -> list[str]:
        """
        Retrieve NPC memories relevant to a given context.

        Args:
            npc_name: The NPC whose memory to search.
            context: The current conversation/situation context.
            n_results: Max number of memories to retrieve.

        Returns:
            List of relevant memory strings.
        """
        results = self.query(npc_name, context, n_results)
        return [r["document"] for r in results]

    def initialize_world_facts(
        self,
        scenario_title: str,
        setting: str,
        locations: list[str],
        public_facts: list[str],
    ) -> None:
        """Initialize the shared world facts collection."""
        docs = [
            f"Scenario: {scenario_title}",
            f"Setting: {setting}",
        ] + [f"Location: {loc}" for loc in locations] + public_facts

        ids = [f"world_{i}" for i in range(len(docs))]
        metadatas = [{"type": "world_fact", "turn": 0}] * len(docs)

        self.add_documents("world_facts", docs, ids, metadatas)
        logger.info("Initialized %d world facts", len(docs))

    def clear_all(self) -> None:
        """Clear all collections (for new game)."""
        for name in list(self._collections.keys()):
            try:
                self._client.delete_collection(name)
            except Exception:
                pass
        self._collections.clear()
        logger.info("All vector DB collections cleared")

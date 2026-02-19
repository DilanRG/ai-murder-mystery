"""
Context window management and conversation history.
Integrates with VectorDB for semantic memory retrieval.
"""
import logging
from dataclasses import dataclass, field
from typing import Optional

from memory.vectordb import VectorDB
from llm.prompt_builder import estimate_tokens

logger = logging.getLogger(__name__)


@dataclass
class ConversationEntry:
    """A single entry in a conversation."""
    role: str  # "user", "assistant", "system"
    content: str
    turn: int = 0
    npc_name: str = ""


class ContextManager:
    """
    Manages conversation histories and context window budgets.
    Integrates semantic memory retrieval from VectorDB.
    """

    def __init__(
        self,
        vector_db: VectorDB,
        max_context_tokens: int = 8192,
        max_response_tokens: int = 1024,
    ) -> None:
        self.vector_db = vector_db
        self.max_context_tokens = max_context_tokens
        self.max_response_tokens = max_response_tokens

        # Per-NPC conversation histories
        self._histories: dict[str, list[ConversationEntry]] = {}

    def add_message(
        self,
        npc_name: str,
        role: str,
        content: str,
        turn: int = 0,
    ) -> None:
        """Add a message to an NPC's conversation history."""
        if npc_name not in self._histories:
            self._histories[npc_name] = []

        self._histories[npc_name].append(
            ConversationEntry(role=role, content=content, turn=turn, npc_name=npc_name)
        )

        # Also store in vector DB for long-term retrieval
        self.vector_db.add_event_memory(
            npc_name=npc_name,
            event=f"[{role}] {content[:200]}",
            turn=turn,
            event_type="conversation",
        )

    def get_history(self, npc_name: str) -> list[dict[str, str]]:
        """Get conversation history as message dicts for the LLM."""
        entries = self._histories.get(npc_name, [])
        return [{"role": e.role, "content": e.content} for e in entries]

    def get_context_with_memory(
        self,
        npc_name: str,
        current_situation: str,
        recent_count: int = 10,
        memory_count: int = 5,
    ) -> tuple[list[dict[str, str]], str]:
        """
        Build context with both recent history and semantic memory.

        Returns:
            Tuple of (recent_messages, memory_context_string).
        """
        # Recent conversation entries
        entries = self._histories.get(npc_name, [])
        recent = entries[-recent_count:]
        recent_messages = [{"role": e.role, "content": e.content} for e in recent]

        # Semantic memory retrieval
        memories = self.vector_db.recall_relevant(
            npc_name=npc_name,
            context=current_situation,
            n_results=memory_count,
        )

        # Also get world facts
        world_memories = self.vector_db.recall_relevant(
            npc_name="world_facts",
            context=current_situation,
            n_results=3,
        )

        memory_parts: list[str] = []
        if memories:
            memory_parts.append("Relevant memories:\n" + "\n".join(f"- {m}" for m in memories))
        if world_memories:
            memory_parts.append("World context:\n" + "\n".join(f"- {m}" for m in world_memories))

        memory_context = "\n\n".join(memory_parts)

        return recent_messages, memory_context

    def calculate_budget(self, system_tokens: int = 0) -> int:
        """Calculate remaining token budget for conversation history."""
        return self.max_context_tokens - self.max_response_tokens - system_tokens

    def clear_npc_history(self, npc_name: str) -> None:
        """Clear conversation history for an NPC."""
        self._histories.pop(npc_name, None)

    def clear_all(self) -> None:
        """Clear all conversation histories."""
        self._histories.clear()

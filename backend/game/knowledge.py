"""
Per-character knowledge partitioning.
Controls what information each character has access to.
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from game.scenario import NPCKnowledge, GameScenario
from game.characters import Character, CharacterRole

logger = logging.getLogger(__name__)


@dataclass
class CharacterKnowledgeState:
    """Runtime knowledge state for a single character."""
    character_name: str
    role: CharacterRole = CharacterRole.SUSPECT

    # From scenario generation
    alibi: str = ""
    true_whereabouts: str = ""
    known_clue_ids: list[str] = field(default_factory=list)
    secrets: list[str] = field(default_factory=list)
    attitude: str = ""
    suspicions: str = ""

    # Accumulated during gameplay
    witnessed_events: list[str] = field(default_factory=list)
    conversations_had: list[str] = field(default_factory=list)
    information_received: list[str] = field(default_factory=list)

    def knows_about(self, topic: str) -> bool:
        """Check if this character has knowledge about a topic."""
        all_knowledge = (
            self.secrets
            + self.witnessed_events
            + self.information_received
            + [self.alibi, self.true_whereabouts, self.attitude, self.suspicions]
        )
        topic_lower = topic.lower()
        return any(topic_lower in k.lower() for k in all_knowledge if k)

    def get_prompt_context(self, is_killer: bool = False) -> str:
        """
        Build a knowledge context string for this character's LLM prompt.

        Args:
            is_killer: Whether this character is the killer (gets extra info).
        """
        lines = [f"You are {self.character_name}."]
        lines.append(f"Your alibi: {self.alibi}")

        if is_killer:
            lines.append(f"SECRET — You are the KILLER. Your true whereabouts: {self.true_whereabouts}")
            lines.append("You must deflect suspicion while appearing cooperative.")
        else:
            if self.true_whereabouts and self.true_whereabouts != self.alibi:
                lines.append(f"(Privately, you were actually: {self.true_whereabouts})")

        if self.secrets:
            lines.append(f"Your secrets (do NOT reveal unless pressured): {'; '.join(self.secrets)}")

        if self.attitude:
            lines.append(f"Your attitude toward the investigation: {self.attitude}")

        if self.suspicions:
            lines.append(f"You suspect: {self.suspicions}")

        if self.witnessed_events:
            lines.append(f"You witnessed: {'; '.join(self.witnessed_events[-5:])}")

        if self.information_received:
            lines.append(f"You've learned: {'; '.join(self.information_received[-5:])}")

        return "\n".join(lines)


class KnowledgeManager:
    """Manages knowledge partitioning across all characters."""

    def __init__(self) -> None:
        self._states: dict[str, CharacterKnowledgeState] = {}
        self._killer_name: str = ""

    def initialize_from_scenario(
        self,
        scenario: GameScenario,
        characters: list[Character],
    ) -> None:
        """Set up knowledge states from the generated scenario."""
        self._killer_name = scenario.murder.killer

        for char in characters:
            if char.is_player:
                continue

            npc_knowledge = scenario.npc_knowledge.get(char.name)
            if npc_knowledge:
                state = CharacterKnowledgeState(
                    character_name=char.name,
                    role=char.assigned_role or CharacterRole.SUSPECT,
                    alibi=npc_knowledge.alibi,
                    true_whereabouts=npc_knowledge.true_whereabouts,
                    known_clue_ids=list(npc_knowledge.known_clues),
                    secrets=list(npc_knowledge.secrets),
                    attitude=npc_knowledge.attitude,
                    suspicions=npc_knowledge.suspicions,
                )
            else:
                state = CharacterKnowledgeState(
                    character_name=char.name,
                    role=char.assigned_role or CharacterRole.SUSPECT,
                )

            self._states[char.name] = state
            logger.debug("Initialized knowledge for %s", char.name)

        logger.info("Knowledge initialized for %d characters", len(self._states))

    def get_state(self, char_name: str) -> Optional[CharacterKnowledgeState]:
        """Get a character's knowledge state."""
        return self._states.get(char_name)

    def add_witnessed_event(self, char_name: str, event: str) -> None:
        """Record that a character witnessed an event."""
        state = self._states.get(char_name)
        if state:
            state.witnessed_events.append(event)

    def add_information(self, char_name: str, info: str) -> None:
        """Add information that a character learned."""
        state = self._states.get(char_name)
        if state:
            state.information_received.append(info)

    def record_conversation(self, char_name: str, with_whom: str, summary: str) -> None:
        """Record that a conversation took place."""
        state = self._states.get(char_name)
        if state:
            state.conversations_had.append(f"Spoke with {with_whom}: {summary}")

    def is_killer(self, char_name: str) -> bool:
        """Check if a character is the killer."""
        return char_name == self._killer_name

    def get_npc_prompt_context(self, char_name: str) -> str:
        """Get the knowledge context for building an NPC's prompt."""
        state = self._states.get(char_name)
        if not state:
            return ""
        return state.get_prompt_context(is_killer=self.is_killer(char_name))

    def get_player_visible_info(
        self,
        player_role: CharacterRole,
    ) -> dict[str, Any]:
        """
        Get information visible to the player based on their role.

        Detective: sees discovered clues, NPC statements, own observations
        Killer: sees the same + knows who the killer is (themselves)
        """
        info: dict[str, Any] = {
            "role": player_role.value,
            "known_alibis": {},
            "known_suspicions": {},
        }

        for name, state in self._states.items():
            # Player only sees alibis they've been told (via conversations)
            if state.conversations_had:
                info["known_alibis"][name] = state.alibi

        if player_role == CharacterRole.KILLER:
            info["you_are_the_killer"] = True
            info["your_mission"] = "Avoid detection. Deflect suspicion onto others."

        return info

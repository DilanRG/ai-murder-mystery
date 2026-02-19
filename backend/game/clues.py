"""
Clue and hint management system.
Tracks clue discovery, difficulty tiers, and reveal conditions.
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from game.scenario import ScenarioClue

logger = logging.getLogger(__name__)


class ClueDifficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class ClueType(str, Enum):
    PHYSICAL = "physical"        # Found at a location
    TESTIMONY = "testimony"      # Obtained from an NPC
    DOCUMENT = "document"        # Written evidence
    OBSERVATION = "observation"  # Something noticed by the player


@dataclass
class ClueState:
    """Runtime state of a clue during gameplay."""
    clue: ScenarioClue
    discovered: bool = False
    discovered_by: str = ""  # Who found it
    discovered_at_turn: int = 0
    notes: str = ""  # Player-added notes

    @property
    def id(self) -> str:
        return self.clue.id

    @property
    def difficulty(self) -> ClueDifficulty:
        return ClueDifficulty(self.clue.difficulty)


class ClueManager:
    """Manages all clues in a game session."""

    def __init__(self) -> None:
        self._clues: dict[str, ClueState] = {}

    def initialize_from_scenario(self, clues: list[ScenarioClue]) -> None:
        """Load clues from a generated scenario."""
        self._clues = {
            clue.id: ClueState(clue=clue)
            for clue in clues
        }
        logger.info("Initialized %d clues", len(self._clues))

    def discover_clue(
        self,
        clue_id: str,
        discovered_by: str,
        turn: int,
    ) -> Optional[ClueState]:
        """
        Mark a clue as discovered.

        Returns:
            The ClueState if newly discovered, None if already known or not found.
        """
        state = self._clues.get(clue_id)
        if state is None:
            logger.warning("Clue not found: %s", clue_id)
            return None

        if state.discovered:
            return None  # Already known

        state.discovered = True
        state.discovered_by = discovered_by
        state.discovered_at_turn = turn
        logger.info("Clue discovered: %s by %s", clue_id, discovered_by)
        return state

    def get_discovered_clues(self) -> list[ClueState]:
        """Get all discovered clues."""
        return [c for c in self._clues.values() if c.discovered]

    def get_undiscovered_clues(self) -> list[ClueState]:
        """Get all undiscovered clues."""
        return [c for c in self._clues.values() if not c.discovered]

    def get_clues_at_location(self, location_id: str) -> list[ClueState]:
        """Get undiscovered clues at a specific location."""
        return [
            c for c in self._clues.values()
            if c.clue.found_at == location_id and not c.discovered
        ]

    def get_clues_from_npc(self, npc_name: str) -> list[ClueState]:
        """Get clues that an NPC can reveal."""
        return [
            c for c in self._clues.values()
            if c.clue.found_at == npc_name and not c.discovered
        ]

    def get_clue(self, clue_id: str) -> Optional[ClueState]:
        """Get a specific clue by ID."""
        return self._clues.get(clue_id)

    @property
    def total_clues(self) -> int:
        return len(self._clues)

    @property
    def discovered_count(self) -> int:
        return len(self.get_discovered_clues())

    def get_progress_summary(self) -> str:
        """Get a summary of clue discovery progress."""
        discovered = self.get_discovered_clues()
        total = self.total_clues
        by_difficulty = {}
        for c in discovered:
            d = c.difficulty.value
            by_difficulty[d] = by_difficulty.get(d, 0) + 1

        parts = [f"Clues: {len(discovered)}/{total} discovered"]
        for diff in ["easy", "medium", "hard"]:
            if diff in by_difficulty:
                parts.append(f"  {diff}: {by_difficulty[diff]}")

        return " | ".join(parts)

"""
Character Card V2 loader and manager.
Handles loading characters from JSON, random selection, and player character creation.
"""
import json
import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from config.settings import CHARACTERS_DIR

logger = logging.getLogger(__name__)


class CharacterRole(str, Enum):
    """Roles a character can play in a game session."""
    DETECTIVE = "detective"
    KILLER = "killer"
    SUSPECT = "suspect"
    WITNESS = "witness"
    VICTIM = "victim"
    RED_HERRING = "red_herring"


@dataclass
class MurderMysteryExtensions:
    """Murder mystery-specific character extensions."""
    possible_roles: list[str] = field(default_factory=lambda: ["suspect", "witness"])
    default_location: str = ""
    social_connections: list[str] = field(default_factory=list)
    secrets: list[str] = field(default_factory=list)


@dataclass
class Character:
    """A Character Card V2 representation."""
    name: str
    description: str = ""
    personality: str = ""
    first_mes: str = ""
    mes_example: str = ""
    scenario: str = ""
    tags: list[str] = field(default_factory=list)
    creator_notes: str = ""
    system_prompt: str = ""
    post_history_instructions: str = ""
    alternate_greetings: list[str] = field(default_factory=list)
    extensions: dict[str, Any] = field(default_factory=dict)

    # Runtime state (not from the JSON file)
    assigned_role: Optional[CharacterRole] = None
    current_location: str = ""
    is_player: bool = False
    knowledge: list[str] = field(default_factory=list)

    @property
    def murder_mystery_ext(self) -> MurderMysteryExtensions:
        """Get murder mystery extensions, creating defaults if missing."""
        mm = self.extensions.get("murder_mystery", {})
        return MurderMysteryExtensions(**mm) if mm else MurderMysteryExtensions()

    def get_prompt_description(self) -> str:
        """Build a description suitable for injecting into LLM prompts."""
        parts = [f"Name: {self.name}"]
        if self.description:
            parts.append(f"Description: {self.description}")
        if self.personality:
            parts.append(f"Personality: {self.personality}")
        return "\n".join(parts)


def load_character(filepath: Path | str) -> Character:
    """
    Load a single character from a Character Card V2 JSON file.

    Args:
        filepath: Path to the character JSON file.

    Returns:
        Character instance.
    """
    filepath = Path(filepath)
    with open(filepath, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Handle both flat and nested "data" formats
    data = raw.get("data", raw)

    return Character(
        name=data.get("name", filepath.stem.replace("_", " ").title()),
        description=data.get("description", ""),
        personality=data.get("personality", ""),
        first_mes=data.get("first_mes", ""),
        mes_example=data.get("mes_example", ""),
        scenario=data.get("scenario", ""),
        tags=data.get("tags", []),
        creator_notes=data.get("creator_notes", ""),
        system_prompt=data.get("system_prompt", ""),
        post_history_instructions=data.get("post_history_instructions", ""),
        alternate_greetings=data.get("alternate_greetings", []),
        extensions=data.get("extensions", {}),
    )


def load_all_characters(directory: Path | str | None = None) -> list[Character]:
    """Load all characters from the characters directory."""
    directory = Path(directory) if directory else CHARACTERS_DIR
    if not directory.exists():
        logger.warning("Characters directory not found: %s", directory)
        return []

    characters = []
    for path in sorted(directory.glob("*.json")):
        try:
            characters.append(load_character(path))
            logger.debug("Loaded character: %s", characters[-1].name)
        except Exception as e:
            logger.error("Failed to load character %s: %s", path.name, e)

    logger.info("Loaded %d characters from %s", len(characters), directory)
    return characters


def select_npcs(
    pool: list[Character],
    count: int = 7,
    include_victim: bool = True,
) -> tuple[list[Character], Optional[Character]]:
    """
    Randomly select NPCs from the pool.

    Args:
        pool: Full character pool.
        count: Number of NPCs to select (excluding victim).
        include_victim: Whether to also select a victim.

    Returns:
        Tuple of (selected NPCs, victim or None).
    """
    if len(pool) < count + (1 if include_victim else 0):
        raise ValueError(
            f"Not enough characters in pool ({len(pool)}) "
            f"for {count} NPCs + {'1 victim' if include_victim else 'no victim'}"
        )

    selected = random.sample(pool, count + (1 if include_victim else 0))

    if include_victim:
        # Pick one that can be a victim
        victim_candidates = [
            c for c in selected
            if "victim" in c.murder_mystery_ext.possible_roles
        ]
        if victim_candidates:
            victim = random.choice(victim_candidates)
        else:
            victim = selected[-1]  # Fallback: last selected becomes victim

        selected.remove(victim)
        victim.assigned_role = CharacterRole.VICTIM
        return selected, victim
    else:
        return selected, None


def create_player_character(
    name: str = "The Player",
    description: str = "",
    role: CharacterRole = CharacterRole.DETECTIVE,
) -> Character:
    """
    Create a player character.

    Args:
        name: Player character name.
        description: Optional character description.
        role: DETECTIVE or KILLER.

    Returns:
        Character instance for the player.
    """
    return Character(
        name=name,
        description=description or f"A {role.value} investigating the mystery.",
        personality="Determined, observant",
        assigned_role=role,
        is_player=True,
    )

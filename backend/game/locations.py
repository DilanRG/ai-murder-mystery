"""
Location graph and NPC movement system.
Manages the spatial world — rooms, connections, and character positions.
"""
import logging
import random
from dataclasses import dataclass, field
from typing import Optional

from game.scenario import LocationDef

logger = logging.getLogger(__name__)


@dataclass
class Location:
    """A location in the game world with runtime state."""
    definition: LocationDef
    characters_present: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return self.definition.id

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def description(self) -> str:
        return self.definition.description

    @property
    def connected_to(self) -> list[str]:
        return self.definition.connected_to


class LocationManager:
    """Manages all locations and character positions."""

    def __init__(self) -> None:
        self._locations: dict[str, Location] = {}
        self._character_locations: dict[str, str] = {}  # char_name -> location_id

    def initialize_from_scenario(self, location_defs: list[LocationDef]) -> None:
        """Load locations from a generated scenario."""
        self._locations = {
            loc.id: Location(definition=loc)
            for loc in location_defs
        }
        logger.info("Initialized %d locations", len(self._locations))

    def place_character(self, char_name: str, location_id: str) -> None:
        """Place a character at a specific location."""
        # Remove from old location
        old_loc_id = self._character_locations.get(char_name)
        if old_loc_id and old_loc_id in self._locations:
            loc = self._locations[old_loc_id]
            if char_name in loc.characters_present:
                loc.characters_present.remove(char_name)

        # Add to new location
        if location_id in self._locations:
            self._locations[location_id].characters_present.append(char_name)
            self._character_locations[char_name] = location_id
        else:
            logger.warning("Location %s not found", location_id)

    def move_character(self, char_name: str, target_location_id: str) -> bool:
        """
        Move a character to an adjacent location.

        Returns:
            True if the move was successful, False if not connected.
        """
        current = self.get_character_location(char_name)
        if current is None:
            # Character not placed yet, place them
            self.place_character(char_name, target_location_id)
            return True

        current_loc = self._locations.get(current)
        if current_loc is None:
            return False

        if target_location_id not in current_loc.connected_to:
            logger.debug(
                "%s can't move from %s to %s (not connected)",
                char_name, current, target_location_id,
            )
            return False

        self.place_character(char_name, target_location_id)
        logger.debug("%s moved from %s to %s", char_name, current, target_location_id)
        return True

    def get_character_location(self, char_name: str) -> Optional[str]:
        """Get the location ID of a character."""
        return self._character_locations.get(char_name)

    def get_characters_at(self, location_id: str) -> list[str]:
        """Get all characters at a location."""
        loc = self._locations.get(location_id)
        return list(loc.characters_present) if loc else []

    def get_location(self, location_id: str) -> Optional[Location]:
        """Get a location by ID."""
        return self._locations.get(location_id)

    def get_all_locations(self) -> list[Location]:
        """Get all locations."""
        return list(self._locations.values())

    def get_adjacent_locations(self, location_id: str) -> list[Location]:
        """Get locations connected to the given location."""
        loc = self._locations.get(location_id)
        if not loc:
            return []
        return [
            self._locations[adj_id]
            for adj_id in loc.connected_to
            if adj_id in self._locations
        ]

    def get_random_adjacent(self, location_id: str) -> Optional[str]:
        """Get a random adjacent location ID."""
        adjacent = self.get_adjacent_locations(location_id)
        return random.choice(adjacent).id if adjacent else None

    def get_npcs_grouped_by_location(self, exclude: str = "") -> dict[str, list[str]]:
        """
        Group all characters by their current location.
        Used for the hybrid NPC resolution model.

        Args:
            exclude: Character name to exclude (usually the player).

        Returns:
            Dict of location_id -> list of character names.
        """
        groups: dict[str, list[str]] = {}
        for char_name, loc_id in self._character_locations.items():
            if char_name == exclude:
                continue
            if loc_id not in groups:
                groups[loc_id] = []
            groups[loc_id].append(char_name)
        return groups

    def get_location_summary(self) -> str:
        """Get a human-readable summary of all locations and occupants."""
        lines = []
        for loc in self._locations.values():
            chars = ", ".join(loc.characters_present) if loc.characters_present else "empty"
            lines.append(f"📍 {loc.name}: {chars}")
        return "\n".join(lines)

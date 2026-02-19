"""
Core game engine — orchestrates all subsystems and manages game state.
"""
import asyncio
import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from llm.api_client import LLMClientBase, get_client
from llm.prompt_builder import build_messages
from game.characters import (
    Character, CharacterRole,
    load_all_characters, select_npcs, create_player_character,
)
from game.scenario import GameScenario, generate_scenario
from game.clues import ClueManager
from game.locations import LocationManager
from game.knowledge import KnowledgeManager
from game.turns import TurnManager, PlayerAction, ActionType, TurnResult
from config.settings import get_settings

logger = logging.getLogger(__name__)


class GameState(str, Enum):
    """Game state machine states."""
    SETUP = "setup"
    SCENARIO_GEN = "scenario_gen"
    PLAYING = "playing"
    ACCUSATION = "accusation"
    RESULTS = "results"
    FINISHED = "finished"


class GameResult(str, Enum):
    """Possible game outcomes."""
    DETECTIVE_WINS = "detective_wins"      # Detective correctly identified the killer
    KILLER_WINS = "killer_wins"            # Killer escaped detection
    TIMEOUT = "timeout"                    # Max turns reached
    WRONG_ACCUSATION = "wrong_accusation"  # Detective accused wrong person


@dataclass
class GameSession:
    """Complete state for a single game session."""
    state: GameState = GameState.SETUP
    result: Optional[GameResult] = None

    # Characters
    player: Optional[Character] = None
    npcs: list[Character] = field(default_factory=list)
    victim: Optional[Character] = None
    all_characters: dict[str, Character] = field(default_factory=dict)

    # Scenario
    scenario: Optional[GameScenario] = None

    # Managers
    clue_manager: Optional[ClueManager] = None
    location_manager: Optional[LocationManager] = None
    knowledge_manager: Optional[KnowledgeManager] = None
    turn_manager: Optional[TurnManager] = None

    # Runtime
    current_turn: int = 0
    max_turns: int = 30
    turn_history: list[TurnResult] = field(default_factory=list)
    game_log: list[str] = field(default_factory=list)


class GameEngine:
    """Main game engine that orchestrates the murder mystery."""

    def __init__(self) -> None:
        self.session: Optional[GameSession] = None
        self.llm_client: Optional[LLMClientBase] = None
        self._settings = get_settings()

    async def initialize(self) -> None:
        """Initialize the LLM client and verify connectivity."""
        self.llm_client = get_client()
        connected = await self.llm_client.check_connection()
        if not connected:
            raise ConnectionError(
                "Cannot connect to LLM provider. Check your API key and network."
            )
        logger.info("LLM client connected successfully")

    async def new_game(
        self,
        player_role: str = "detective",
        player_name: str = "The Player",
        player_description: str = "",
    ) -> GameSession:
        """
        Start a new game session.

        Args:
            player_role: "detective" or "killer"
            player_name: Player's character name
            player_description: Optional character description

        Returns:
            Initialized GameSession in SETUP state.
        """
        if not self.llm_client:
            await self.initialize()

        session = GameSession()
        session.max_turns = self._settings.game.max_turns

        # Create player character
        role = CharacterRole.DETECTIVE if player_role == "detective" else CharacterRole.KILLER
        session.player = create_player_character(player_name, player_description, role)

        # Load and select NPCs
        pool = load_all_characters()
        if len(pool) < 8:
            raise ValueError(
                f"Need at least 8 characters in pool, found {len(pool)}. "
                f"Add more characters to backend/characters/."
            )

        npcs, victim = select_npcs(pool, count=7, include_victim=True)
        session.npcs = npcs
        session.victim = victim

        # Build character lookup
        session.all_characters = {session.player.name: session.player}
        if victim:
            session.all_characters[victim.name] = victim
        for npc in npcs:
            session.all_characters[npc.name] = npc

        session.state = GameState.SETUP
        self.session = session

        logger.info(
            "New game: player=%s (%s), %d NPCs, victim=%s",
            player_name, player_role, len(npcs), victim.name if victim else "none",
        )

        return session

    async def generate_game_scenario(self) -> GameScenario:
        """
        Generate the murder mystery scenario using AI.
        Must be called after new_game().
        """
        if not self.session or not self.llm_client:
            raise RuntimeError("Call new_game() first")

        self.session.state = GameState.SCENARIO_GEN

        scenario = await generate_scenario(
            llm_client=self.llm_client,
            player=self.session.player,
            npcs=self.session.npcs,
            victim=self.session.victim,
        )
        self.session.scenario = scenario

        # If player is the killer, override the scenario's killer assignment
        if self.session.player.assigned_role == CharacterRole.KILLER:
            # The player IS the killer, so pick a different NPC as the "detective"
            for npc in self.session.npcs:
                if npc.assigned_role != CharacterRole.VICTIM:
                    npc.assigned_role = CharacterRole.DETECTIVE
                    break
            scenario.murder.killer = self.session.player.name

        # Assign killer role to the NPC who is the killer
        if self.session.player.assigned_role == CharacterRole.DETECTIVE:
            for npc in self.session.npcs:
                if npc.name == scenario.murder.killer:
                    npc.assigned_role = CharacterRole.KILLER
                    break

        # Initialize subsystems
        self._init_clues(scenario)
        self._init_locations(scenario)
        self._init_knowledge(scenario)
        self._init_turns()

        self.session.state = GameState.PLAYING

        logger.info("Scenario generated: '%s'", scenario.title)
        return scenario

    def _init_clues(self, scenario: GameScenario) -> None:
        """Initialize the clue manager."""
        manager = ClueManager()
        manager.initialize_from_scenario(scenario.clues)
        self.session.clue_manager = manager

    def _init_locations(self, scenario: GameScenario) -> None:
        """Initialize locations and place characters."""
        manager = LocationManager()
        manager.initialize_from_scenario(scenario.locations)

        # Place player at the first location
        if scenario.locations:
            first_loc = scenario.locations[0].id
            manager.place_character(self.session.player.name, first_loc)

        # Place NPCs at their default or scenario-assigned locations
        for npc in self.session.npcs:
            npc_knowledge = scenario.npc_knowledge.get(npc.name)
            default_loc = npc.murder_mystery_ext.default_location

            # Try to find a matching location
            placed = False
            if default_loc:
                for loc in scenario.locations:
                    if loc.id == default_loc or default_loc in loc.id:
                        manager.place_character(npc.name, loc.id)
                        placed = True
                        break

            if not placed and scenario.locations:
                # Random location
                random_loc = random.choice(scenario.locations)
                manager.place_character(npc.name, random_loc.id)

        self.session.location_manager = manager

    def _init_knowledge(self, scenario: GameScenario) -> None:
        """Initialize the knowledge manager."""
        manager = KnowledgeManager()
        all_chars = [self.session.player] + self.session.npcs
        manager.initialize_from_scenario(scenario, all_chars)
        self.session.knowledge_manager = manager

    def _init_turns(self) -> None:
        """Initialize the turn manager."""
        self.session.turn_manager = TurnManager(
            llm_client=self.llm_client,
            location_manager=self.session.location_manager,
            knowledge_manager=self.session.knowledge_manager,
            clue_manager=self.session.clue_manager,
            characters=self.session.all_characters,
            player=self.session.player,
        )

    async def player_move(self, location_id: str) -> TurnResult:
        """Player moves to a new location."""
        return await self._do_turn(PlayerAction(
            action_type=ActionType.MOVE,
            target=location_id,
        ))

    async def player_talk(self, npc_name: str, message: str = "") -> TurnResult:
        """Player talks to an NPC."""
        return await self._do_turn(PlayerAction(
            action_type=ActionType.TALK,
            target=npc_name,
            message=message,
        ))

    async def player_investigate(self) -> TurnResult:
        """Player investigates the current location."""
        return await self._do_turn(PlayerAction(
            action_type=ActionType.INVESTIGATE,
        ))

    async def player_wait(self) -> TurnResult:
        """Player waits and observes."""
        return await self._do_turn(PlayerAction(
            action_type=ActionType.WAIT,
        ))

    async def player_accuse(self, suspect_name: str, reasoning: str = "") -> dict[str, Any]:
        """
        Player makes an accusation.
        This ends the game.

        Returns:
            Game result with details.
        """
        if not self.session:
            raise RuntimeError("No active game session")

        self.session.state = GameState.ACCUSATION
        actual_killer = self.session.scenario.murder.killer

        if self.session.player.assigned_role == CharacterRole.DETECTIVE:
            if suspect_name == actual_killer:
                self.session.result = GameResult.DETECTIVE_WINS
                outcome = "correct"
            else:
                self.session.result = GameResult.WRONG_ACCUSATION
                outcome = "wrong"
        else:
            # Player is killer — accusation doesn't apply the same way
            self.session.result = GameResult.KILLER_WINS
            outcome = "killer_revealed"

        self.session.state = GameState.RESULTS

        # Generate a narrative ending
        ending = await self._generate_ending(suspect_name, outcome, reasoning)

        return {
            "outcome": outcome,
            "player_role": self.session.player.assigned_role.value,
            "accused": suspect_name,
            "actual_killer": actual_killer,
            "result": self.session.result.value,
            "narrative_ending": ending,
            "turns_taken": self.session.current_turn,
            "clues_found": self.session.clue_manager.discovered_count,
            "total_clues": self.session.clue_manager.total_clues,
        }

    async def _do_turn(self, action: PlayerAction) -> TurnResult:
        """Execute a complete turn."""
        if not self.session or not self.session.turn_manager:
            raise RuntimeError("Game not initialized")

        if self.session.state != GameState.PLAYING:
            raise RuntimeError(f"Cannot play — game is in state: {self.session.state}")

        self.session.current_turn += 1

        # Check max turns
        if self.session.current_turn >= self.session.max_turns:
            self.session.state = GameState.RESULTS
            self.session.result = GameResult.TIMEOUT

        result = await self.session.turn_manager.process_player_action(action)
        self.session.turn_history.append(result)

        return result

    async def _generate_ending(
        self,
        suspect_name: str,
        outcome: str,
        reasoning: str,
    ) -> str:
        """Generate a narrative ending using the LLM."""
        if not self.llm_client or not self.session:
            return "The mystery concludes."

        scenario = self.session.scenario
        clues_found = self.session.clue_manager.get_discovered_clues()
        clue_descriptions = [c.clue.description for c in clues_found]

        prompt = f"""Write a dramatic concluding narration for a murder mystery game.

Scenario: {scenario.title}
Setting: {scenario.setting}
The murder: {scenario.murder.victim} was killed by {scenario.murder.killer}.
Method: {scenario.murder.method}
Motive: {scenario.murder.motive}

The player (role: {self.session.player.assigned_role.value}) accused: {suspect_name}
Outcome: {outcome}
Player's reasoning: {reasoning or 'No reasoning provided'}
Clues discovered: {', '.join(clue_descriptions[:5]) if clue_descriptions else 'Very few'}
Turns taken: {self.session.current_turn}

Write a 2-3 paragraph dramatic conclusion. Reveal the full truth of the mystery.
If the player was correct, make it triumphant. If wrong, make it bittersweet.
Be atmospheric and cinematic."""

        messages = [
            {"role": "system", "content": "You are a master mystery narrator. Write atmospheric, cinematic conclusions."},
            {"role": "user", "content": prompt},
        ]

        try:
            response = await self.llm_client.generate(messages, max_tokens=512, temperature=0.9)
            return response.content
        except Exception:
            return "The mystery reaches its conclusion, and the truth is finally revealed..."

    def get_game_state(self) -> dict[str, Any]:
        """Get the current game state for the frontend."""
        if not self.session:
            return {"state": "no_session"}

        state: dict[str, Any] = {
            "state": self.session.state.value,
            "turn": self.session.current_turn,
            "max_turns": self.session.max_turns,
            "player": {
                "name": self.session.player.name,
                "role": self.session.player.assigned_role.value if self.session.player.assigned_role else "",
            },
        }

        if self.session.state == GameState.PLAYING and self.session.location_manager:
            player_loc_id = self.session.location_manager.get_character_location(
                self.session.player.name
            )
            player_loc = self.session.location_manager.get_location(player_loc_id) if player_loc_id else None

            state["current_location"] = {
                "id": player_loc_id or "",
                "name": player_loc.name if player_loc else "",
                "description": player_loc.description if player_loc else "",
            }

            # Characters at current location
            chars_here = self.session.location_manager.get_characters_at(player_loc_id) if player_loc_id else []
            state["characters_here"] = [
                {
                    "name": c,
                    "is_player": c == self.session.player.name,
                }
                for c in chars_here
            ]

            # Available locations to move to
            if player_loc_id:
                adjacent = self.session.location_manager.get_adjacent_locations(player_loc_id)
                state["adjacent_locations"] = [
                    {"id": loc.id, "name": loc.name} for loc in adjacent
                ]

            # Clue progress
            if self.session.clue_manager:
                state["clues"] = {
                    "discovered": self.session.clue_manager.discovered_count,
                    "total": self.session.clue_manager.total_clues,
                    "list": [
                        {
                            "id": c.id,
                            "description": c.clue.description,
                            "difficulty": c.difficulty.value,
                            "discovered_at_turn": c.discovered_at_turn,
                        }
                        for c in self.session.clue_manager.get_discovered_clues()
                    ],
                }

            # NPC list (alive NPCs)
            state["npcs"] = [
                {
                    "name": npc.name,
                    "location": self.session.location_manager.get_character_location(npc.name) or "unknown",
                }
                for npc in self.session.npcs
                if npc.assigned_role != CharacterRole.VICTIM
            ]

            # Location map
            state["all_locations"] = [
                {
                    "id": loc.id,
                    "name": loc.name,
                    "characters": self.session.location_manager.get_characters_at(loc.id),
                }
                for loc in self.session.location_manager.get_all_locations()
            ]

        if self.session.scenario:
            state["scenario_title"] = self.session.scenario.title
            state["scenario_setting"] = self.session.scenario.setting

        if self.session.result:
            state["result"] = self.session.result.value

        return state

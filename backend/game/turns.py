"""
Turn-based game loop with hybrid NPC action resolution.
Locations processed in parallel, NPCs within a location processed sequentially.
"""
import asyncio
import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from llm.api_client import LLMClientBase
from llm.prompt_builder import build_messages, truncate_messages_to_fit
from game.characters import Character, CharacterRole
from game.locations import LocationManager
from game.knowledge import KnowledgeManager
from game.clues import ClueManager

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    MOVE = "move"
    TALK = "talk"
    INVESTIGATE = "investigate"
    ACCUSE = "accuse"
    WAIT = "wait"


@dataclass
class PlayerAction:
    """An action taken by the player."""
    action_type: ActionType
    target: str = ""       # NPC name, location ID, or clue ID
    message: str = ""      # Dialogue message or accusation reasoning
    turn: int = 0


@dataclass
class NPCAction:
    """An action taken by an NPC during their resolution."""
    npc_name: str
    action_type: ActionType
    target: str = ""
    dialogue: str = ""
    internal_thought: str = ""  # Not shown to player
    visible_to_player: bool = False


@dataclass
class TurnEvent:
    """A single event that occurred during a turn."""
    description: str
    location: str = ""
    involved: list[str] = field(default_factory=list)
    visible_to: list[str] = field(default_factory=list)  # Character names who can see this
    is_player_visible: bool = False


@dataclass
class TurnResult:
    """Complete result of processing a turn."""
    turn_number: int
    player_action: Optional[PlayerAction] = None
    player_action_response: str = ""
    npc_actions: list[NPCAction] = field(default_factory=list)
    events: list[TurnEvent] = field(default_factory=list)
    clues_discovered: list[str] = field(default_factory=list)
    narrative_summary: str = ""


NPC_ACTION_SYSTEM_PROMPT = """You are roleplaying as {npc_name} in a murder mystery game.

{character_description}

{knowledge_context}

CURRENT SITUATION:
- Location: {current_location}
- Others here: {others_present}
- Turn: {turn_number}

{recent_events}

Decide what {npc_name} does this turn. You should stay in character.
Consider: Would they move somewhere? Talk to someone present? Investigate? Stay quiet?

Respond with JSON:
{{
  "action": "move|talk|investigate|wait",
  "target": "location_id or character_name if applicable",
  "dialogue": "What they say out loud (if anything)",
  "internal_thought": "What they're privately thinking",
  "reason": "Brief reason for this action"
}}"""

NPC_DIALOGUE_SYSTEM_PROMPT = """You are {npc_name} in a murder mystery game. Stay in character.

{character_description}

{knowledge_context}

You are currently at: {current_location}
Others present: {others_present}

The player ({player_name}) is talking to you. Respond in character.
Do NOT reveal your secrets easily. Be natural, suspicious, or helpful according to your personality.
If you have a clue the player might want, hint at it but don't give it away freely.
Keep responses concise (2-4 paragraphs max) and atmospheric."""


class TurnManager:
    """Manages the turn-based game loop with hybrid NPC resolution."""

    def __init__(
        self,
        llm_client: LLMClientBase,
        location_manager: LocationManager,
        knowledge_manager: KnowledgeManager,
        clue_manager: ClueManager,
        characters: dict[str, Character],
        player: Character,
    ) -> None:
        self.llm = llm_client
        self.locations = location_manager
        self.knowledge = knowledge_manager
        self.clues = clue_manager
        self.characters = characters  # name -> Character
        self.player = player
        self.current_turn = 0
        self.conversation_histories: dict[str, list[dict[str, str]]] = {}  # npc_name -> history
        self.turn_history: list[TurnResult] = []

    async def process_player_action(self, action: PlayerAction) -> TurnResult:
        """
        Process a player action and resolve all NPC actions.

        This is the main turn loop:
        1. Resolve the player's action
        2. Resolve NPC actions (hybrid: parallel by location, sequential within)
        3. Compile turn results
        """
        self.current_turn += 1
        action.turn = self.current_turn

        result = TurnResult(
            turn_number=self.current_turn,
            player_action=action,
        )

        # 1. Resolve player action
        player_response = await self._resolve_player_action(action, result)
        result.player_action_response = player_response

        # 2. Resolve NPC actions (hybrid model)
        npc_actions = await self._resolve_all_npc_actions()
        result.npc_actions = npc_actions

        # 3. Filter events visible to the player
        player_location = self.locations.get_character_location(self.player.name)
        for npc_action in npc_actions:
            event = TurnEvent(
                description=npc_action.dialogue or f"{npc_action.npc_name} {npc_action.action_type.value}s.",
                location=self.locations.get_character_location(npc_action.npc_name) or "",
                involved=[npc_action.npc_name],
            )
            # Player can see events at their location
            npc_location = self.locations.get_character_location(npc_action.npc_name)
            event.is_player_visible = (npc_location == player_location)
            npc_action.visible_to_player = event.is_player_visible
            result.events.append(event)

        # 4. Generate narrative summary
        result.narrative_summary = self._generate_turn_summary(result)
        self.turn_history.append(result)

        return result

    async def _resolve_player_action(
        self,
        action: PlayerAction,
        result: TurnResult,
    ) -> str:
        """Resolve the player's action and return the response text."""

        match action.action_type:
            case ActionType.MOVE:
                success = self.locations.move_character(self.player.name, action.target)
                if success:
                    loc = self.locations.get_location(action.target)
                    chars_here = self.locations.get_characters_at(action.target)
                    chars_here = [c for c in chars_here if c != self.player.name]
                    npc_list = ", ".join(chars_here) if chars_here else "no one"
                    return (
                        f"You move to **{loc.name if loc else action.target}**.\n"
                        f"*{loc.description if loc else ''}*\n\n"
                        f"Present here: {npc_list}"
                    )
                else:
                    return "You can't reach that location from here."

            case ActionType.TALK:
                return await self._handle_player_talk(action)

            case ActionType.INVESTIGATE:
                return self._handle_player_investigate(action, result)

            case ActionType.ACCUSE:
                return ""  # Handled separately by the engine

            case ActionType.WAIT:
                return "*You wait and observe your surroundings.*"

        return ""

    async def _handle_player_talk(self, action: PlayerAction) -> str:
        """Handle the player talking to an NPC."""
        npc_name = action.target
        char = self.characters.get(npc_name)
        if not char:
            return f"There's no one named {npc_name} here."

        # Check NPC is at the same location
        player_loc = self.locations.get_character_location(self.player.name)
        npc_loc = self.locations.get_character_location(npc_name)
        if player_loc != npc_loc:
            return f"{npc_name} isn't here. They're somewhere else."

        # Get conversation history
        history = self.conversation_histories.get(npc_name, [])

        # Build the NPC's prompt
        knowledge_ctx = self.knowledge.get_npc_prompt_context(npc_name)
        others = [c for c in self.locations.get_characters_at(player_loc) if c not in (self.player.name, npc_name)]

        system_prompt = NPC_DIALOGUE_SYSTEM_PROMPT.format(
            npc_name=npc_name,
            character_description=char.get_prompt_description(),
            knowledge_context=knowledge_ctx,
            current_location=player_loc,
            others_present=", ".join(others) if others else "no one else",
            player_name=self.player.name,
        )

        messages = build_messages(
            system_prompt=system_prompt,
            conversation_history=history,
            user_message=action.message or f"*{self.player.name} approaches {npc_name}.*",
        )
        messages = truncate_messages_to_fit(messages)

        response = await self.llm.generate(messages, max_tokens=512)

        # Update conversation history
        if npc_name not in self.conversation_histories:
            self.conversation_histories[npc_name] = []
        self.conversation_histories[npc_name].append(
            {"role": "user", "content": action.message or "Hello."}
        )
        self.conversation_histories[npc_name].append(
            {"role": "assistant", "content": response.content}
        )

        # Record conversation in knowledge
        self.knowledge.record_conversation(
            npc_name,
            self.player.name,
            f"Player asked: '{action.message[:50]}...' Turn {self.current_turn}",
        )

        # Check if any clues should be revealed
        npc_clues = self.clues.get_clues_from_npc(npc_name)
        for clue in npc_clues:
            # Simple heuristic: medium+ difficulty clues may be revealed through conversation
            if clue.difficulty.value == "easy" or (
                clue.difficulty.value == "medium"
                and len(self.conversation_histories.get(npc_name, [])) >= 4
            ):
                discovered = self.clues.discover_clue(
                    clue.id, self.player.name, self.current_turn
                )
                if discovered:
                    response.content += f"\n\n🔍 **Clue discovered:** {discovered.clue.description}"

        return response.content

    def _handle_player_investigate(
        self,
        action: PlayerAction,
        result: TurnResult,
    ) -> str:
        """Handle the player investigating a location."""
        player_loc = self.locations.get_character_location(self.player.name)
        if not player_loc:
            return "You need to be at a location to investigate."

        location_clues = self.clues.get_clues_at_location(player_loc)
        if not location_clues:
            return "*You search the area carefully but find nothing new.*"

        # Discover easy clues automatically, medium with some luck
        found_text = []
        for clue in location_clues:
            if clue.difficulty.value == "easy":
                discovered = self.clues.discover_clue(clue.id, self.player.name, self.current_turn)
                if discovered:
                    found_text.append(f"🔍 **{discovered.clue.description}**")
                    result.clues_discovered.append(clue.id)
            elif clue.difficulty.value == "medium" and random.random() > 0.4:
                discovered = self.clues.discover_clue(clue.id, self.player.name, self.current_turn)
                if discovered:
                    found_text.append(f"🔍 **{discovered.clue.description}**")
                    result.clues_discovered.append(clue.id)

        if found_text:
            return "*You search the area and find something...*\n\n" + "\n".join(found_text)
        else:
            return "*You search carefully but don't find anything significant... yet. Perhaps a more thorough search or the right questions might help.*"

    async def _resolve_all_npc_actions(self) -> list[NPCAction]:
        """
        Resolve all NPC actions using the hybrid model:
        - Parallel across locations
        - Sequential within each location
        """
        groups = self.locations.get_npcs_grouped_by_location(exclude=self.player.name)

        # Process each location group in parallel
        tasks = [
            self._resolve_location_group(loc_id, npc_names)
            for loc_id, npc_names in groups.items()
        ]

        location_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Flatten results
        all_actions: list[NPCAction] = []
        for loc_result in location_results:
            if isinstance(loc_result, Exception):
                logger.error("Location group resolution failed: %s", loc_result)
                continue
            all_actions.extend(loc_result)

        return all_actions

    async def _resolve_location_group(
        self,
        location_id: str,
        npc_names: list[str],
    ) -> list[NPCAction]:
        """
        Resolve NPCs at a single location SEQUENTIALLY.
        Each NPC can react to what the previous NPC did.
        """
        actions: list[NPCAction] = []
        recent_events_at_location: list[str] = []

        for npc_name in npc_names:
            char = self.characters.get(npc_name)
            if not char or char.assigned_role == CharacterRole.VICTIM:
                continue

            try:
                action = await self._resolve_single_npc(
                    npc_name, location_id, recent_events_at_location
                )
                actions.append(action)

                # Add this NPC's action to the event list for the next NPC
                if action.dialogue:
                    recent_events_at_location.append(
                        f"{npc_name} said: \"{action.dialogue}\""
                    )
                if action.action_type == ActionType.MOVE:
                    recent_events_at_location.append(
                        f"{npc_name} left toward {action.target}."
                    )
                    # Actually move the NPC
                    self.locations.move_character(npc_name, action.target)

            except Exception as e:
                logger.error("Failed to resolve NPC %s: %s", npc_name, e)
                # Fallback: NPC waits
                actions.append(NPCAction(
                    npc_name=npc_name,
                    action_type=ActionType.WAIT,
                    dialogue="",
                    internal_thought="(Action resolution failed)",
                ))

        return actions

    async def _resolve_single_npc(
        self,
        npc_name: str,
        location_id: str,
        recent_events: list[str],
    ) -> NPCAction:
        """Resolve a single NPC's action using the LLM."""
        char = self.characters.get(npc_name)
        if not char:
            return NPCAction(npc_name=npc_name, action_type=ActionType.WAIT)

        knowledge_ctx = self.knowledge.get_npc_prompt_context(npc_name)
        loc = self.locations.get_location(location_id)
        others = [c for c in self.locations.get_characters_at(location_id) if c != npc_name]

        recent_str = ""
        if recent_events:
            recent_str = "RECENT EVENTS HERE:\n" + "\n".join(f"- {e}" for e in recent_events[-5:])

        system_prompt = NPC_ACTION_SYSTEM_PROMPT.format(
            npc_name=npc_name,
            character_description=char.get_prompt_description(),
            knowledge_context=knowledge_ctx,
            current_location=loc.name if loc else location_id,
            others_present=", ".join(others) if others else "no one",
            turn_number=self.current_turn,
            recent_events=recent_str,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"What does {npc_name} do this turn? Respond with JSON."},
        ]

        try:
            response = await self.llm.generate(messages, max_tokens=256, temperature=0.8)
            content = response.content.strip()

            # Parse JSON from response
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
                content = content.rsplit("```", 1)[0]

            import json
            data = json.loads(content)

            action_type = ActionType(data.get("action", "wait"))

            # Validate move targets
            if action_type == ActionType.MOVE:
                target = data.get("target", "")
                if not self.locations.get_location(target):
                    # Invalid target, stay put
                    action_type = ActionType.WAIT
                    data["target"] = ""

            return NPCAction(
                npc_name=npc_name,
                action_type=action_type,
                target=data.get("target", ""),
                dialogue=data.get("dialogue", ""),
                internal_thought=data.get("internal_thought", ""),
            )

        except Exception as e:
            logger.warning("NPC %s action parse failed: %s, defaulting to wait", npc_name, e)
            return NPCAction(
                npc_name=npc_name,
                action_type=ActionType.WAIT,
            )

    def _generate_turn_summary(self, result: TurnResult) -> str:
        """Generate a narrative summary of the turn for the player."""
        lines = [f"--- Turn {result.turn_number} ---"]

        # Player action
        if result.player_action:
            action = result.player_action
            lines.append(f"\n**Your action:** {action.action_type.value}")

        # Events visible to the player
        visible_events = [e for e in result.events if e.is_player_visible]
        if visible_events:
            lines.append("\n**What you observe:**")
            for event in visible_events:
                lines.append(f"• {event.description}")

        # Events heard about (at other locations)
        hidden_events = [e for e in result.events if not e.is_player_visible and e.description]
        if hidden_events:
            lines.append(f"\n*You hear faint sounds from elsewhere in the building — the others are active too.*")

        # Clues found
        if result.clues_discovered:
            lines.append(f"\n📋 **New clues found:** {len(result.clues_discovered)}")

        return "\n".join(lines)

    def get_recent_events_for_npc(self, npc_name: str, count: int = 5) -> list[str]:
        """Get recent events visible to an NPC for context."""
        events: list[str] = []
        for turn_result in self.turn_history[-count:]:
            for event in turn_result.events:
                npc_loc = self.locations.get_character_location(npc_name)
                if event.location == npc_loc or npc_name in event.involved:
                    events.append(f"Turn {turn_result.turn_number}: {event.description}")
        return events

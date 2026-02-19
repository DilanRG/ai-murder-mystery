"""
AI-driven scenario generation.
Takes selected characters and produces a complete murder mystery scenario.
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from llm.api_client import LLMClientBase, LLMResponse
from llm.prompt_builder import build_messages, truncate_messages_to_fit
from game.characters import Character, CharacterRole

logger = logging.getLogger(__name__)

SCENARIO_SYSTEM_PROMPT = """You are a master mystery writer and game designer. Your task is to create a compelling murder mystery scenario.

You will be given a list of characters. You must:
1. Create a vivid setting/location for the mystery (e.g., a grand estate, a luxury train, a remote island hotel)
2. Define the MURDER: who was killed, how, when, where, and why
3. Assign the KILLER role to one NPC (not the player)
4. Create a web of CLUES that lead to the killer, with varying difficulty
5. Give each NPC character unique knowledge, alibis, and potential motives
6. Create RED HERRINGS — false leads that point to innocent characters
7. Design LOCATIONS within the setting for characters to inhabit and move between

The mystery should be layered like Murder on the Orient Express mixed with Hitman — theatrical, with hidden depths.

CRITICAL RULES:
- The scenario must be solvable through careful investigation
- Every NPC must have something to hide (even if it's unrelated to the murder)
- Clues should have difficulty tiers: EASY (obvious), MEDIUM (requires asking the right questions), HARD (requires combining multiple pieces of evidence)
- The killer's motive should be compelling and sympathetic, not cartoonish

Respond ONLY with valid JSON matching the schema provided."""

SCENARIO_USER_PROMPT_TEMPLATE = """Create a murder mystery scenario with these characters:

PLAYER CHARACTER:
- Name: {player_name}
- Role: {player_role}
- Description: {player_description}

NPC CHARACTERS:
{npc_descriptions}

VICTIM (already selected):
- Name: {victim_name}
- Description: {victim_description}

Generate a complete scenario as JSON with this exact schema:
{{
  "title": "Scenario title",
  "setting": "Detailed description of the setting/location",
  "time_period": "When the story takes place",
  "backstory": "Events leading up to the murder",
  "murder": {{
    "victim": "{victim_name}",
    "killer": "Name of the NPC who is the killer",
    "method": "How the murder was committed",
    "motive": "Why the killer did it",
    "time_of_death": "When the murder occurred",
    "location_of_death": "Where the body was found"
  }},
  "locations": [
    {{
      "id": "location_id",
      "name": "Location Name",
      "description": "What this place looks like and contains",
      "connected_to": ["other_location_id"],
      "clues_here": ["clue_id"]
    }}
  ],
  "clues": [
    {{
      "id": "clue_id",
      "description": "What the clue is",
      "points_to": "Who or what it implicates",
      "difficulty": "easy|medium|hard",
      "found_at": "location_id or npc_name",
      "type": "physical|testimony|document|observation"
    }}
  ],
  "npc_knowledge": {{
    "NPC Name": {{
      "alibi": "Where they claim to have been",
      "true_whereabouts": "Where they actually were",
      "known_clues": ["clue_ids they know about"],
      "secrets": ["Their personal secrets relevant to the scenario"],
      "attitude": "How they feel about the investigation",
      "suspicions": "Who they suspect and why"
    }}
  }},
  "red_herrings": [
    {{
      "description": "The false lead",
      "implicates": "Who it wrongly points to",
      "truth": "What the real explanation is"
    }}
  ],
  "opening_narration": "Atmospheric text to read to the player when the game begins"
}}"""


@dataclass
class MurderDetails:
    """Details about the murder."""
    victim: str = ""
    killer: str = ""
    method: str = ""
    motive: str = ""
    time_of_death: str = ""
    location_of_death: str = ""


@dataclass
class ScenarioClue:
    """A clue in the scenario."""
    id: str = ""
    description: str = ""
    points_to: str = ""
    difficulty: str = "medium"
    found_at: str = ""
    type: str = "physical"
    discovered: bool = False


@dataclass
class LocationDef:
    """A location definition from the scenario."""
    id: str = ""
    name: str = ""
    description: str = ""
    connected_to: list[str] = field(default_factory=list)
    clues_here: list[str] = field(default_factory=list)


@dataclass
class NPCKnowledge:
    """What an NPC knows in this scenario."""
    alibi: str = ""
    true_whereabouts: str = ""
    known_clues: list[str] = field(default_factory=list)
    secrets: list[str] = field(default_factory=list)
    attitude: str = ""
    suspicions: str = ""


@dataclass
class RedHerring:
    """A false lead."""
    description: str = ""
    implicates: str = ""
    truth: str = ""


@dataclass
class GameScenario:
    """Complete generated scenario for a game session."""
    title: str = ""
    setting: str = ""
    time_period: str = ""
    backstory: str = ""
    murder: MurderDetails = field(default_factory=MurderDetails)
    locations: list[LocationDef] = field(default_factory=list)
    clues: list[ScenarioClue] = field(default_factory=list)
    npc_knowledge: dict[str, NPCKnowledge] = field(default_factory=dict)
    red_herrings: list[RedHerring] = field(default_factory=list)
    opening_narration: str = ""
    raw_json: dict = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: dict) -> "GameScenario":
        """Parse a GameScenario from the AI-generated JSON."""
        murder_data = data.get("murder", {})
        murder = MurderDetails(**murder_data)

        locations = [
            LocationDef(**loc)
            for loc in data.get("locations", [])
        ]

        clues = [
            ScenarioClue(**clue)
            for clue in data.get("clues", [])
        ]

        npc_knowledge = {
            name: NPCKnowledge(**info)
            for name, info in data.get("npc_knowledge", {}).items()
        }

        red_herrings = [
            RedHerring(**rh)
            for rh in data.get("red_herrings", [])
        ]

        return cls(
            title=data.get("title", "Untitled Mystery"),
            setting=data.get("setting", ""),
            time_period=data.get("time_period", ""),
            backstory=data.get("backstory", ""),
            murder=murder,
            locations=locations,
            clues=clues,
            npc_knowledge=npc_knowledge,
            red_herrings=red_herrings,
            opening_narration=data.get("opening_narration", ""),
            raw_json=data,
        )

    def get_clue_by_id(self, clue_id: str) -> ScenarioClue | None:
        """Find a clue by its ID."""
        return next((c for c in self.clues if c.id == clue_id), None)

    def get_location_by_id(self, loc_id: str) -> LocationDef | None:
        """Find a location by its ID."""
        return next((l for l in self.locations if l.id == loc_id), None)


async def generate_scenario(
    llm_client: LLMClientBase,
    player: Character,
    npcs: list[Character],
    victim: Character,
) -> GameScenario:
    """
    Generate a complete murder mystery scenario using the LLM.

    Args:
        llm_client: The LLM client to use.
        player: The player's character.
        npcs: List of NPC characters.
        victim: The victim character.

    Returns:
        A complete GameScenario.
    """
    # Build NPC descriptions
    npc_descriptions = "\n".join(
        f"- {npc.name}: {npc.description} (Personality: {npc.personality})"
        for npc in npcs
    )

    user_prompt = SCENARIO_USER_PROMPT_TEMPLATE.format(
        player_name=player.name,
        player_role=player.assigned_role.value if player.assigned_role else "detective",
        player_description=player.description,
        npc_descriptions=npc_descriptions,
        victim_name=victim.name,
        victim_description=victim.description,
    )

    messages = build_messages(
        system_prompt=SCENARIO_SYSTEM_PROMPT,
        conversation_history=[],
        user_message=user_prompt,
    )

    messages = truncate_messages_to_fit(messages)

    logger.info("Generating scenario with %d characters...", len(npcs) + 2)

    response = await llm_client.generate(
        messages,
        max_tokens=4096,
        temperature=1.0,
        top_p=0.95,
    )

    # Parse the JSON response
    content = response.content.strip()
    # Handle markdown code fences
    if content.startswith("```"):
        content = content.split("\n", 1)[1]  # Remove first line
        content = content.rsplit("```", 1)[0]  # Remove last fence

    try:
        scenario_data = json.loads(content)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse scenario JSON: %s", e)
        logger.debug("Raw response: %s", content[:500])
        raise ValueError("Failed to generate valid scenario. Please try again.") from e

    scenario = GameScenario.from_json(scenario_data)
    logger.info("Generated scenario: '%s' — Killer: %s", scenario.title, scenario.murder.killer)

    return scenario

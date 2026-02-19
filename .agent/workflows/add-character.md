---
description: How to add a new NPC character to the character pool
---

# Add a New NPC Character

Characters follow the **Character Card V2** spec and live in `backend/characters/`.

## Steps

### 1. Create a new JSON file
Create `backend/characters/<character_name>.json` using snake_case naming.

### 2. Use this template
```json
{
  "spec": "chara_card_v2",
  "spec_version": "2.0",
  "data": {
    "name": "Character Name",
    "description": "A 2-3 paragraph physical and background description of the character.",
    "personality": "Comma-separated personality traits: e.g. 'shrewd, secretive, darkly humorous, loyal to a fault'",
    "first_mes": "The character's first message/greeting when approached by the player.",
    "mes_example": "<START>\n{{user}}: Example player dialogue\n{{char}}: Example character response showing their personality and speech patterns.",
    "scenario": "Any scenario-specific context for the character (may be overridden by game engine).",
    "tags": ["archetype_tag", "role_tag"],
    "creator_notes": "Design notes: what makes this character interesting in a murder mystery context, what secrets they might hold.",
    "system_prompt": "",
    "post_history_instructions": "",
    "alternate_greetings": [],
    "character_book": null,
    "extensions": {
      "murder_mystery": {
        "possible_roles": ["suspect", "witness", "victim", "red_herring"],
        "default_location": "location_id",
        "social_connections": [],
        "secrets": []
      }
    }
  }
}
```

### 3. Ensure variety
- Each character should have a **distinct personality, background, and speech pattern**
- Include at least 2-3 `possible_roles` so the game engine has flexibility
- Define `secrets` that could be relevant across different scenarios

### 4. Test the character
// turbo
```
cd c:\random scripting\game\backend
python -c "from game.characters import load_character; c = load_character('characters/<character_name>.json'); print(f'Loaded: {c.name}')"
```

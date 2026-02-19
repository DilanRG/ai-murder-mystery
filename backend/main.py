"""
AI Murder Mystery Game — FastAPI Backend Server.
Provides REST API endpoints for the Electron frontend.
"""
import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config.settings import get_settings
from config.user_settings import (
    get_user_config,
    save_user_config,
    apply_user_config_to_settings,
    load_user_config,
)
from game.engine import GameEngine, GameState

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Global game engine instance
engine = GameEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App startup/shutdown lifecycle."""
    logger.info("🔪 AI Murder Mystery Game — Backend Starting...")
    # Load saved user config and apply to runtime settings
    load_user_config()
    apply_user_config_to_settings()
    try:
        await engine.initialize()
        logger.info("✅ Backend ready")
    except Exception as e:
        logger.warning("⚠️  LLM not connected: %s (configure via Settings)", e)
    yield
    logger.info("Backend shutting down")


app = FastAPI(
    title="AI Murder Mystery Game",
    description="Backend API for the AI-powered murder mystery game",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for Electron
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request Models ──────────────────────────────────────────────

class NewGameRequest(BaseModel):
    player_role: str = "detective"  # "detective" or "killer"
    player_name: str = "The Player"
    player_description: str = ""


class TalkRequest(BaseModel):
    npc_name: str
    message: str = ""


class MoveRequest(BaseModel):
    location_id: str


class AccuseRequest(BaseModel):
    suspect_name: str
    reasoning: str = ""


class SettingsUpdateRequest(BaseModel):
    api_key: Optional[str] = None
    model: Optional[str] = None
    providers: Optional[list[str]] = None
    instruct_template: Optional[str] = None
    context_length: Optional[int] = None
    response_length: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    repetition_penalty: Optional[float] = None
    min_p: Optional[float] = None


# ── API Endpoints ───────────────────────────────────────────────

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "game_ready": engine.llm_client is not None}


@app.get("/api/state")
async def get_state():
    """Get the current game state."""
    return engine.get_game_state()


@app.post("/api/game/new")
async def new_game(req: NewGameRequest):
    """Start a new game session."""
    try:
        session = await engine.new_game(
            player_role=req.player_role,
            player_name=req.player_name,
            player_description=req.player_description,
        )
        return {
            "status": "ok",
            "message": f"Game created. Player: {req.player_name} ({req.player_role})",
            "npcs": [npc.name for npc in session.npcs],
            "victim": session.victim.name if session.victim else None,
        }
    except Exception as e:
        logger.error("Failed to create game: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/game/generate-scenario")
async def generate_scenario():
    """Generate the murder mystery scenario (takes a moment)."""
    if not engine.session:
        raise HTTPException(status_code=400, detail="No game session. Call /api/game/new first.")

    try:
        scenario = await engine.generate_game_scenario()
        return {
            "status": "ok",
            "title": scenario.title,
            "setting": scenario.setting,
            "opening_narration": scenario.opening_narration,
            "locations": [
                {"id": loc.id, "name": loc.name, "description": loc.description}
                for loc in scenario.locations
            ],
            "victim": scenario.murder.victim,
        }
    except Exception as e:
        logger.error("Scenario generation failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/game/talk")
async def talk_to_npc(req: TalkRequest):
    """Talk to an NPC."""
    if not engine.session or engine.session.state != GameState.PLAYING:
        raise HTTPException(status_code=400, detail="Game not in playing state.")

    try:
        result = await engine.player_talk(req.npc_name, req.message)
        return {
            "status": "ok",
            "response": result.player_action_response,
            "turn": result.turn_number,
            "events": [
                {
                    "description": e.description,
                    "visible": e.is_player_visible,
                    "location": e.location,
                }
                for e in result.events
            ],
            "narrative": result.narrative_summary,
            "state": engine.get_game_state(),
        }
    except Exception as e:
        logger.error("Talk failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/game/move")
async def move_player(req: MoveRequest):
    """Move to a different location."""
    if not engine.session or engine.session.state != GameState.PLAYING:
        raise HTTPException(status_code=400, detail="Game not in playing state.")

    try:
        result = await engine.player_move(req.location_id)
        return {
            "status": "ok",
            "response": result.player_action_response,
            "turn": result.turn_number,
            "events": [
                {
                    "description": e.description,
                    "visible": e.is_player_visible,
                    "location": e.location,
                }
                for e in result.events
            ],
            "narrative": result.narrative_summary,
            "state": engine.get_game_state(),
        }
    except Exception as e:
        logger.error("Move failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/game/investigate")
async def investigate():
    """Investigate the current location."""
    if not engine.session or engine.session.state != GameState.PLAYING:
        raise HTTPException(status_code=400, detail="Game not in playing state.")

    try:
        result = await engine.player_investigate()
        return {
            "status": "ok",
            "response": result.player_action_response,
            "turn": result.turn_number,
            "clues_found": result.clues_discovered,
            "events": [
                {
                    "description": e.description,
                    "visible": e.is_player_visible,
                    "location": e.location,
                }
                for e in result.events
            ],
            "narrative": result.narrative_summary,
            "state": engine.get_game_state(),
        }
    except Exception as e:
        logger.error("Investigate failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/game/wait")
async def wait_turn():
    """Wait and observe."""
    if not engine.session or engine.session.state != GameState.PLAYING:
        raise HTTPException(status_code=400, detail="Game not in playing state.")

    try:
        result = await engine.player_wait()
        return {
            "status": "ok",
            "response": result.player_action_response,
            "turn": result.turn_number,
            "events": [
                {
                    "description": e.description,
                    "visible": e.is_player_visible,
                    "location": e.location,
                }
                for e in result.events
            ],
            "narrative": result.narrative_summary,
            "state": engine.get_game_state(),
        }
    except Exception as e:
        logger.error("Wait failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/game/accuse")
async def accuse(req: AccuseRequest):
    """Make an accusation — this ends the game."""
    if not engine.session or engine.session.state != GameState.PLAYING:
        raise HTTPException(status_code=400, detail="Game not in playing state.")

    try:
        result = await engine.player_accuse(req.suspect_name, req.reasoning)
        return {
            "status": "ok",
            **result,
            "state": engine.get_game_state(),
        }
    except Exception as e:
        logger.error("Accusation failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/settings")
async def get_current_settings():
    """Get current settings (API key masked)."""
    config = get_user_config()
    settings = get_settings()
    return {
        "api_key": ("***" + config["api_key"][-6:]) if len(config.get("api_key", "")) > 6 else ("•" * len(config.get("api_key", "")) if config.get("api_key") else ""),
        "api_key_set": bool(config.get("api_key") or settings.llm.openrouter_api_key),
        "model": config.get("model") or settings.llm.model,
        "providers": config.get("providers", []),
        "instruct_template": config.get("instruct_template", "chatml"),
        "context_length": config.get("context_length", settings.llm.max_context_tokens),
        "response_length": config.get("response_length", settings.llm.max_response_tokens),
        "temperature": config.get("temperature", settings.sampler.temperature),
        "top_p": config.get("top_p", settings.sampler.top_p),
        "top_k": config.get("top_k", settings.sampler.top_k),
        "repetition_penalty": config.get("repetition_penalty", settings.sampler.repetition_penalty),
        "min_p": config.get("min_p", settings.sampler.min_p),
        "connected": engine.llm_client is not None,
    }


@app.post("/api/settings")
async def update_settings(req: SettingsUpdateRequest):
    """Update and persist all settings."""
    config = get_user_config()

    # Update config with non-None values
    updates = req.model_dump(exclude_none=True)
    config.update(updates)
    save_user_config(config)

    # Apply to runtime settings
    apply_user_config_to_settings()

    # Reinitialize LLM client if connection-related settings changed
    if any(k in updates for k in ("api_key", "model")):
        try:
            await engine.initialize()
            return {"status": "ok", "message": "Settings saved. LLM reconnected.", "connected": True}
        except Exception as e:
            return {"status": "ok", "message": f"Settings saved. LLM error: {e}", "connected": False}

    return {"status": "ok", "message": "Settings saved.", "connected": engine.llm_client is not None}


@app.get("/api/models/search")
async def search_models(q: str = ""):
    """Search available models from OpenRouter."""
    import httpx

    settings = get_settings()
    config = get_user_config()
    api_key = config.get("api_key") or settings.llm.openrouter_api_key

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            resp = await client.get(
                f"{settings.llm.openrouter_base_url}/models",
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.error("Model search failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Failed to fetch models: {e}")

    models = data.get("data", [])
    query_lower = q.lower()

    results = []
    for m in models:
        model_id = m.get("id", "")
        model_name = m.get("name", model_id)

        # Filter by query
        if query_lower and query_lower not in model_id.lower() and query_lower not in model_name.lower():
            continue

        # Extract pricing
        pricing = m.get("pricing", {})
        prompt_price = float(pricing.get("prompt", "0")) * 1_000_000
        completion_price = float(pricing.get("completion", "0")) * 1_000_000

        results.append({
            "id": model_id,
            "name": model_name,
            "context_length": m.get("context_length", 0),
            "prompt_price": round(prompt_price, 2),
            "completion_price": round(completion_price, 2),
            "provider": model_id.split("/")[0] if "/" in model_id else "",
            "top_provider": m.get("top_provider", {}).get("max_completion_tokens"),
        })

    # Sort by name
    results.sort(key=lambda x: x["name"].lower())

    return {"models": results[:100]}  # Cap at 100 results


@app.get("/api/instruct-presets")
async def list_instruct_presets():
    """List available instruct template presets."""
    from config.settings import INSTRUCT_PRESETS_DIR

    presets = []
    if INSTRUCT_PRESETS_DIR.exists():
        for p in sorted(INSTRUCT_PRESETS_DIR.glob("*.jinja2")):
            presets.append({
                "id": p.stem,
                "name": p.stem.replace("_", " ").title(),
                "filename": p.name,
            })

    return {"presets": presets}


@app.get("/api/characters")
async def list_characters():
    """List all available characters in the pool."""
    from game.characters import load_all_characters
    chars = load_all_characters()
    return {
        "characters": [
            {
                "name": c.name,
                "description": c.description[:100] + "..." if len(c.description) > 100 else c.description,
                "personality": c.personality,
                "tags": c.tags,
            }
            for c in chars
        ]
    }


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )

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
    try:
        await engine.initialize()
        logger.info("✅ Backend ready")
    except Exception as e:
        logger.warning("⚠️  LLM not connected: %s (configure API key to play)", e)
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
    temperature: Optional[float] = None
    top_p: Optional[float] = None


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


@app.post("/api/settings")
async def update_settings(req: SettingsUpdateRequest):
    """Update runtime settings (API key, model, etc.)."""
    settings = get_settings()

    if req.api_key is not None:
        settings.llm.openrouter_api_key = req.api_key
        # Reinitialize the engine with new key
        try:
            await engine.initialize()
        except Exception as e:
            return {"status": "error", "message": str(e)}

    if req.model is not None:
        settings.llm.model = req.model

    if req.temperature is not None:
        settings.sampler.temperature = req.temperature

    if req.top_p is not None:
        settings.sampler.top_p = req.top_p

    return {"status": "ok", "message": "Settings updated"}


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

"""
Application configuration using Pydantic Settings.
Loads from .env file and environment variables.
"""
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
CHARACTERS_DIR = BASE_DIR / "characters"
SAMPLER_PRESETS_DIR = BASE_DIR / "config" / "sampler_presets"
INSTRUCT_PRESETS_DIR = BASE_DIR / "config" / "instruct_presets"


class LLMSettings(BaseSettings):
    """LLM provider configuration."""

    provider: str = Field(default="openrouter", description="LLM provider name")
    openrouter_api_key: str = Field(default="", description="OpenRouter API key")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenRouter API base URL",
    )
    model: str = Field(
        default="openai/gpt-4o-mini",
        description="Model identifier (provider/model format for OpenRouter)",
    )
    max_context_tokens: int = Field(default=8192, description="Max context window size")
    max_response_tokens: int = Field(default=1024, description="Max tokens in response")

    model_config = {"env_prefix": "LLM_", "env_file": str(BASE_DIR / ".env"), "extra": "ignore"}


class SamplerSettings(BaseSettings):
    """Default sampler parameters. Can be overridden by presets."""

    temperature: float = Field(default=0.9, ge=0.0, le=2.0)
    top_p: float = Field(default=0.95, ge=0.0, le=1.0)
    top_k: int = Field(default=40, ge=0)
    repetition_penalty: float = Field(default=1.1, ge=1.0, le=2.0)
    min_p: float = Field(default=0.05, ge=0.0, le=1.0)

    model_config = {"env_prefix": "SAMPLER_", "env_file": str(BASE_DIR / ".env"), "extra": "ignore"}


class GameSettings(BaseSettings):
    """Game-specific configuration."""

    total_characters: int = Field(default=8, description="Total chars including player")
    npc_count: int = Field(default=7, description="Number of NPCs (excl. player)")
    victim_count: int = Field(default=1, description="Number of victims")
    max_turns: int = Field(default=30, description="Maximum turns before game ends")
    locations_count: int = Field(default=6, description="Number of locations in scenario")

    model_config = {"env_prefix": "GAME_", "env_file": str(BASE_DIR / ".env"), "extra": "ignore"}


class AppSettings(BaseSettings):
    """Top-level application settings."""

    debug: bool = Field(default=False)
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8765)

    llm: LLMSettings = Field(default_factory=LLMSettings)
    sampler: SamplerSettings = Field(default_factory=SamplerSettings)
    game: GameSettings = Field(default_factory=GameSettings)

    model_config = {"env_prefix": "APP_", "env_file": str(BASE_DIR / ".env"), "extra": "ignore"}


# Singleton instance
_settings: Optional[AppSettings] = None


def get_settings() -> AppSettings:
    """Get or create the application settings singleton."""
    global _settings
    if _settings is None:
        _settings = AppSettings()
    return _settings

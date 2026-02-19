"""
Persistent user settings — saves/loads to a local JSON file.
Overrides .env defaults with user-configured values from the settings UI.
"""
import json
import logging
from pathlib import Path
from typing import Any, Optional

from config.settings import BASE_DIR

logger = logging.getLogger(__name__)

CONFIG_FILE = BASE_DIR / "user_config.json"

# Default structure
_DEFAULTS: dict[str, Any] = {
    "api_key": "",
    "model": "",
    "providers": [],
    "instruct_template": "chatml",
    "context_length": 8192,
    "response_length": 1024,
    "temperature": 0.9,
    "top_p": 0.95,
    "top_k": 40,
    "repetition_penalty": 1.1,
    "min_p": 0.05,
}

# In-memory cache
_user_config: Optional[dict[str, Any]] = None


def load_user_config() -> dict[str, Any]:
    """Load user config from JSON file, merging with defaults."""
    global _user_config
    config = dict(_DEFAULTS)

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            config.update(saved)
            logger.info("Loaded user config from %s", CONFIG_FILE)
        except Exception as e:
            logger.warning("Failed to load user config: %s", e)

    _user_config = config
    return config


def save_user_config(config: dict[str, Any]) -> None:
    """Save user config to JSON file."""
    global _user_config
    _user_config = config

    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        logger.info("Saved user config to %s", CONFIG_FILE)
    except Exception as e:
        logger.error("Failed to save user config: %s", e)
        raise


def get_user_config() -> dict[str, Any]:
    """Get the current user config (from cache or file)."""
    global _user_config
    if _user_config is None:
        return load_user_config()
    return _user_config


def apply_user_config_to_settings() -> None:
    """
    Apply user config values onto the runtime Pydantic settings.
    Called on startup and after settings changed from the UI.
    """
    from config.settings import get_settings

    config = get_user_config()
    settings = get_settings()

    if config.get("api_key"):
        settings.llm.openrouter_api_key = config["api_key"]
    if config.get("model"):
        settings.llm.model = config["model"]
    if config.get("context_length"):
        settings.llm.max_context_tokens = config["context_length"]
    if config.get("response_length"):
        settings.llm.max_response_tokens = config["response_length"]
    if config.get("temperature") is not None:
        settings.sampler.temperature = config["temperature"]
    if config.get("top_p") is not None:
        settings.sampler.top_p = config["top_p"]
    if config.get("top_k") is not None:
        settings.sampler.top_k = config["top_k"]
    if config.get("repetition_penalty") is not None:
        settings.sampler.repetition_penalty = config["repetition_penalty"]
    if config.get("min_p") is not None:
        settings.sampler.min_p = config["min_p"]

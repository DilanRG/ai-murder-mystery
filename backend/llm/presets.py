"""
Sampler preset management — load/save/apply preset files.
"""
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from config.settings import SAMPLER_PRESETS_DIR

logger = logging.getLogger(__name__)


@dataclass
class SamplerPreset:
    """A named sampler parameter preset."""

    name: str
    description: str = ""
    temperature: float = 0.9
    top_p: float = 0.95
    top_k: int = 40
    repetition_penalty: float = 1.1
    min_p: float = 0.05

    def to_kwargs(self) -> dict[str, Any]:
        """Convert to kwargs dict for the LLM client."""
        return {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "repetition_penalty": self.repetition_penalty,
            "min_p": self.min_p,
        }

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(
            {
                "name": self.name,
                "description": self.description,
                "temperature": self.temperature,
                "top_p": self.top_p,
                "top_k": self.top_k,
                "repetition_penalty": self.repetition_penalty,
                "min_p": self.min_p,
            },
            indent=2,
        )


def load_preset(name: str) -> SamplerPreset:
    """
    Load a sampler preset by name from the presets directory.

    Args:
        name: Preset name (without .json extension).

    Returns:
        SamplerPreset instance.
    """
    path = SAMPLER_PRESETS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Sampler preset not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return SamplerPreset(**data)


def list_presets() -> list[str]:
    """List all available preset names."""
    if not SAMPLER_PRESETS_DIR.exists():
        return []
    return [p.stem for p in SAMPLER_PRESETS_DIR.glob("*.json")]


def save_preset(preset: SamplerPreset) -> Path:
    """
    Save a preset to the presets directory.

    Returns:
        Path to the saved file.
    """
    SAMPLER_PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    path = SAMPLER_PRESETS_DIR / f"{preset.name.lower().replace(' ', '_')}.json"
    with open(path, "w", encoding="utf-8") as f:
        f.write(preset.to_json())
    logger.info("Saved sampler preset: %s → %s", preset.name, path)
    return path

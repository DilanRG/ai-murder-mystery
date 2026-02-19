"""
Prompt construction with Jinja2 instruct templates,
system prompts, and author's note support.
"""
import logging
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from config.settings import INSTRUCT_PRESETS_DIR, get_settings

logger = logging.getLogger(__name__)

# Jinja2 environment for instruct templates
_jinja_env: Optional[Environment] = None


def _get_jinja_env() -> Environment:
    """Get or create the Jinja2 environment for instruct templates."""
    global _jinja_env
    if _jinja_env is None:
        _jinja_env = Environment(
            loader=FileSystemLoader(str(INSTRUCT_PRESETS_DIR)),
            autoescape=select_autoescape([]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
    return _jinja_env


def render_instruct_prompt(
    messages: list[dict[str, str]],
    template_name: str = "chatml.jinja2",
    author_note: str = "",
    add_generation_prompt: bool = True,
) -> str:
    """
    Render messages through a Jinja2 instruct template.

    Args:
        messages: List of {"role": ..., "content": ...} dicts.
        template_name: Name of the template file in instruct_presets/.
        author_note: Optional author's note to inject.
        add_generation_prompt: Whether to add the assistant prompt prefix.

    Returns:
        Formatted prompt string.
    """
    env = _get_jinja_env()
    template = env.get_template(template_name)
    return template.render(
        messages=messages,
        author_note=author_note,
        add_generation_prompt=add_generation_prompt,
    )


def build_messages(
    system_prompt: str,
    conversation_history: list[dict[str, str]],
    user_message: str = "",
    author_note: str = "",
    author_note_depth: int = 2,
    memory_context: str = "",
) -> list[dict[str, str]]:
    """
    Build a complete message list for the LLM.

    Args:
        system_prompt: The system prompt defining AI behavior.
        conversation_history: Previous messages [{"role":..., "content":...}].
        user_message: The current user/player message (if any).
        author_note: Author's note to inject at a specific depth.
        author_note_depth: How many messages from the end to inject the note.
        memory_context: Retrieved memory context to prepend to system prompt.

    Returns:
        Complete message list ready for the LLM API.
    """
    messages: list[dict[str, str]] = []

    # Build system prompt with memory context
    full_system = system_prompt
    if memory_context:
        full_system = f"{system_prompt}\n\n[Relevant Memory/Context]\n{memory_context}"

    messages.append({"role": "system", "content": full_system})

    # Add conversation history
    history = list(conversation_history)

    # Inject author's note at the specified depth
    if author_note and history:
        insert_idx = max(0, len(history) - author_note_depth)
        history.insert(
            insert_idx,
            {
                "role": "system",
                "content": f"[Author's Note: {author_note}]",
            },
        )

    messages.extend(history)

    # Add current user message
    if user_message:
        messages.append({"role": "user", "content": user_message})

    return messages


def estimate_tokens(text: str) -> int:
    """
    Rough token estimate. ~4 chars per token for English text.
    For precise counting, use tiktoken (loaded lazily).
    """
    return len(text) // 4


def truncate_messages_to_fit(
    messages: list[dict[str, str]],
    max_tokens: int | None = None,
    reserve_for_response: int | None = None,
) -> list[dict[str, str]]:
    """
    Truncate conversation history to fit within the context window.
    Always preserves the system prompt (first message) and the latest user message.

    Args:
        messages: Full message list.
        max_tokens: Max context tokens. Defaults to settings value.
        reserve_for_response: Tokens reserved for the response.

    Returns:
        Truncated message list.
    """
    settings = get_settings()
    if max_tokens is None:
        max_tokens = settings.llm.max_context_tokens
    if reserve_for_response is None:
        reserve_for_response = settings.llm.max_response_tokens

    budget = max_tokens - reserve_for_response

    if not messages:
        return messages

    # Always keep system prompt and latest message
    system_msg = messages[0] if messages[0]["role"] == "system" else None
    latest_msg = messages[-1]
    middle = messages[1:-1] if len(messages) > 2 else []

    used = 0
    if system_msg:
        used += estimate_tokens(system_msg["content"])
    used += estimate_tokens(latest_msg["content"])

    # Add middle messages from most recent backward
    kept_middle: list[dict[str, str]] = []
    for msg in reversed(middle):
        msg_tokens = estimate_tokens(msg["content"])
        if used + msg_tokens <= budget:
            kept_middle.insert(0, msg)
            used += msg_tokens
        else:
            break

    result = []
    if system_msg:
        result.append(system_msg)
    result.extend(kept_middle)
    result.append(latest_msg)

    if len(result) < len(messages):
        logger.info(
            "Truncated context: %d → %d messages (budget: %d tokens)",
            len(messages),
            len(result),
            budget,
        )

    return result

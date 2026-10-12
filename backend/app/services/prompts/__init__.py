"""LLM prompt templates for the roast engine."""

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent

# Bump whenever the system prompt, user prompt, tool schema, or roast post-processing changes in a
# way that should produce a different roast. Part of the dedupe key, so old roasts aren't reused.
PROMPT_VERSION = "2026-10-12.1"


@lru_cache
def load_prompt(name: str) -> str:
    """Load a prompt template file shipped in this package.

    Args:
        name: File name inside ``app/services/prompts`` (e.g. ``"system_prompt.md"``).

    Returns:
        The file's text with surrounding whitespace stripped.
    """
    path = (PROMPTS_DIR / name).resolve()
    if path.parent != PROMPTS_DIR:
        raise ValueError(f"Invalid prompt name: {name!r}")
    return path.read_text(encoding="utf-8").strip()


def load_system_prompt() -> str:
    """Return the roast engine's system prompt."""
    return load_prompt("system_prompt.md")

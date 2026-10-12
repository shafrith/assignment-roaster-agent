"""Thin wrapper around the Anthropic client with retries and usage logging."""

import logging
import os
from pathlib import Path

import anthropic
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent / "prompts" / "answer.txt"
MODEL_NAME = os.environ.get("MODEL_NAME", "")
MAX_TOKENS = 1024

_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


def build_prompt(question: str, context: list[str]) -> str:
    """Render the answer prompt template."""
    template = PROMPT_PATH.read_text(encoding="utf-8")
    return template.format(context="\n\n".join(context), question=question)


@retry(
    retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.APIConnectionError)),
    wait=wait_exponential(min=1, max=20),
    stop=stop_after_attempt(3),
)
def ask_model(prompt: str) -> str:
    """Call the model and return the text answer."""
    try:
        response = _client.messages.create(
            model=MODEL_NAME,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIStatusError:
        logger.exception("Model call failed")
        raise
    logger.info(
        "usage input=%d output=%d", response.usage.input_tokens, response.usage.output_tokens
    )
    return "".join(block.text for block in response.content if block.type == "text")

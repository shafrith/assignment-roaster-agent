"""Generate a structured Tanglish roast of an analyzed repository with OpenAI.

The model must answer by calling the strict ``submit_roast`` function (forced ``tool_choice``).
The arguments are validated (and length-bounded) with :class:`RoastOutput`; invalid or missing
output is retried once, while a refusal, content filter or ``length`` truncation fails
immediately with :class:`RoastGenerationError`. Score
rules that matter for fairness (0-10 clamp, the committed-secret cap, the prompt-injection cap)
are enforced here in code, not left to the model, and every output string is run through the
secret scanner before it is returned.

Prompt contents are never logged: they contain (redacted) third-party repository code.
"""

import json
import logging
from collections.abc import Callable
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import openai
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    field_validator,
)

from app.config import settings
from app.services.contracts import (
    AnalysisResult,
    Finding,
    IssueCategory,
    RepoInfo,
    RoastGenerationError,
    RoastResult,
    Severity,
)
from app.services.prompts import load_system_prompt
from app.services.prompts.user_prompt import build_user_prompt
from app.services.repo_analyzer import INJECTION_MESSAGE, PATH_INJECTION_MESSAGE
from app.services.secret_scanner import scan_and_redact

logger = logging.getLogger(__name__)

TOOL_NAME = "submit_roast"
# Worst-case wall time per roast = timeout x (SDK retries + 1) x MAX_ATTEMPTS = 120 x 2 x 2 = 8 min,
# which stays under the pipeline's stale-submission cutoff.
REQUEST_TIMEOUT_SECONDS = 120.0
SDK_MAX_RETRIES = 1
MAX_ATTEMPTS = 2  # initial call + one retry on invalid/missing tool output (never on refusal)
# A roast needs ~2-4K output tokens; the cap bounds cost if the model rambles.
ROAST_MAX_TOKENS = 8_000
UNUSABLE_FINISH_REASONS = frozenset({"length", "content_filter"})

SECRET_SCORE_CAP = Decimal("4.0")
# A detected prompt-injection attempt can never be rewarded with a near-perfect score, whatever
# the model was persuaded to output.
INJECTION_SCORE_CAP = Decimal("8.0")
SCORE_MIN = Decimal("0.0")
SCORE_MAX = Decimal("10.0")

# Output bounds (QUAL-4): everything below is stored in Postgres and shown on public pages.
VERDICT_MAX_LENGTH = 120
ROAST_TEXT_MAX_LENGTH = 6_000
ITEM_MAX_LENGTH = 500
FILE_MAX_LENGTH = 300
MAX_STRENGTHS = 8
MAX_ISSUES = 15
MAX_FIX_TIPS = 10

_INJECTION_MESSAGES = frozenset({INJECTION_MESSAGE, PATH_INJECTION_MESSAGE})

CATEGORIES: list[str] = [
    "structure",
    "documentation",
    "dependencies",
    "testing",
    "security",
    "code_quality",
    "git_hygiene",
    "genai_practices",
]
SEVERITIES: list[str] = ["low", "medium", "high", "critical"]
_MIN_ITEMS: dict[str, int] = {"strengths": 1, "fix_tips": 3}
_MAX_ITEMS: dict[str, int] = {"strengths": MAX_STRENGTHS, "fix_tips": MAX_FIX_TIPS}


def _clip(value: str, limit: int) -> str:
    """Cut ``value`` to at most ``limit`` characters, marking the cut with an ellipsis."""
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


# Strict function calling guarantees schema-valid arguments. Strict mode does not support
# numeric, string length, or array-size constraints, so those limits live in the descriptions
# and are enforced by RoastOutput (Pydantic) after the call.
ROAST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["score", "verdict_title", "roast_text", "strengths", "issues", "fix_tips"],
    "properties": {
        "score": {
            "type": "number",
            "description": "Score from 0 to 10 with at most one decimal.",
        },
        "verdict_title": {
            "type": "string",
            "description": f"Short Tanglish nickname (~6 words, <={VERDICT_MAX_LENGTH} chars).",
        },
        "roast_text": {
            "type": "string",
            "description": "Tanglish markdown roast, 150-400 words.",
        },
        "strengths": {
            "type": "array",
            "items": {"type": "string"},
            "description": f"1-{MAX_STRENGTHS} genuine, specific strengths.",
        },
        "issues": {
            "type": "array",
            "description": f"The most important problems (typically 3-8, max {MAX_ISSUES}).",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["category", "severity", "file", "message"],
                "properties": {
                    "category": {"type": "string", "enum": CATEGORIES},
                    "severity": {"type": "string", "enum": SEVERITIES},
                    "file": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Repo path the issue is about, or null.",
                    },
                    "message": {"type": "string"},
                },
            },
        },
        "fix_tips": {
            "type": "array",
            "items": {"type": "string"},
            "description": f"3-{MAX_FIX_TIPS} actionable fixes, most impactful first.",
        },
    },
}

ROAST_TOOL: ChatCompletionToolParam = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": (
            "Submit the final roast of the repository. Call this exactly once with the score, "
            "verdict title, Tanglish markdown roast, strengths, issues, and fix tips."
        ),
        "strict": True,
        "parameters": ROAST_SCHEMA,
    },
}

ClientFactory = Callable[[], AsyncOpenAI]


# ---------------------------------------------------------------------------- output validation


class RoastIssueOutput(BaseModel):
    """One issue as returned by the model."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    category: IssueCategory
    severity: Severity
    file: str | None = None
    message: str = Field(min_length=1)

    @field_validator("file", mode="before")
    @classmethod
    def blank_file_is_none(cls, value: Any) -> Any:
        """Treat ``""`` as no file."""
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("file")
    @classmethod
    def clip_file(cls, value: str | None) -> str | None:
        """Bound the file path length."""
        return None if value is None else _clip(value, FILE_MAX_LENGTH)

    @field_validator("message")
    @classmethod
    def clip_message(cls, value: str) -> str:
        """Bound the message length."""
        return _clip(value, ITEM_MAX_LENGTH)


class RoastOutput(BaseModel):
    """Validated ``submit_roast`` function arguments."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    score: float = Field(allow_inf_nan=False)
    verdict_title: str = Field(min_length=1)
    roast_text: str = Field(min_length=1)
    strengths: list[str] = Field(min_length=1)
    issues: list[RoastIssueOutput]
    fix_tips: list[str] = Field(min_length=3)

    @field_validator("strengths", "issues", "fix_tips", mode="before")
    @classmethod
    def parse_json_string_lists(cls, value: Any) -> Any:
        """Accept a list that the model serialized as a JSON string."""
        if isinstance(value, str):
            try:
                return json.loads(value)
            except ValueError:
                return value
        return value

    @field_validator("strengths", "fix_tips")
    @classmethod
    def drop_blank_items(cls, value: list[str], info: ValidationInfo) -> list[str]:
        """Remove empty strings, then re-check the minimum item count on the real items.

        (``Field(min_length=...)`` runs before this validator, so it alone would accept
        ``["", "", ""]``.)
        """
        cleaned = [item.strip() for item in value if item and item.strip()]
        name = str(info.field_name)
        minimum = _MIN_ITEMS[name]
        if len(cleaned) < minimum:
            raise ValueError(f"needs at least {minimum} non-empty item(s)")
        return [_clip(item, ITEM_MAX_LENGTH) for item in cleaned[: _MAX_ITEMS[name]]]

    @field_validator("issues")
    @classmethod
    def clip_issues(cls, value: list[RoastIssueOutput]) -> list[RoastIssueOutput]:
        """Keep at most :data:`MAX_ISSUES` issues."""
        return value[:MAX_ISSUES]

    @field_validator("verdict_title")
    @classmethod
    def clip_verdict(cls, value: str) -> str:
        """Clip the title to the DB column length."""
        return value[:VERDICT_MAX_LENGTH].strip()

    @field_validator("roast_text")
    @classmethod
    def clip_roast_text(cls, value: str) -> str:
        """Bound the roast length (the prompt asks for 150-400 words, ~3K chars)."""
        return _clip(value, ROAST_TEXT_MAX_LENGTH)


# ---------------------------------------------------------------------------- pure helpers


def has_committed_secret(analysis: AnalysisResult) -> bool:
    """True when the analyzer found a real secret committed to the repo."""
    return analysis.secrets_found_count > 0 or any(
        f.category == "security" and f.severity == "critical" for f in analysis.findings
    )


def has_injection_attempt(analysis: AnalysisResult) -> bool:
    """True when the analyzer deterministically flagged a prompt-injection attempt."""
    return any(
        f.category == "security" and f.message in _INJECTION_MESSAGES for f in analysis.findings
    )


def normalize_score(raw: float, analysis: AnalysisResult) -> Decimal:
    """Clamp to [0, 10], round to one decimal, and apply the secret and injection caps."""
    score = Decimal(str(raw)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    score = max(SCORE_MIN, min(SCORE_MAX, score))
    if has_committed_secret(analysis):
        score = min(score, SECRET_SCORE_CAP)
    if has_injection_attempt(analysis) and score > INJECTION_SCORE_CAP:
        logger.warning(
            "Model scored %s despite a detected prompt-injection attempt; capping at %s",
            score,
            INJECTION_SCORE_CAP,
        )
        score = INJECTION_SCORE_CAP
    return score


def redact_output(output: RoastOutput) -> tuple[RoastOutput, int]:
    """Run the secret scanner over every string the model produced (defence in depth).

    Repo content is redacted before prompting, but the model could still reconstruct or echo a
    key-like string; nothing it writes reaches the DB or the public page unscanned.

    Returns:
        ``(redacted_output, secrets_found)``.
    """
    found = 0

    def scrub(text: str) -> str:
        nonlocal found
        redacted, count = scan_and_redact(text)
        found += count
        return redacted

    issues = [
        issue.model_copy(
            update={
                "message": scrub(issue.message),
                "file": None if issue.file is None else scrub(issue.file),
            }
        )
        for issue in output.issues
    ]
    redacted = output.model_copy(
        update={
            "verdict_title": scrub(output.verdict_title),
            "roast_text": scrub(output.roast_text),
            "strengths": [scrub(s) for s in output.strengths],
            "fix_tips": [scrub(t) for t in output.fix_tips],
            "issues": issues,
        }
    )
    return redacted, found


def merge_critical_findings(issues: list[Finding], analysis: AnalysisResult) -> list[Finding]:
    """Ensure every critical analyzer finding is present in the roast's issues."""
    merged = list(issues)
    for finding in analysis.findings:
        if finding.severity != "critical":
            continue
        covered = any(
            i.severity == "critical" and i.category == finding.category and i.file == finding.file
            for i in merged
        )
        if not covered:
            merged.insert(0, finding)
    return merged


class UnusableResponseError(ValueError):
    """The response was refused or truncated; re-sending the identical request won't help."""


def parse_roast_response(response: Any) -> RoastOutput:
    """Extract and validate the ``submit_roast`` arguments from a Chat Completions response.

    Raises:
        UnusableResponseError: If the model refused, was filtered, or hit the token limit.
        ValueError: If the response has no ``submit_roast`` call or its arguments aren't JSON.
        ValidationError: If the arguments do not match :class:`RoastOutput`.
    """
    choices = getattr(response, "choices", None) or []
    if not choices:
        raise ValueError("no choices in response")
    choice = choices[0]
    finish_reason = getattr(choice, "finish_reason", None)
    if finish_reason in UNUSABLE_FINISH_REASONS:
        raise UnusableResponseError(f"unusable finish_reason: {finish_reason}")
    message = getattr(choice, "message", None)
    if getattr(message, "refusal", None):
        raise UnusableResponseError("model refused")
    for call in getattr(message, "tool_calls", None) or []:
        function = getattr(call, "function", None)
        if getattr(function, "name", None) == TOOL_NAME:
            return RoastOutput.model_validate(json.loads(function.arguments))
    raise ValueError("no submit_roast tool call in response")


def _usage_tokens(response: Any) -> tuple[int, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0

    def _int(name: str) -> int:
        value = getattr(usage, name, 0)
        return value if isinstance(value, int) else 0

    return _int("prompt_tokens"), _int("completion_tokens")


def _finish_reason(response: Any) -> str | None:
    choices = getattr(response, "choices", None) or []
    return getattr(choices[0], "finish_reason", None) if choices else None


def _default_client_factory() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=SDK_MAX_RETRIES,
    )


client_factory: ClientFactory = _default_client_factory
"""Module-level factory; tests may monkeypatch it (or pass ``client=`` directly)."""


# ---------------------------------------------------------------------------- orchestration


async def _request_roast(client: AsyncOpenAI, system_prompt: str, user_prompt: str) -> Any:
    # Forced function call: the model must answer through submit_roast (strict schema). Parallel
    # calls are disabled because strict structured outputs do not support them.
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    return await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        max_completion_tokens=ROAST_MAX_TOKENS,
        messages=messages,
        tools=[ROAST_TOOL],
        tool_choice={"type": "function", "function": {"name": TOOL_NAME}},
        parallel_tool_calls=False,
    )


async def generate_roast(
    info: RepoInfo,
    analysis: AnalysisResult,
    *,
    client: AsyncOpenAI | None = None,
) -> RoastResult:
    """Ask the model for a structured Tanglish roast of an analyzed repo.

    Args:
        info: Repository metadata.
        analysis: Analyzer output (sampled contents already redacted).
        client: Optional OpenAI client (tests). When omitted, one is created from
            :data:`client_factory` and closed afterwards.

    Returns:
        The validated :class:`RoastResult`.

    Raises:
        RoastGenerationError: Missing API key, API failure, or invalid output after one retry.
    """
    owns_client = client is None
    if client is None:
        if not settings.OPENAI_API_KEY:
            logger.error("OPENAI_API_KEY is not configured; cannot generate roast")
            raise RoastGenerationError()
        client = client_factory()

    repo_label = f"{info.owner}/{info.name}@{info.head_sha[:7]}"
    system_prompt = load_system_prompt()
    user_prompt = build_user_prompt(info, analysis)
    total_in = total_out = 0
    model_used = settings.OPENAI_MODEL
    output: RoastOutput | None = None

    try:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = await _request_roast(client, system_prompt, user_prompt)
            except openai.APIError as exc:  # timeouts, connection, rate limit, status errors
                logger.exception("OpenAI API error for %s (%s)", repo_label, type(exc).__name__)
                raise RoastGenerationError() from exc

            in_tokens, out_tokens = _usage_tokens(response)
            total_in += in_tokens
            total_out += out_tokens
            response_model = getattr(response, "model", None)
            if isinstance(response_model, str) and response_model:
                model_used = response_model

            try:
                output = parse_roast_response(response)
                break
            except UnusableResponseError:
                # A refusal, content filter or truncation would just repeat with an identical
                # request, so fail cleanly instead of paying for it twice.
                logger.warning(
                    "Unusable roast response for %s (finish_reason=%s); not retrying",
                    repo_label,
                    _finish_reason(response),
                )
                break
            except (ValueError, ValidationError) as exc:
                error_count = exc.error_count() if isinstance(exc, ValidationError) else 1
                logger.warning(
                    "Invalid roast output for %s (attempt %d/%d, finish_reason=%s, errors=%d)",
                    repo_label,
                    attempt,
                    MAX_ATTEMPTS,
                    _finish_reason(response),
                    error_count,
                )
    finally:
        if owns_client:
            await client.close()

    if output is None:
        logger.error("Roast generation failed for %s", repo_label)
        raise RoastGenerationError()

    output, leaked = redact_output(output)
    if leaked:
        logger.warning(
            "Redacted %d secret-like string(s) from the model output for %s", leaked, repo_label
        )

    issues = [
        Finding(category=i.category, severity=i.severity, message=i.message, file=i.file)
        for i in output.issues
    ]
    result = RoastResult(
        score=normalize_score(output.score, analysis),
        verdict_title=output.verdict_title,
        roast_text=output.roast_text,
        strengths=output.strengths,
        issues=merge_critical_findings(issues, analysis),
        fix_tips=output.fix_tips,
        model=model_used,
        input_tokens=total_in,
        output_tokens=total_out,
    )
    logger.info(
        "Roast generated for %s: score=%s model=%s input_tokens=%d output_tokens=%d",
        repo_label,
        result.score,
        result.model,
        result.input_tokens,
        result.output_tokens,
    )
    return result

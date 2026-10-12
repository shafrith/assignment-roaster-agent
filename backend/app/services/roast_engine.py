"""Generate a structured Tanglish roast of an analyzed repository with Claude.

Claude must answer through the strict ``submit_roast`` tool. The tool input is validated (and
length-bounded) with :class:`RoastOutput`; invalid or missing output is retried once, while a
refusal or ``max_tokens`` truncation fails immediately with :class:`RoastGenerationError`. Score
rules that matter for fairness (0-10 clamp, the committed-secret cap, the prompt-injection cap)
are enforced here in code, not left to the model, and every output string is run through the
secret scanner before it is returned.

Prompt contents are never logged: they contain (redacted) third-party repository code.
"""

import json
import logging
from collections.abc import Callable
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal

import anthropic
from anthropic import AsyncAnthropic
from anthropic.types import MessageParam, TextBlockParam, ToolChoiceAutoParam, ToolParam
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
# Thinking is always on for current models and counts toward max_tokens; 16K is the recommended
# non-streaming ceiling and leaves ample headroom above the ~2-4K tokens a roast needs.
ROAST_MAX_TOKENS = 16_000
# A roast is a bounded, single-shot review: "medium" keeps cost/latency predictable (the default
# differs per model, so it is set explicitly). Re-measure on real repos before raising it.
ROAST_EFFORT: Literal["low", "medium", "high"] = "medium"
# Server-side refusal fallback: a classifier decline is re-run on Anthropic's recommended fallback
# model inside the same call instead of us re-sending an identical request.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
UNUSABLE_STOP_REASONS = frozenset({"max_tokens", "refusal"})

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


# Strict tool use guarantees schema-valid input. Strict mode does not support numeric, string
# length, or array-size constraints, so those limits live in the descriptions and are enforced by
# RoastOutput (Pydantic) after the call.
ROAST_TOOL: ToolParam = {
    "name": TOOL_NAME,
    "description": (
        "Submit the final roast of the repository. Call this exactly once with the score, "
        "verdict title, Tanglish markdown roast, strengths, issues, and fix tips."
    ),
    "strict": True,
    "input_schema": {
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
    },
}

ClientFactory = Callable[[], AsyncAnthropic]


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
    """Validated ``submit_roast`` tool input."""

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
    """Extract and validate the ``submit_roast`` tool input from a Messages API response.

    Raises:
        UnusableResponseError: If the response was refused or hit ``max_tokens``.
        ValueError: If the response has no ``submit_roast`` call.
        ValidationError: If the tool input does not match :class:`RoastOutput`.
    """
    stop_reason = getattr(response, "stop_reason", None)
    if stop_reason in UNUSABLE_STOP_REASONS:
        raise UnusableResponseError(f"unusable stop_reason: {stop_reason}")
    for block in getattr(response, "content", None) or []:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == TOOL_NAME:
            return RoastOutput.model_validate(block.input)
    raise ValueError("no submit_roast tool call in response")


def _usage_tokens(response: Any) -> tuple[int, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0

    def _int(name: str) -> int:
        value = getattr(usage, name, 0)
        return value if isinstance(value, int) else 0

    input_tokens = (
        _int("input_tokens") + _int("cache_creation_input_tokens") + _int("cache_read_input_tokens")
    )
    return input_tokens, _int("output_tokens")


def _default_client_factory() -> AsyncAnthropic:
    return AsyncAnthropic(
        api_key=settings.ANTHROPIC_API_KEY,
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=SDK_MAX_RETRIES,
    )


client_factory: ClientFactory = _default_client_factory
"""Module-level factory; tests may monkeypatch it (or pass ``client=`` directly)."""


# ---------------------------------------------------------------------------- orchestration


async def _request_roast(client: AsyncAnthropic, system_prompt: str, user_prompt: str) -> Any:
    # Current models (e.g. Sonnet 5.5 / Opus 5.5) reject forced tool_choice, so we use "auto"
    # with a single allowed call; the system prompt requires calling submit_roast, and a missing
    # call is treated as invalid output and retried.
    system: list[TextBlockParam] = [
        {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}
    ]
    tool_choice: ToolChoiceAutoParam = {"type": "auto", "disable_parallel_tool_use": True}
    messages: list[MessageParam] = [{"role": "user", "content": user_prompt}]
    # Thinking is left at the model default (adaptive; it cannot be disabled on current models).
    # The refusal fallback is a beta body field, sent via extra_headers/extra_body so the call
    # stays on the stable ``messages`` surface.
    return await client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=ROAST_MAX_TOKENS,
        system=system,
        tools=[ROAST_TOOL],
        tool_choice=tool_choice,
        messages=messages,
        output_config={"effort": ROAST_EFFORT},
        extra_headers={"anthropic-beta": FALLBACK_BETA},
        extra_body={"fallbacks": "default"},
    )


async def generate_roast(
    info: RepoInfo,
    analysis: AnalysisResult,
    *,
    client: AsyncAnthropic | None = None,
) -> RoastResult:
    """Ask Claude for a structured Tanglish roast of an analyzed repo.

    Args:
        info: Repository metadata.
        analysis: Analyzer output (sampled contents already redacted).
        client: Optional Anthropic client (tests). When omitted, one is created from
            :data:`client_factory` and closed afterwards.

    Returns:
        The validated :class:`RoastResult`.

    Raises:
        RoastGenerationError: Missing API key, API failure, or invalid output after one retry.
    """
    owns_client = client is None
    if client is None:
        if not settings.ANTHROPIC_API_KEY:
            logger.error("ANTHROPIC_API_KEY is not configured; cannot generate roast")
            raise RoastGenerationError()
        client = client_factory()

    repo_label = f"{info.owner}/{info.name}@{info.head_sha[:7]}"
    system_prompt = load_system_prompt()
    user_prompt = build_user_prompt(info, analysis)
    total_in = total_out = 0
    model_used = settings.ANTHROPIC_MODEL
    output: RoastOutput | None = None

    try:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = await _request_roast(client, system_prompt, user_prompt)
            except (
                anthropic.APITimeoutError,
                anthropic.APIConnectionError,
                anthropic.RateLimitError,
                anthropic.APIStatusError,
                anthropic.APIError,
            ) as exc:
                logger.exception("Claude API error for %s (%s)", repo_label, type(exc).__name__)
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
                # A refusal (after the server-side fallback) or a truncation would just repeat
                # with an identical request, so fail cleanly instead of paying for it twice.
                stop_details = getattr(response, "stop_details", None)
                logger.warning(
                    "Unusable roast response for %s (stop_reason=%s, category=%s); not retrying",
                    repo_label,
                    getattr(response, "stop_reason", None),
                    getattr(stop_details, "category", None),
                )
                break
            except (ValueError, ValidationError) as exc:
                error_count = exc.error_count() if isinstance(exc, ValidationError) else 1
                logger.warning(
                    "Invalid roast output for %s (attempt %d/%d, stop_reason=%s, errors=%d)",
                    repo_label,
                    attempt,
                    MAX_ATTEMPTS,
                    getattr(response, "stop_reason", None),
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

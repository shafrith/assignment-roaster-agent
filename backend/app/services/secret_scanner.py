"""Detect and redact credentials in repository content (and in LLM output, as defence in depth).

Every piece of repo content that is stored, logged, or sent to the LLM passes through
:func:`scan_and_redact` first. Only match COUNTS ever leave this module, never the values.

Detection layers, applied in order:

1. Private key blocks (``-----BEGIN ... PRIVATE KEY-----`` through the matching END line).
2. Provider token formats (Anthropic, OpenAI, Groq, Stripe, Slack, GitHub, AWS, Google, HF, JWT).
3. Credentials embedded in URLs (``postgresql://user:PASSWORD@host``) - only the password part.
4. ``Authorization: Bearer <token>`` headers.
5. Generic ``*_api_key`` / ``*secret*`` / ``*token`` / ``*password`` assignments, quoted or not.
6. For committed dotenv files (:func:`is_env_file`), every remaining non-placeholder value.

All patterns are precompiled and bounded, with no nested quantifiers, so scanning stays linear in
the input size even for large or adversarial files.
"""

import posixpath
import re
from dataclasses import dataclass

REDACTED = "[REDACTED_SECRET]"

# Upper bound on a single token match; real keys are far shorter. Bounding keeps matching cheap.
_MAX = 512
_MAX_JWT_PART = 4096
_MAX_KEY_BLOCK = 16_384

ENV_TEMPLATE_SUFFIXES = (".example", ".sample", ".template", ".dist", ".defaults")

# ---------------------------------------------------------------------------- path helpers


def is_env_file(path: str) -> bool:
    """Return True for committed dotenv files (``.env``, ``.env.local``), not templates.

    This is the single source of truth used by both the scanner and the repo analyzer.
    """
    base = posixpath.basename(path).lower()
    if base != ".env" and not base.startswith(".env."):
        return False
    return not base.endswith(ENV_TEMPLATE_SUFFIXES)


def is_env_template(path: str) -> bool:
    """Return True for ``.env.example``-style templates."""
    base = posixpath.basename(path).lower()
    return base.startswith(".env") and base.endswith(ENV_TEMPLATE_SUFFIXES)


# ---------------------------------------------------------------------------- patterns

_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN (?:[A-Z0-9]{1,16} ){0,3}PRIVATE KEY(?: BLOCK)?-----"
    # Either the whole block up to its END marker, or (truncated file / no END) the base64 body.
    rf"(?:[\s\S]{{0,{_MAX_KEY_BLOCK}}}?-----END (?:[A-Z0-9]{{1,16}} ){{0,3}}PRIVATE KEY"
    rf"(?: BLOCK)?-----|[A-Za-z0-9+/=\s\\:-]{{0,{_MAX_KEY_BLOCK}}})"
)

# Provider-specific token formats. The look-behind stops matches in the middle of words such as
# ``disk-...`` or ``task-...``.
_PROVIDER_PATTERNS: tuple[str, ...] = (
    rf"sk-ant-[A-Za-z0-9_-]{{20,{_MAX}}}",
    # Current OpenAI project/service-account/admin keys contain '-' and '_'.
    rf"sk-(?:proj|svcacct|admin)-[A-Za-z0-9_-]{{20,{_MAX}}}",
    rf"sk-[A-Za-z0-9_-]{{32,{_MAX}}}",
    rf"sk-[A-Za-z0-9]{{20,{_MAX}}}",
    rf"gsk_[A-Za-z0-9]{{40,{_MAX}}}",  # Groq
    rf"(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{{20,{_MAX}}}",  # Stripe secret / restricted keys
    rf"xox[abprs]-[A-Za-z0-9-]{{10,{_MAX}}}",  # Slack
    rf"gh[pousr]_[A-Za-z0-9]{{36,{_MAX}}}",  # GitHub PAT / OAuth / app tokens
    rf"github_pat_\w{{20,{_MAX}}}",
    r"(?:AKIA|ASIA)[0-9A-Z]{16}",  # AWS access key id
    r"AIza[0-9A-Za-z_-]{35}",  # Google API key
    rf"hf_[A-Za-z0-9]{{30,{_MAX}}}",  # Hugging Face
    # JSON Web Tokens (header.payload.signature, header always starts with '{"' -> eyJ).
    rf"eyJ[A-Za-z0-9_-]{{10,{_MAX_JWT_PART}}}\.[A-Za-z0-9_-]{{10,{_MAX_JWT_PART}}}"
    rf"\.[A-Za-z0-9_-]{{10,{_MAX_JWT_PART}}}",
)

_PROVIDER_RE = re.compile(
    r"(?<![A-Za-z0-9_-])(?:" + "|".join(f"(?:{p})" for p in _PROVIDER_PATTERNS) + ")"
)

# scheme://user:password@ - only the password is redacted so the roast can still say "DB URL".
_URL_CREDENTIALS_RE = re.compile(
    r"(?P<prefix>(?<![A-Za-z0-9+.-])[A-Za-z][A-Za-z0-9+.-]{1,20}://[^\s:/@'\"`<>]{0,128}:)"
    rf"(?P<password>[^\s@/'\"`<>]{{1,{_MAX}}})(?=@)"
)

_BEARER_RE = re.compile(
    rf"(?P<prefix>(?<![A-Za-z0-9])[Bb]earer\s{{1,4}})(?P<token>[A-Za-z0-9_\-.=+/~]{{20,{_MAX}}})"
)

# Generic secret-ish assignments: an identifier ENDING in a secret-ish word (``client_secret``,
# ``DB_PASSWORD``, ``aws_secret_access_key``, ``openai.api_key``, ``authToken``), then ``=``/``:``,
# then a quoted or bare value. The match starts at the keyword (a literal, so the regex engine can
# skip ahead quickly); any identifier prefix is left untouched. Only the value is redacted so the
# roast can still say *which* variable leaked.
_SECRET_WORD = (
    r"(?:api[_-]?key|secret(?:[_-]?key)?|token|password|passwd|pwd|access[_-]?key"
    r"|private[_-]?key)"
)
_UNQUOTED_CHARS = r"A-Za-z0-9_\-+/=~"
_GENERIC_RE = re.compile(
    rf"(?P<name>{_SECRET_WORD})(?P<nq>['\"]?)"
    r"(?P<sep>\s{0,8}(?::=|=>|[:=])\s{0,8})"
    rf"(?:(?P<quote>['\"`])(?P<value>[^'\"`\r\n]{{12,{_MAX}}})(?P=quote)"
    rf"|(?P<bare>[{_UNQUOTED_CHARS}]{{12,{_MAX}}})(?![{_UNQUOTED_CHARS}.(\[{{]))",
    re.IGNORECASE,
)
# Dotenv variable names whose value always counts as a secret.
_ENV_SECRET_NAME_RE = re.compile(
    r"key|secret|token|pass|pwd|auth|credential|private|signature|salt", re.IGNORECASE
)

# ``KEY=value`` lines in dotenv files.
_ENV_LINE_RE = re.compile(
    r"^(?P<prefix>[ \t]{0,16}(?:export[ \t]{1,8})?(?P<name>[A-Za-z_][A-Za-z0-9_.-]{0,128})"
    r"[ \t]{0,8}=[ \t]{0,8})(?P<value>[^\r\n]+)$",
    re.MULTILINE,
)
_BENIGN_ENV_VALUE_RE = re.compile(
    r"^(?:true|false|yes|no|on|off|none|null|debug|info|warning|error|development|production|"
    r"staging|test|local|localhost|[0-9]{1,10}(?:\.[0-9]{1,10})?)$",
    re.IGNORECASE,
)

# Values that are obviously placeholders, not real credentials.
_PLACEHOLDER_HINTS = (
    "your",
    "xxx",
    "***",
    "example",
    "changeme",
    "change-me",
    "change_me",
    "placeholder",
    "dummy",
    "replace",
    "insert",
    "<",
    "${",
    "{{",
    "...",
    "os.environ",
    "getenv",
    "process.env",
    "redacted",
)

# URL passwords that are clearly local-dev defaults (docker-compose, tutorials), not secrets.
_TRIVIAL_PASSWORDS = frozenset(
    {"password", "pass", "passwd", "postgres", "root", "admin", "secret", "user", "test",
     "example", "changeme", "guest", "mysql", "redis", "mongo", "roaster"}
)  # fmt: skip


@dataclass(frozen=True)
class ScanResult:
    """Result of scanning a text: redacted text and how many secrets were found."""

    redacted: str
    count: int


def _is_placeholder(value: str) -> bool:
    lowered = value.lower()
    if any(hint in lowered for hint in _PLACEHOLDER_HINTS):
        return True
    # "aaaaaaaaaaaa", "000000000000", "------------"
    return len(set(lowered)) <= 2


def _looks_like_credential(value: str) -> bool:
    """A bare value that mixes letters and digits, as keys and passwords usually do."""
    has_alpha = any(c.isalpha() for c in value)
    has_digit = any(c.isdigit() for c in value)
    return has_alpha and has_digit


def _strip_env_value(raw: str) -> tuple[str, str, str]:
    """Split a dotenv value into ``(quote, value, trailing)`` (trailing = closing quote/comment)."""
    stripped = raw.rstrip()
    trailing_ws = raw[len(stripped) :]
    if stripped[:1] in {"'", '"'} and len(stripped) >= 2:
        quote = stripped[0]
        end = stripped.find(quote, 1)
        if end != -1:
            return quote, stripped[1:end], stripped[end:] + trailing_ws
        return quote, stripped[1:], trailing_ws
    comment = re.search(r"\s#", stripped)
    if comment:
        return "", stripped[: comment.start()], stripped[comment.start() :] + trailing_ws
    return "", stripped, trailing_ws


def scan_text(text: str, path: str | None = None) -> ScanResult:
    """Redact credentials in ``text``.

    Args:
        text: Arbitrary (possibly huge) text from a repository file or from model output.
        path: Repository path of ``text`` when known. Committed dotenv files get every
            non-placeholder value redacted line by line.

    Returns:
        A :class:`ScanResult` with the redacted text and the number of secrets replaced.
    """
    if not text:
        return ScanResult(redacted=text, count=0)

    count = 0
    redacted, found = _PRIVATE_KEY_RE.subn(REDACTED, text)
    count += found
    redacted, found = _PROVIDER_RE.subn(REDACTED, redacted)
    count += found

    def _replace_url(match: re.Match[str]) -> str:
        nonlocal count
        password = match.group("password")
        if (
            REDACTED in password
            or _is_placeholder(password)
            or password.lower() in _TRIVIAL_PASSWORDS
        ):
            return match.group(0)
        count += 1
        return match.group("prefix") + REDACTED

    redacted = _URL_CREDENTIALS_RE.sub(_replace_url, redacted)

    def _replace_bearer(match: re.Match[str]) -> str:
        nonlocal count
        token = match.group("token")
        if _is_placeholder(token) or not _looks_like_credential(token):
            return match.group(0)
        count += 1
        return match.group("prefix") + REDACTED

    redacted = _BEARER_RE.sub(_replace_bearer, redacted)

    def _replace_generic(match: re.Match[str]) -> str:
        nonlocal count
        head = f"{match.group('name')}{match.group('nq')}{match.group('sep')}"
        quote = match.group("quote")
        if quote is not None:
            value = match.group("value")
            if REDACTED in value or _is_placeholder(value):
                return match.group(0)
            count += 1
            return f"{head}{quote}{REDACTED}{quote}"
        bare = match.group("bare")
        if _is_placeholder(bare) or not _looks_like_credential(bare):
            return match.group(0)
        count += 1
        return f"{head}{REDACTED}"

    redacted = _GENERIC_RE.sub(_replace_generic, redacted)

    if path is not None and is_env_file(path):

        def _replace_env(match: re.Match[str]) -> str:
            nonlocal count
            quote, value, trailing = _strip_env_value(match.group("value"))
            value_stripped = value.strip()
            if (
                not value_stripped
                or REDACTED in value_stripped
                or _is_placeholder(value_stripped)
                or _BENIGN_ENV_VALUE_RE.match(value_stripped)
            ):
                return match.group(0)
            if _ENV_SECRET_NAME_RE.search(match.group("name")) or (
                len(value_stripped) >= 16 and _looks_like_credential(value_stripped)
            ):
                count += 1
            # Everything else is still redacted (hosts, model names, ...): a committed .env is
            # never safe to forward verbatim, but only credential-like values count as secrets.
            return f"{match.group('prefix')}{quote}{REDACTED}{trailing}"

        redacted = _ENV_LINE_RE.sub(_replace_env, redacted)

    return ScanResult(redacted=redacted, count=count)


def scan_and_redact(text: str, path: str | None = None) -> tuple[str, int]:
    """Replace every detected secret in ``text`` with ``[REDACTED_SECRET]``.

    Args:
        text: Repository content (or model output).
        path: Repository path of ``text``, when known (enables dotenv line redaction).

    Returns:
        ``(redacted_text, secrets_found)``.
    """
    result = scan_text(text, path)
    return result.redacted, result.count

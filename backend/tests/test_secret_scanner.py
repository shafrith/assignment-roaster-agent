"""Secret scanner: every pattern is redacted, placeholders are not, counts are exact."""

import time

import pytest

from app.services.secret_scanner import REDACTED, scan_and_redact, scan_text

ANTHROPIC_KEY = "sk-ant-api03-" + "A1b2C3d4E5f6G7h8I9j0" * 3
OPENAI_LEGACY_KEY = "sk-" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4"
OPENAI_PROJECT_KEY = "sk-proj-" + "Ab3_Cd5-Ef7" * 8
AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
GITHUB_PAT_CLASSIC = "ghp_" + "a" * 18 + "B" * 18
GITHUB_PAT_FINE = "github_pat_11ABCDEFG0" + "x" * 40
GOOGLE_KEY = "AIza" + "SyA1234567890abcdefghijklmnopqrstuv"
HF_TOKEN = "hf_" + "AbCdEfGhIjKlMnOpQrStUvWxYz123456"

PROVIDER_KEYS = [
    ANTHROPIC_KEY,
    OPENAI_LEGACY_KEY,
    OPENAI_PROJECT_KEY,
    AWS_KEY,
    GITHUB_PAT_CLASSIC,
    GITHUB_PAT_FINE,
    GOOGLE_KEY,
    HF_TOKEN,
]


@pytest.mark.parametrize("key", PROVIDER_KEYS)
@pytest.mark.parametrize(
    "template",
    [
        "{key}",
        "OPENAI_API_KEY={key}",
        'client = Client(api_key="{key}")',
        "export TOKEN='{key}'\n",
        "  key: {key} # comment",
    ],
)
def test_provider_tokens_redacted(key: str, template: str) -> None:
    redacted, count = scan_and_redact(template.format(key=key))
    assert key not in redacted
    assert REDACTED in redacted
    assert count == 1


@pytest.mark.parametrize(
    "line",
    [
        'api_key = "a8f5f167f44f4964e6c998dee827110c"',
        "API-KEY: 'Zm9vYmFyYmF6cXV4MTIzNDU2'",
        'apikey="0123456789abcdef0123"',
        'client_secret = "s3cr3t-v4lu3-1234567"',
        'SECRET_KEY = "django-insecure-abc123def456ghi789"',
        'auth_token="tok_live_9a8b7c6d5e4f3g2h"',
        'const TOKEN = "eyJhbGciOiJIUzI1NiJ9.e30.abc"',
    ],
)
def test_generic_assignments_redacted_keeping_the_name(line: str) -> None:
    redacted, count = scan_and_redact(line)
    assert count == 1
    assert REDACTED in redacted
    value = line.split("=", 1)[-1] if "=" in line else line.split(":", 1)[-1]
    assert value.strip().strip("'\"") not in redacted
    name = line.split("=")[0].split(":")[0].strip().split()[-1]
    assert name in redacted


@pytest.mark.parametrize(
    "line",
    [
        'api_key = "your-api-key-here"',
        'api_key = "YOUR_OPENAI_API_KEY"',
        'api_key = "xxxxxxxxxxxxxxxxxxxx"',
        'api_key = "<insert-your-key-here>"',
        'token = "${GITHUB_TOKEN_FROM_ENV}"',
        'secret = "{{ secrets.MY_SECRET }}"',
        'api_key = "changeme-before-deploy"',
        'api_key = "sk-...paste-here..."',
        'api_key = "placeholder-value-123"',
        'api_key = "dummy-key-for-tests"',
        'api_key = "example-api-key-1234"',
        'api_key = os.environ["OPENAI_API_KEY"]',
        'api_key = os.getenv("OPENAI_API_KEY")',
        "apiKey: process.env.OPENAI_API_KEY",
        'token = "short"',
        "ANTHROPIC_API_KEY=",
        "max_tokens = 1024",
        "The task-abcdefghijklmnopqrstuvwxyz1234 id is fine",
        "disk-abcdefghijklmnopqrstuvwxyz1234",
        "tokenizer = 'bert-base-uncased-model'",
    ],
)
def test_placeholders_and_benign_text_not_redacted(line: str) -> None:
    redacted, count = scan_and_redact(line)
    assert count == 0
    assert redacted == line


def test_count_matches_number_of_secrets() -> None:
    text = "\n".join(
        [
            f"ANTHROPIC_API_KEY={ANTHROPIC_KEY}",
            f"OPENAI_API_KEY={OPENAI_LEGACY_KEY}",
            'api_key = "s9d8f7g6h5j4k3l2q1"',
            'api_key = "your-key-here-please"',
            f'gh = "{GITHUB_PAT_CLASSIC}"',
        ]
    )
    redacted, count = scan_and_redact(text)
    assert count == 4
    assert redacted.count(REDACTED) == 4
    for secret in (ANTHROPIC_KEY, OPENAI_LEGACY_KEY, "s9d8f7g6h5j4k3l2q1"):
        assert secret not in redacted
    assert "your-key-here-please" in redacted


def test_provider_key_in_generic_assignment_counted_once() -> None:
    redacted, count = scan_and_redact(f'openai.api_key = "{OPENAI_LEGACY_KEY}"')
    assert count == 1
    assert redacted == f'openai.api_key = "{REDACTED}"'


def test_empty_text() -> None:
    assert scan_and_redact("") == ("", 0)
    result = scan_text("")
    assert result.count == 0


def test_scanning_is_idempotent() -> None:
    once, first = scan_and_redact(f"key={ANTHROPIC_KEY}\napi_key='abcdefghijklmnop1234'")
    twice, second = scan_and_redact(once)
    assert first == 2
    assert second == 0
    assert twice == once


def test_large_input_is_fast() -> None:
    chunk = (
        "def handler(event):\n"
        "    value = compute(event['payload'])  # ordinary code line\n"
        "    logger.info('processed %s', value)\n"
    )
    body = chunk * (5_000_000 // len(chunk))
    adversarial = "sk-" + "a" * 200_000 + "\n" + 'api_key = "' + "b" * 200_000 + "\n"
    text = body + adversarial + f"\nKEY={ANTHROPIC_KEY}\n"
    assert len(text) > 5_000_000
    start = time.perf_counter()
    redacted, count = scan_and_redact(text)
    elapsed = time.perf_counter() - start
    assert elapsed < 3.0, f"scan took {elapsed:.2f}s"
    assert ANTHROPIC_KEY not in redacted
    assert count >= 2


# ---------------------------------------------------------------------------- SEC-1 regressions

GROQ_KEY = "gsk_" + "a1B2c3D4e5F6" * 4
STRIPE_KEY = "sk_live_" + "51HxYzAbCdEfGhIjKlMnOp"
STRIPE_RESTRICTED = "rk_live_" + "51HxYzAbCdEfGhIjKlMnOp"
SLACK_TOKEN = "xoxb-" + "123456789012-1234567890123-AbCdEfGhIjKlMnOpQrStUvWx"
GITHUB_OAUTH = "gho_" + "a1B2c3D4e5F6g7H8i9J0" * 2
GITHUB_SERVER = "ghs_" + "a1B2c3D4e5F6g7H8i9J0" * 2
GITHUB_USER = "ghu_" + "a1B2c3D4e5F6g7H8i9J0" * 2
JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4ifQ."
    "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
)
RSA_BLOCK = (
    "-----BEGIN RSA PRIVATE KEY-----\n"
    "MIIEowIBAAKCAQEAu1SU1LfVLPHCozMxH2Mo4lgOEePzNm0tRgeLezV6ffAt0gun\n"
    "VTLw7onLRnrq0/IzW7yWR7QkrmBL7jTKEn5u+qKhbwKfBstIs+bMY2Zkp18gnTxK\n"
    "-----END RSA PRIVATE KEY-----"
)


@pytest.mark.parametrize(
    ("text", "secret"),
    [
        # Cases verified as missed in the review (SEC-1).
        (f"GROQ_API_KEY={GROQ_KEY}", GROQ_KEY),
        (RSA_BLOCK, "MIIEowIBAAKCAQEAu1SU1LfVLPHCozMxH2Mo4lgOEePzNm0tRgeLezV6ffAt0gun"),
        ("DATABASE_URL=postgresql://admin:SuperS3cretPass@host/db", "SuperS3cretPass"),
        ('password = "hunter2hunter2xx"', "hunter2hunter2xx"),
        ("aws_secret_access_key = abcdEFGHijklMNOPqrst1234", "abcdEFGHijklMNOPqrst1234"),
        # Widened provider formats.
        (f"STRIPE_SECRET_KEY={STRIPE_KEY}", STRIPE_KEY),
        (f"stripe.api_key = '{STRIPE_RESTRICTED}'", STRIPE_RESTRICTED),
        (f"SLACK_BOT_TOKEN={SLACK_TOKEN}", SLACK_TOKEN),
        (f"token: {GITHUB_OAUTH}", GITHUB_OAUTH),
        (f"GH={GITHUB_SERVER}", GITHUB_SERVER),
        (f"GH={GITHUB_USER}", GITHUB_USER),
        (f"const session = '{JWT}';", JWT),
        # Generic names: quoted, unquoted, JSON, YAML, camelCase, Bearer headers.
        ('SECRET_KEY="django-insecure-abc123def456ghi789"', "django-insecure-abc123def456ghi789"),
        ("DB_PASSWORD: Sup3rS3cretPassw0rd", "Sup3rS3cretPassw0rd"),
        ('{"client_secret": "a1b2c3d4e5f6g7h8i9"}', "a1b2c3d4e5f6g7h8i9"),
        ("authToken := 'q1w2e3r4t5y6u7i8o9'", "q1w2e3r4t5y6u7i8o9"),
        (
            'headers = {"Authorization": "Bearer abcdef1234567890abcdef12"}',
            "abcdef1234567890abcdef12",
        ),
        ("redis://:R3disPassw0rd@cache:6379/0", "R3disPassw0rd"),
        ("mongodb+srv://app:M0ng0Pass2024@cluster0.mongodb.net/db", "M0ng0Pass2024"),
    ],
)
def test_sec1_secrets_redacted(text: str, secret: str) -> None:
    redacted, count = scan_and_redact(text)
    assert secret not in redacted
    assert REDACTED in redacted
    assert count == 1


def test_url_credentials_keep_scheme_user_and_host() -> None:
    redacted, _ = scan_and_redact("DATABASE_URL=postgresql://admin:SuperS3cretPass@host/db")
    assert redacted == f"DATABASE_URL=postgresql://admin:{REDACTED}@host/db"


@pytest.mark.parametrize(
    "line",
    [
        "DATABASE_URL=postgresql://user:password@localhost:5432/db",
        "DATABASE_URL=postgresql://roaster:roaster@localhost:5438/roaster_test",
        "url = 'postgresql://${DB_USER}:${DB_PASS}@db/app'",
        "see https://example.com:8080/path and git@github.com:org/repo.git",
        "csrf_token = request.form['csrf_token']",
        "token = self.tokenizer.encode(text)",
        "password = get_password_from_vault()",
        "password: Optional[str] = None",
        "access_token = response.json()['access_token']",
        "SECRET_KEY = settings.SECRET_KEY",
        "Authorization: Bearer <your-token-here>",
        "Authorization: `Bearer ${token}`",
        "token_count = count_tokens(prompt_template_string)",
        "-----BEGIN PUBLIC KEY-----",
        "password = 'aaaaaaaaaaaaaaaa'",
        "aws_secret_access_key = YOUR_AWS_SECRET_ACCESS_KEY",
    ],
)
def test_sec1_benign_lines_untouched(line: str) -> None:
    redacted, count = scan_and_redact(line)
    assert count == 0
    assert redacted == line


def test_truncated_private_key_body_is_redacted() -> None:
    text = (
        "key = '''-----BEGIN OPENSSH PRIVATE KEY-----\n"
        "b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9u\nZQAAAAAAAAABAAAAMwAAAAtzc2gtZWQy"
    )
    redacted, count = scan_and_redact(text)
    assert count == 1
    assert "b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9u" not in redacted


ENV_FILE = "\n".join(
    [
        "# committed by accident",
        "DEBUG=true",
        "PORT=8000",
        "MODEL_NAME=gpt-4o-mini",
        f"OPENAI_API_KEY={OPENAI_PROJECT_KEY}",
        "SECRET_KEY_BASE=abcdefgh12345678abcdefgh",
        "DB_PASS='hunter2'",
        'export JWT_SECRET="q1w2e3r4t5y6u7i8o9p0" # prod',
        "SESSION_SALT=Zx9Yw8Xv7Uu6Tt5Ss4",
        "EMPTY=",
        "PLACEHOLDER=your-key-here",
    ]
)


def test_env_file_values_redacted_line_by_line() -> None:
    redacted, count = scan_and_redact(ENV_FILE, ".env")
    lines = redacted.splitlines()
    assert lines[0] == "# committed by accident"
    assert "DEBUG=true" in lines and "PORT=8000" in lines and "EMPTY=" in lines
    assert "PLACEHOLDER=your-key-here" in lines
    for secret in (
        OPENAI_PROJECT_KEY,
        "gpt-4o-mini",
        "abcdefgh12345678abcdefgh",
        "hunter2",
        "q1w2e3r4t5y6u7i8o9p0",
        "Zx9Yw8Xv7Uu6Tt5Ss4",
    ):
        assert secret not in redacted
    assert f"DB_PASS='{REDACTED}'" in lines
    assert f'export JWT_SECRET="{REDACTED}" # prod' in lines
    assert f"MODEL_NAME={REDACTED}" in lines  # redacted but not counted as a secret
    assert count == 5


@pytest.mark.parametrize("path", [".env.example", "config/.env.sample", "settings.py", None])
def test_env_line_rules_only_apply_to_committed_env_files(path: str | None) -> None:
    redacted, count = scan_and_redact("DB_PASS='hunter2'\nMODEL_NAME=gpt-4o-mini", path)
    assert count == 0
    assert "hunter2" in redacted


def test_env_file_detection_is_shared_with_analyzer() -> None:
    from app.services import repo_analyzer, secret_scanner

    assert repo_analyzer.is_env_file is secret_scanner.is_env_file
    assert repo_analyzer.is_env_template is secret_scanner.is_env_template


def test_large_env_and_adversarial_input_is_fast() -> None:
    adversarial = (
        "password = "
        + "a1" * 100_000
        + "\n"
        + "postgresql://"
        + "u" * 100_000
        + ":"
        + "p" * 100_000
        + "\n"
        + "Bearer "
        + "x1" * 100_000
        + "\n"
        + "-----BEGIN RSA PRIVATE KEY-----\n"
        + "A" * 200_000
        + "\n"
        + "eyJ"
        + "a" * 100_000
        + "."
        + "b" * 100_000
        + "\n"
    ) * 5
    env = "\n".join(f"KEY_{i}=value{i}abcdefghijklmnop" for i in range(5_000))
    start = time.perf_counter()
    scan_and_redact(adversarial)
    scan_and_redact(env, ".env")
    elapsed = time.perf_counter() - start
    assert elapsed < 3.0, f"scan took {elapsed:.2f}s"

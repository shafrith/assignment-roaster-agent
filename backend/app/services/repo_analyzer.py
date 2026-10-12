"""Static analysis of a public GitHub repository for the roast engine.

Structure: small PURE functions (path classification, sampling, notebook extraction, code-smell
heuristics, GenAI findings) that are unit-testable without I/O, plus one async orchestrator,
:func:`analyze_repo`, that fetches data through :class:`GitHubClient`.

Safety rules enforced here:

* Repo code is only ever parsed with :func:`ast.parse` - never compiled to bytecode or executed.
* Every sampled file passes through :func:`scan_and_redact` before it is put in a
  :class:`SampledFile`; findings mention file paths but never secret values.
"""

import ast
import asyncio
import json
import logging
import posixpath
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.config import settings
from app.services.contracts import (
    AnalysisResult,
    Finding,
    RepoInfo,
    RepoTooLargeError,
    SampledFile,
)
from app.services.github_client import GitHubClient

# Dotenv detection lives in the scanner (single source of truth: the scanner redacts every value
# in exactly the files the analyzer reports as committed .env files).
from app.services.secret_scanner import is_env_file, is_env_template, scan_and_redact

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------- constants

MAX_FILE_BYTES = 20_000
MAX_NOTEBOOK_TREE_SIZE = 5_000_000  # don't even try notebooks bigger than this
# Notebooks are fetched whole (outputs inflate them), then reduced to code cells and trimmed.
# Fetching every eligible notebook completely keeps the JSON parseable; peak memory is bounded by
# FETCH_CONCURRENCY x 5 MB. If a notebook is still cut off, extraction falls back to a lenient
# cell-by-cell parse.
MAX_NOTEBOOK_BYTES = MAX_NOTEBOOK_TREE_SIZE
FETCH_CONCURRENCY = 8
LARGE_FILE_LINES = 500
LONG_FUNCTION_LINES = 80
PRINT_CALL_THRESHOLD = 5
MIN_README_WORDS = 50
LARGE_COMMITTED_FILE_BYTES = 5_000_000
LARGEST_FILES_COUNT = 5

IGNORED_DIRS = frozenset(
    {
        "node_modules",
        "venv",
        ".venv",
        "env",
        "__pycache__",
        ".git",
        "dist",
        "build",
        ".ipynb_checkpoints",
        "site-packages",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".idea",
        ".vscode",
        ".next",
        "coverage",
        "htmlcov",
        ".eggs",
    }
)

BINARY_EXTENSIONS = frozenset(
    {
        # images / media
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp", ".tiff",
        ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv", ".flac", ".ogg", ".webm",
        # documents / archives
        ".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx",
        ".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".whl", ".jar",
        # datasets / models
        ".csv", ".tsv", ".parquet", ".feather", ".arrow", ".pkl", ".pickle", ".joblib",
        ".pt", ".pth", ".bin", ".h5", ".hdf5", ".onnx", ".safetensors", ".ckpt", ".npy",
        ".npz", ".tflite", ".gguf", ".db", ".sqlite", ".sqlite3", ".jsonl",
        # compiled / fonts / misc
        ".pyc", ".pyo", ".so", ".dll", ".dylib", ".exe", ".o", ".a", ".class",
        ".woff", ".woff2", ".ttf", ".otf", ".eot", ".lock", ".min.js", ".map",
    }
)  # fmt: skip

SOURCE_EXTENSIONS = frozenset(
    {
        ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".java", ".kt", ".go", ".rs",
        ".rb", ".php", ".cs", ".cpp", ".cc", ".c", ".h", ".hpp", ".swift", ".scala", ".r",
        ".sh", ".sql", ".vue", ".svelte", ".dart", ".html", ".css", ".scss",
    }
)  # fmt: skip

DEPENDENCY_FILES = frozenset(
    {"requirements.txt", "pyproject.toml", "pipfile", "package.json", "environment.yml",
     "environment.yaml", "setup.py", "setup.cfg", "poetry.lock", "go.mod", "cargo.toml",
     "pom.xml", "build.gradle", "gemfile"}
)  # fmt: skip

ENTRY_POINTS = (
    "main.py",
    "app.py",
    "streamlit_app.py",
    "index.ts",
    "server.py",
    "run.py",
    "index.js",
    "main.ts",
)

TEST_DIR_NAMES = frozenset({"tests", "test", "__tests__", "spec"})
_TEST_FILE_RE = re.compile(
    r"^(test_.+\.py|.+_test\.py|.+\.(test|spec)\.(ts|tsx|js|jsx|mjs)|.+_test\.go|.+Test\.java)$"
)

LLM_IMPORT_MARKERS = (
    "openai",
    "anthropic",
    "langchain",
    "llama_index",
    "google.generativeai",
    "google.genai",
    "transformers",
    "groq",
    "cohere",
    "mistralai",
    "ollama",
    "litellm",
    "@anthropic-ai/sdk",
    "@google/generative-ai",
)
LLM_CALL_SUFFIXES = (
    "chat.completions.create",
    "completions.create",
    "ChatCompletion.create",
    "messages.create",
    "messages.stream",
    "generate_content",
    "responses.create",
    "invoke",
    "ainvoke",
    "predict",
    "run",
)
LLM_CLIENT_HINTS = ("client", "openai", "anthropic", "llm", "chat", "model", "chain", "agent")

_MODEL_NAME_RE = re.compile(
    r"^(gpt-[0-9][\w.-]*|claude-[\w.-]+|gemini-[\w.-]+|"
    r"text-davinci-\d+|llama-?[0-9][\w.-]*|mistral-[\w.-]+|command-r[\w.-]*)$",
    re.IGNORECASE,
)
_MODEL_NAME_IN_TEXT_RE = re.compile(
    r"['\"](gpt-[0-9][\w.-]*|claude-[\w.-]+|gemini-[\w.-]+|text-davinci-\d+)['\"]",
    re.IGNORECASE,
)
_RETRY_RE = re.compile(r"retry|tenacity|backoff|max_retries|maxRetries", re.IGNORECASE)
_TOKEN_HANDLING_RE = re.compile(
    r"usage|max_tokens|maxTokens|max_output_tokens|tiktoken|count_tokens|token_count|cost",
    re.IGNORECASE,
)
_ENV_USAGE_RE = re.compile(r"os\.environ|os\.getenv|getenv\(|process\.env|load_dotenv|dotenv")
_INJECTION_RE = re.compile(
    r"\b(?:ignore|disregard|forget|override)\s+(?:all\s+|any\s+)?(?:of\s+)?(?:the\s+|your\s+)?"
    r"(?:previous|prior|above|earlier|preceding|system)\s+(?:instructions?|prompts?|rules)"
    r"|\b(?:give|rate|score|grade|mark)\s+(?:this|me|it|us|my\s+\w+|this\s+\w+|the\s+\w+)\s+"
    r"(?:a\s+|an\s+)?(?:10|ten)\s*(?:/\s*10|out\s+of\s+10|out\s+of\s+ten)"
    r"|\byou\s+are\s+now\s+(?:a|an|in)\b"
    r"|\b(?:system\s+prompt|new\s+instructions)\s*:"
    r"|\b(?:dear|attention|note\s+to|hey)\s+(?:the\s+)?(?:ai|llm|claude|chatgpt|gpt|language\s+model)"
    r"(?:\s+(?:reviewer|grader|assistant|evaluator))?\s*[:,]",
    re.IGNORECASE,
)
_PATH_SEPARATORS_RE = re.compile(r"[_\-./]+")
_NOTEBOOK_MAGIC_RE = re.compile(r"^\s*[!%]", re.MULTILINE)

SEVERITY_ORDER: dict[str, int] = {"critical": 0, "high": 1, "medium": 2, "low": 3}


# ---------------------------------------------------------------------------- path classification


@dataclass
class PathClassification:
    """Facts derived purely from the repository tree (no file contents)."""

    files: list[tuple[str, int]] = field(default_factory=list)  # non-ignored blobs (path, size)
    all_blobs: list[tuple[str, int]] = field(default_factory=list)
    readme_paths: list[str] = field(default_factory=list)
    has_gitignore: bool = False
    dependency_files: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)
    env_files: list[str] = field(default_factory=list)
    has_env_example: bool = False
    notebooks: list[tuple[str, int]] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    source_files: list[tuple[str, int]] = field(default_factory=list)
    committed_venv: bool = False
    committed_node_modules: bool = False
    committed_checkpoints: bool = False
    committed_pycache: bool = False
    large_binaries: list[tuple[str, int]] = field(default_factory=list)


def _extension(path: str) -> str:
    base = posixpath.basename(path).lower()
    if base.endswith(".min.js"):
        return ".min.js"
    return posixpath.splitext(base)[1]


def is_binary_path(path: str) -> bool:
    """Return True for images, archives, datasets, model weights, and compiled artifacts."""
    return _extension(path) in BINARY_EXTENSIONS


def is_ignored_path(path: str) -> bool:
    """Return True for vendored/generated directories and binary/data files."""
    segments = path.split("/")
    if any(seg in IGNORED_DIRS for seg in segments[:-1]):
        return True
    return is_binary_path(path)


def is_test_path(path: str) -> bool:
    """Return True for files that look like automated tests."""
    segments = path.split("/")
    if any(seg.lower() in TEST_DIR_NAMES for seg in segments[:-1]):
        return True
    return bool(_TEST_FILE_RE.match(segments[-1]))


def _depth(path: str) -> int:
    return path.count("/")


def classify_paths(tree: Iterable[dict[str, Any]]) -> PathClassification:
    """Classify a GitHub recursive tree listing.

    Args:
        tree: Entries from ``GET /git/trees/{sha}?recursive=1`` (``path``, ``type``, ``size``).

    Returns:
        A :class:`PathClassification` describing what the repo contains.
    """
    result = PathClassification()
    for entry in tree:
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            continue
        segments = path.split("/")
        dir_segments = segments if entry.get("type") == "tree" else segments[:-1]
        if "node_modules" in dir_segments:
            result.committed_node_modules = True
        if ".ipynb_checkpoints" in dir_segments:
            result.committed_checkpoints = True
        if "__pycache__" in dir_segments or path.endswith((".pyc", ".pyo")):
            result.committed_pycache = True
        if (
            any(seg in {"venv", ".venv"} for seg in dir_segments)
            or "site-packages" in dir_segments
            or segments[-1] == "pyvenv.cfg"
        ):
            result.committed_venv = True

        if entry.get("type") != "blob":
            continue
        size = entry.get("size")
        size = size if isinstance(size, int) and size >= 0 else 0
        result.all_blobs.append((path, size))
        if is_binary_path(path) and size >= LARGE_COMMITTED_FILE_BYTES:
            result.large_binaries.append((path, size))
        if is_ignored_path(path):
            continue

        result.files.append((path, size))
        base = segments[-1]
        lower = base.lower()
        if lower.startswith("readme"):
            result.readme_paths.append(path)
        if lower == ".gitignore":
            result.has_gitignore = True
        if lower in DEPENDENCY_FILES:
            result.dependency_files.append(path)
        if is_env_file(path):
            result.env_files.append(path)
        if is_env_template(path):
            result.has_env_example = True
        if is_test_path(path):
            result.test_files.append(path)
        if lower.endswith(".ipynb"):
            result.notebooks.append((path, size))
        elif _extension(path) in SOURCE_EXTENSIONS:
            result.source_files.append((path, size))
            if lower in ENTRY_POINTS:
                result.entry_points.append(path)

    # Root README first, then shallowest.
    result.readme_paths.sort(key=lambda p: (_depth(p), p.lower()))
    result.entry_points.sort(
        key=lambda p: (_depth(p), ENTRY_POINTS.index(p.split("/")[-1].lower()))
    )
    result.dependency_files.sort(key=lambda p: (_depth(p), p))
    return result


def largest_files(
    classification: PathClassification, limit: int = LARGEST_FILES_COUNT
) -> list[dict[str, Any]]:
    """Return the ``limit`` largest committed blobs as ``[{"path", "size"}]``."""
    ranked = sorted(classification.all_blobs, key=lambda item: (-item[1], item[0]))[:limit]
    return [{"path": path, "size": size} for path, size in ranked]


def select_files_to_sample(classification: PathClassification, max_files: int) -> list[str]:
    """Choose which files to fetch and send to the LLM, highest priority first.

    Priority: root README -> committed ``.env`` files (redacted evidence) -> entry points ->
    dependency files -> other source files by size desc -> notebooks by size desc.
    """
    ordered: list[str] = []
    seen: set[str] = set()

    def add(paths: Iterable[str]) -> None:
        for path in paths:
            if path not in seen and len(ordered) < max_files:
                seen.add(path)
                ordered.append(path)

    add(classification.readme_paths[:1])
    add(classification.env_files)
    add(classification.entry_points)
    add(classification.dependency_files)
    add(path for path, _ in sorted(classification.source_files, key=lambda i: (-i[1], i[0])))
    add(
        path
        for path, size in sorted(classification.notebooks, key=lambda i: (-i[1], i[0]))
        if size <= MAX_NOTEBOOK_TREE_SIZE
    )
    return ordered


# ---------------------------------------------------------------------------- tree-level findings


def hygiene_findings(c: PathClassification) -> list[Finding]:
    """Findings derived from the tree alone: committed junk, missing README/deps/tests, etc."""
    findings: list[Finding] = []
    if c.committed_venv:
        findings.append(
            Finding("git_hygiene", "high", "Virtual environment (venv/) committed to the repo.")
        )
    if c.committed_node_modules:
        findings.append(Finding("git_hygiene", "high", "node_modules/ committed to the repo."))
    if c.committed_checkpoints:
        findings.append(
            Finding("git_hygiene", "low", ".ipynb_checkpoints/ committed - add it to .gitignore.")
        )
    if c.committed_pycache:
        findings.append(
            Finding("git_hygiene", "low", "__pycache__ / .pyc files committed to the repo.")
        )
    for path in c.env_files:
        findings.append(
            Finding("security", "high", "Environment file committed to the repo.", file=path)
        )
    for path, size in c.large_binaries[:3]:
        findings.append(
            Finding(
                "git_hygiene",
                "medium",
                f"Large binary/data file committed ({size // 1_000_000} MB) - use Git LFS or "
                "download it at runtime.",
                file=path,
            )
        )
    if not c.has_gitignore:
        findings.append(Finding("git_hygiene", "medium", "No .gitignore file."))
    if not c.readme_paths:
        findings.append(Finding("documentation", "high", "No README file."))
    if not c.dependency_files:
        findings.append(
            Finding(
                "dependencies",
                "high",
                "No dependency file (requirements.txt / pyproject.toml / package.json / "
                "environment.yml).",
            )
        )
    if not c.test_files:
        findings.append(Finding("testing", "medium", "No automated tests found."))
    return findings


# ---------------------------------------------------------------------------- content helpers


_CELLS_ARRAY_RE = re.compile(r'"cells"\s*:\s*\[')
_JSON_DECODER = json.JSONDecoder()


def _lenient_notebook_cells(raw: str) -> list[Any]:
    """Decode the complete cells of a notebook whose JSON is cut off or otherwise broken.

    Walks the top-level ``"cells": [...]`` array one element at a time with
    :meth:`json.JSONDecoder.raw_decode` and stops at the first element that does not decode, so a
    notebook truncated mid-way still yields every cell before the cut. Nothing is executed.
    """
    match = _CELLS_ARRAY_RE.search(raw)
    if match is None:
        return []
    cells: list[Any] = []
    pos = match.end()
    length = len(raw)
    while pos < length:
        while pos < length and raw[pos] in " \t\r\n,":
            pos += 1
        if pos >= length or raw[pos] == "]":
            break
        try:
            cell, pos = _JSON_DECODER.raw_decode(raw, pos)
        except (ValueError, RecursionError):
            break
        cells.append(cell)
    return cells


def _notebook_cells(raw: str) -> list[Any]:
    """Return the notebook's cell list (nbformat 3 or 4), leniently for broken JSON."""
    try:
        data = json.loads(raw)
    except (ValueError, RecursionError):
        return _lenient_notebook_cells(raw)
    if not isinstance(data, dict):
        return []
    cells = data.get("cells")
    if isinstance(cells, list):
        return cells
    # nbformat 3 kept cells inside worksheets.
    collected: list[Any] = []
    worksheets = data.get("worksheets")
    if isinstance(worksheets, list):
        for ws in worksheets:
            if isinstance(ws, dict) and isinstance(ws.get("cells"), list):
                collected.extend(ws["cells"])
    return collected


def extract_notebook_code(raw: str) -> str:
    """Extract only the code cells of a Jupyter notebook as plain source.

    Outputs, markdown, and metadata are dropped. Truncated notebooks yield the code of every
    complete cell before the cut; unreadable notebooks yield ``""``.
    """
    cells = _notebook_cells(raw)
    chunks: list[str] = []
    for index, cell in enumerate(cells):
        if not isinstance(cell, dict) or cell.get("cell_type") != "code":
            continue
        source = cell.get("source", cell.get("input", ""))
        if isinstance(source, list):
            source = "".join(s for s in source if isinstance(s, str))
        if not isinstance(source, str) or not source.strip():
            continue
        chunks.append(f"# --- cell {index + 1} ---\n{source.rstrip()}\n")
    return "\n".join(chunks)


def count_words(text: str) -> int:
    """Count whitespace-separated words."""
    return len(text.split())


def count_lines(text: str) -> int:
    """Count lines (a trailing newline does not add a line)."""
    return len(text.splitlines())


def _dotted_name(node: ast.AST) -> str:
    """Return ``a.b.c`` for an attribute chain (calls in the chain are skipped)."""
    parts: list[str] = []
    while True:
        if isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        elif isinstance(node, ast.Call):
            node = node.func
        elif isinstance(node, ast.Name):
            parts.append(node.id)
            break
        else:
            break
    return ".".join(reversed(parts))


def _is_llm_call(name: str) -> bool:
    if not name:
        return False
    lowered = name.lower()
    for suffix in LLM_CALL_SUFFIXES:
        if name == suffix or name.endswith("." + suffix):
            if suffix in {"invoke", "ainvoke", "predict", "run"}:
                receiver = lowered.rsplit(".", 1)[0]
                return "." in name and any(hint in receiver for hint in LLM_CLIENT_HINTS)
            return True
    return False


class _SmellVisitor(ast.NodeVisitor):
    """Collect code-smell facts from a Python AST (pure inspection, nothing is executed)."""

    def __init__(self) -> None:
        self.long_functions: list[tuple[str, int]] = []
        self.function_count = 0
        self.annotated_functions = 0
        self.bare_excepts = 0
        self.print_calls = 0
        self.llm_calls = 0
        self.unguarded_llm_calls = 0
        self.model_names: set[str] = set()
        self._try_depth = 0

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.function_count += 1
        args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        args = [a for a in args if a.arg not in {"self", "cls"}]
        if node.returns is not None or any(a.annotation is not None for a in args):
            self.annotated_functions += 1
        end = getattr(node, "end_lineno", None) or node.lineno
        length = end - node.lineno + 1
        if length > LONG_FUNCTION_LINES:
            self.long_functions.append((node.name, length))
        self.generic_visit(node)

    visit_FunctionDef = _visit_function
    visit_AsyncFunctionDef = _visit_function

    def _visit_try(self, node: ast.Try | ast.TryStar) -> None:
        self._try_depth += 1
        for stmt in node.body:
            self.visit(stmt)
        self._try_depth -= 1
        for part in (*node.handlers, *node.orelse, *node.finalbody):
            self.visit(part)

    def visit_Try(self, node: ast.Try) -> None:
        self._visit_try(node)

    def visit_TryStar(self, node: ast.TryStar) -> None:
        self._visit_try(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self.bare_excepts += 1
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id == "print":
            self.print_calls += 1
        if _is_llm_call(_dotted_name(node.func)):
            self.llm_calls += 1
            if self._try_depth == 0:
                self.unguarded_llm_calls += 1
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and len(node.value) < 60:
            if _MODEL_NAME_RE.match(node.value.strip()):
                self.model_names.add(node.value.strip())


def _strip_notebook_magics(source: str) -> str:
    """Comment out IPython ``!shell`` / ``%magic`` lines so notebook code can be parsed."""
    return _NOTEBOOK_MAGIC_RE.sub("#", source)


def python_smells(path: str, source: str, truncated: bool = False) -> list[Finding]:
    """Detect Python code smells using :func:`ast.parse` only (the code is never executed).

    Args:
        path: Repository path, used in finding messages.
        source: Python source (notebook code cells are accepted too).
        truncated: Whether ``source`` was cut off; syntax errors are then ignored.

    Returns:
        Findings for long files/functions, bare excepts, print debugging, missing type hints,
        hardcoded model names, and LLM calls without error handling.
    """
    findings: list[Finding] = []
    lines = count_lines(source)
    if lines > LARGE_FILE_LINES:
        findings.append(
            Finding("code_quality", "medium", f"File is {lines} lines long - split it up.", path)
        )

    is_notebook = path.lower().endswith(".ipynb")
    to_parse = _strip_notebook_magics(source) if is_notebook else source
    try:
        tree = ast.parse(to_parse, filename=path)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        if not truncated and not is_notebook:
            findings.append(
                Finding("code_quality", "low", "File does not parse as valid Python 3.", path)
            )
        return findings

    visitor = _SmellVisitor()
    try:
        visitor.visit(tree)
    except RecursionError:
        return findings

    if visitor.long_functions:
        worst = sorted(visitor.long_functions, key=lambda item: -item[1])[:3]
        names = ", ".join(f"{name}() ({length} lines)" for name, length in worst)
        findings.append(
            Finding(
                "code_quality",
                "medium",
                f"Functions longer than {LONG_FUNCTION_LINES} lines: {names}.",
                path,
            )
        )
    if visitor.bare_excepts:
        findings.append(
            Finding(
                "code_quality",
                "medium",
                f"{visitor.bare_excepts} bare `except:` clause(s) swallow every error.",
                path,
            )
        )
    if visitor.print_calls >= PRINT_CALL_THRESHOLD:
        findings.append(
            Finding(
                "code_quality",
                "low",
                f"{visitor.print_calls} print() calls - use the logging module.",
                path,
            )
        )
    if visitor.function_count >= 3 and visitor.annotated_functions == 0:
        findings.append(
            Finding(
                "code_quality",
                "low",
                f"No type hints on any of {visitor.function_count} functions.",
                path,
            )
        )
    if visitor.model_names:
        names = ", ".join(sorted(visitor.model_names)[:3])
        findings.append(
            Finding(
                "genai_practices",
                "low",
                f"Hardcoded model name(s): {names} - read them from config/env.",
                path,
            )
        )
    if visitor.unguarded_llm_calls:
        findings.append(
            Finding(
                "genai_practices",
                "medium",
                f"{visitor.unguarded_llm_calls} LLM API call(s) with no try/except around them.",
                path,
            )
        )
    return findings


def generic_smells(path: str, source: str) -> list[Finding]:
    """Language-agnostic smells for non-Python source files (size, hardcoded model names)."""
    findings: list[Finding] = []
    lines = count_lines(source)
    if lines > LARGE_FILE_LINES:
        findings.append(
            Finding("code_quality", "medium", f"File is {lines} lines long - split it up.", path)
        )
    models = sorted({m.group(1) for m in _MODEL_NAME_IN_TEXT_RE.finditer(source)})
    if models:
        findings.append(
            Finding(
                "genai_practices",
                "low",
                f"Hardcoded model name(s): {', '.join(models[:3])} - read them from config/env.",
                path,
            )
        )
    return findings


def requirements_findings(path: str, source: str) -> list[Finding]:
    """Flag unpinned dependencies in a ``requirements.txt``."""
    if posixpath.basename(path).lower() != "requirements.txt":
        return []
    requirements = [
        line.strip()
        for line in source.splitlines()
        if line.strip() and not line.strip().startswith(("#", "-"))
    ]
    unpinned = [r for r in requirements if not re.search(r"[=<>~!]=|[<>]|@", r)]
    if requirements and len(unpinned) == len(requirements):
        return [
            Finding(
                "dependencies",
                "low",
                f"None of the {len(requirements)} requirements are version-pinned.",
                path,
            )
        ]
    return []


INJECTION_MESSAGE = (
    "Contains text that looks like a prompt-injection attempt aimed at the reviewer."
)
PATH_INJECTION_MESSAGE = "File name looks like a prompt-injection attempt aimed at the reviewer."
MAX_PATH_INJECTION_FINDINGS = 3


def looks_like_injection(text: str) -> bool:
    """Return True if ``text`` contains an obvious prompt-injection phrase."""
    return bool(_INJECTION_RE.search(text))


def injection_findings(path: str, source: str) -> list[Finding]:
    """Flag text that looks like a prompt-injection attempt aimed at the roaster."""
    if looks_like_injection(source):
        return [Finding("security", "medium", INJECTION_MESSAGE, path)]
    return []


def path_injection_findings(paths: Iterable[str]) -> list[Finding]:
    """Flag file/directory names that spell out an injection (``ignore_previous_instructions.py``).

    Paths reach the model through the analysis summary, so they are checked deterministically
    instead of trusting the model to notice.
    """
    findings: list[Finding] = []
    for path in paths:
        if looks_like_injection(_PATH_SEPARATORS_RE.sub(" ", path)):
            findings.append(Finding("security", "medium", PATH_INJECTION_MESSAGE, path))
            if len(findings) >= MAX_PATH_INJECTION_FINDINGS:
                break
    return findings


def notebook_unreadable_finding(path: str) -> Finding:
    """Finding for a notebook whose code cells could not be extracted (so the model knows why)."""
    return Finding(
        "code_quality",
        "low",
        "Notebook too large or malformed to analyse - no code cells could be extracted. "
        "Clear cell outputs before committing.",
        path,
    )


def uses_llm(source: str) -> bool:
    """Return True if the source imports or references a known LLM SDK."""
    return any(marker in source for marker in LLM_IMPORT_MARKERS)


def genai_findings(
    c: PathClassification, sampled: Sequence[SampledFile], secrets_found: int
) -> list[Finding]:
    """Repo-level GenAI practice findings computed from the tree and sampled sources."""
    findings: list[Finding] = []
    code_files = [f for f in sampled if _extension(f.path) != ".md" and not is_env_file(f.path)]
    all_code = "\n".join(f.content for f in code_files)
    llm = uses_llm(all_code)

    runnable = [p for p, _ in c.source_files if _extension(p) in {".py", ".ts", ".js", ".tsx"}]
    if c.notebooks and not runnable:
        findings.append(
            Finding(
                "genai_practices",
                "medium",
                "Notebook-only submission - no runnable script or app entry point.",
            )
        )
    if secrets_found:
        findings.append(
            Finding(
                "genai_practices",
                "high",
                "API key / secret hardcoded in the repo instead of loaded from the environment.",
            )
        )
    if not llm:
        return findings

    has_prompt_files = any("prompt" in p.lower() for p, _ in c.files)
    if not has_prompt_files:
        findings.append(
            Finding(
                "genai_practices",
                "low",
                "No prompt templates - prompts are written inline in the code.",
            )
        )
    if not _TOKEN_HANDLING_RE.search(all_code):
        findings.append(
            Finding("genai_practices", "low", "No token limits, usage tracking, or cost handling.")
        )
    if not _RETRY_RE.search(all_code):
        findings.append(Finding("genai_practices", "medium", "No retry/backoff on LLM API errors."))
    if not c.has_env_example and (_ENV_USAGE_RE.search(all_code) or llm):
        findings.append(
            Finding(
                "documentation",
                "low",
                "No .env.example documenting required environment variables.",
            )
        )
    return findings


def sort_findings(findings: Iterable[Finding]) -> list[Finding]:
    """Deduplicate findings and order them by severity (critical first)."""
    unique = list(dict.fromkeys(findings))
    return sorted(unique, key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.category))


def secret_finding(path: str, count: int) -> Finding:
    """Critical security finding for secrets committed in ``path`` (never includes the value)."""
    noun = "secret" if count == 1 else "secrets"
    return Finding(
        "security",
        "critical",
        f"{count} hardcoded {noun} (API key/token) committed - revoke and rotate immediately. "
        "Value redacted.",
        path,
    )


def content_findings(path: str, content: str, truncated: bool) -> list[Finding]:
    """Run every per-file content heuristic appropriate for ``path``."""
    ext = _extension(path)
    findings: list[Finding] = []
    if ext in {".py", ".ipynb"}:
        findings.extend(python_smells(path, content, truncated))
    elif ext in SOURCE_EXTENSIONS:
        findings.extend(generic_smells(path, content))
    findings.extend(requirements_findings(path, content))
    findings.extend(injection_findings(path, content))
    return findings


# ---------------------------------------------------------------------------- orchestration


@dataclass
class _FetchedFile:
    path: str
    content: str  # redacted
    truncated: bool
    secrets: int
    injection: bool = False  # raw text (incl. notebook markdown) contains an injection phrase
    unreadable_notebook: bool = False


def _truncate(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


async def _fetch_sample(
    gh: GitHubClient, info: RepoInfo, path: str, semaphore: asyncio.Semaphore
) -> _FetchedFile | None:
    is_notebook = path.lower().endswith(".ipynb")
    async with semaphore:
        fetched = await gh.get_file_text(
            info.owner,
            info.name,
            path,
            info.head_sha,
            max_bytes=MAX_NOTEBOOK_BYTES if is_notebook else MAX_FILE_BYTES,
        )
    if fetched is None:
        return None
    raw, truncated = fetched
    injection = looks_like_injection(raw)
    if is_notebook:
        # Count secrets over the whole notebook (outputs included), but only keep code cells.
        # Raw notebook JSON escapes quotes, so quoted assignments are only visible once the code
        # is extracted: take the larger of the two counts (they overlap, so don't add them).
        _, raw_secrets = scan_and_redact(raw, path)
        code = extract_notebook_code(raw)
        redacted, code_secrets = scan_and_redact(code, path)
        content, cut = _truncate(redacted, MAX_FILE_BYTES)
        return _FetchedFile(
            path,
            content,
            truncated or cut,
            max(raw_secrets, code_secrets),
            injection=injection,
            unreadable_notebook=bool(raw.strip()) and not code.strip(),
        )
    redacted, secrets = scan_and_redact(raw, path)
    return _FetchedFile(path, redacted, truncated, secrets, injection=injection)


async def analyze_repo(gh: GitHubClient, info: RepoInfo) -> AnalysisResult:
    """Analyze a repository: tree hygiene, sampled file contents, secrets, and code smells.

    Args:
        gh: An open :class:`GitHubClient`.
        info: Repo metadata from :meth:`GitHubClient.get_repo_info`.

    Returns:
        The :class:`AnalysisResult` (sampled contents are already secret-redacted).

    Raises:
        RepoTooLargeError: If the repo exceeds ``MAX_REPO_SIZE_MB``.
        GitHubUnavailableError: On GitHub API failures.
    """
    if info.size_kb > settings.max_repo_size_kb:
        raise RepoTooLargeError(f"Repo romba perusu da, {settings.MAX_REPO_SIZE_MB}MB-kku mela! 🐘")

    languages, tree, (commit_count, last_commit_at) = await asyncio.gather(
        gh.get_languages(info.owner, info.name),
        gh.get_tree(info.owner, info.name, info.head_sha),
        gh.get_commit_stats(info.owner, info.name, info.head_sha),
    )
    classification = classify_paths(tree)
    to_sample = select_files_to_sample(classification, settings.MAX_SAMPLED_FILES)

    semaphore = asyncio.Semaphore(FETCH_CONCURRENCY)
    results = await asyncio.gather(
        *(_fetch_sample(gh, info, path, semaphore) for path in to_sample)
    )
    fetched = [r for r in results if r is not None]

    findings = hygiene_findings(classification)
    findings.extend(path_injection_findings(path for path, _ in classification.all_blobs))
    sampled: list[SampledFile] = []
    secrets_total = 0
    readme_words = 0
    total_lines = 0
    readme_path = classification.readme_paths[0] if classification.readme_paths else None
    for item in fetched:
        # Secrets count even when nothing is left to sample (e.g. a key only in notebook output).
        secrets_total += item.secrets
        if item.secrets:
            findings.append(secret_finding(item.path, item.secrets))
        if item.injection:
            # Checked on the raw text, so injections hidden in notebook markdown or past the
            # truncation point are still reported (deduplicated with content_findings below).
            findings.append(Finding("security", "medium", INJECTION_MESSAGE, item.path))
        if item.unreadable_notebook:
            findings.append(notebook_unreadable_finding(item.path))
        if not item.content.strip():
            continue
        sampled.append(SampledFile(path=item.path, content=item.content, truncated=item.truncated))
        total_lines += count_lines(item.content)
        if item.path == readme_path:
            readme_words = count_words(item.content)
        findings.extend(content_findings(item.path, item.content, item.truncated))

    if readme_path and readme_words < MIN_README_WORDS:
        findings.append(
            Finding(
                "documentation",
                "medium",
                f"README is only {readme_words} words - explain setup, usage, and design.",
                readme_path,
            )
        )
    findings.extend(genai_findings(classification, sampled, secrets_total))

    logger.info(
        "Analyzed %s/%s@%s: %d files, %d sampled, %d secrets, %d findings",
        info.owner,
        info.name,
        info.head_sha[:7],
        len(classification.files),
        len(sampled),
        secrets_total,
        len(findings),
    )
    return AnalysisResult(
        languages=languages,
        file_count=len(classification.files),
        total_lines=total_lines,
        notebook_count=len(classification.notebooks),
        has_readme=bool(classification.readme_paths),
        readme_word_count=readme_words,
        has_tests=bool(classification.test_files),
        has_dependency_file=bool(classification.dependency_files),
        has_gitignore=classification.has_gitignore,
        has_env_file_committed=bool(classification.env_files),
        secrets_found_count=secrets_total,
        commit_count=commit_count,
        last_commit_at=last_commit_at,
        largest_files=largest_files(classification),
        findings=sort_findings(findings),
        sampled_files=sampled,
    )

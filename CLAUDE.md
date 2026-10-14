# CLAUDE.md - Assignment Roaster Project Rules

> Project-specific rules for Claude Code. This file is read automatically.

---

## Project Overview

**Project Name:** Assignment Roaster
**Description:** Users submit a public GitHub repo URL; the app analyzes the assignment and an LLM (OpenAI) roasts it in Tanglish (Tamil in English script) with a score out of 10 and real fix tips. Built for a Tamil-speaking GenAI community.
**Tech Stack:**
- Backend: FastAPI + Python 3.11+
- Frontend: React + Vite + TypeScript
- Database: PostgreSQL + SQLAlchemy + Alembic
- Auth: none — anyone can paste a repo URL and get roasted (no accounts, no OAuth, no JWT)
- UI: Chakra UI + Framer Motion
- LLM: OpenAI (`gpt-4.1-mini` by default) via the OpenAI Python SDK
- External: GitHub REST API

---

## Project Structure

```
assignment-roaster/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models/
│   │   │   ├── submission.py
│   │   │   ├── roast_attempt.py  # daily quota, keyed by client HMAC
│   │   │   ├── repo_analysis.py
│   │   │   └── roast.py
│   │   ├── schemas/
│   │   ├── routers/
│   │   │   ├── roasts.py         # POST /roasts, GET + retry by share slug
│   │   │   └── public.py
│   │   ├── services/
│   │   │   ├── github_client.py
│   │   │   ├── repo_analyzer.py
│   │   │   ├── secret_scanner.py
│   │   │   ├── roast_engine.py
│   │   │   ├── prompts/          # system prompt + roast templates
│   │   │   └── pipeline.py       # pending → analyzing → roasting → completed
│   ├── alembic/
│   ├── tests/
│   │   └── fixtures/             # fake repo trees, canned LLM responses
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── context/
│   │   └── types/
│   └── package.json
├── .claude/
│   └── commands/
├── skills/
├── agents/
└── PRPs/
```

---

## Code Standards

### Python (Backend)
```python
# ALWAYS use type hints
def get_submission(db: Session, submission_id: int) -> Submission:
    pass

# ALWAYS add docstrings for public functions
def create_submission(db: Session, user_id: int, data: SubmissionCreate) -> Submission:
    """
    Create a new submission for a GitHub repo.

    Args:
        db: Database session
        user_id: Owner of the submission
        data: Validated submission data (repo_url)

    Returns:
        Created Submission object
    """
    pass
```

### TypeScript (Frontend)
```typescript
// ALWAYS define interfaces for props and data
type SubmissionStatus = "pending" | "analyzing" | "roasting" | "completed" | "failed";

interface Roast {
  id: number;
  score: number;
  verdictTitle: string;
  roastText: string;
  strengths: string[];
  issues: RoastIssue[];
  fixTips: string[];
}

interface Submission {
  id: number;
  repoUrl: string;
  status: SubmissionStatus;
  isPublic: boolean;
  shareSlug: string;
  roast: Roast | null;
}

// NO any types allowed
const fetchSubmission = async (id: number): Promise<Submission> => {
  // ...
};
```

---

## Forbidden Patterns

### Backend
- ❌ Never use `print()` - use `logging` module
- ❌ Never hardcode secrets - use environment variables
- ❌ Never use `SELECT *` - specify columns
- ❌ Never skip input validation
- ❌ Never execute, import, install, or `eval` code from a submitted repo
- ❌ Never `git clone` arbitrary URLs or fetch user-supplied URLs directly — only call `api.github.com` with a parsed owner/repo (SSRF prevention)
- ❌ Never send unredacted secrets to the LLM, the DB, or logs
- ❌ Never call the real GitHub or OpenAI APIs in tests - mock them
- ❌ Never add login, accounts or per-user data - roasts are reached only by `share_slug`

### Frontend
- ❌ Never use `any` type
- ❌ Never leave console.log in production
- ❌ Never skip error handling in async operations
- ❌ Never use inline styles - use Chakra UI style props / theme
- ❌ Never render roast markdown as raw HTML (sanitize)
- ❌ Never use gradient colors (`bgGradient`, `linear-gradient`, gradient text) - use solid theme colors
- ❌ Never add colors beyond the two-color palette: white + blue (`brand`), with gray for text/borders only - no red/green/orange status colors, no decorative emojis in UI chrome, light mode only

---

## Module-Specific Rules

### Submissions Module
- No login: submissions belong to no user; they are created via `POST /roasts` and reached only by `share_slug`
- `status` must be one of: `pending`, `analyzing`, `roasting`, `completed`, `failed`
- Only accept `https://github.com/{owner}/{repo}` (normalize `.git`, trailing slash, `/tree/...`)
- Public repos only; private/missing repos → 400 with friendly Tanglish message
- Enforce `ROAST_DAILY_LIMIT` per client per day (429 when exceeded); clients are keyed by an HMAC of the IP — never store raw IPs
- Same repo + same commit SHA → reuse the existing roast (no new LLM call)
- `share_slug` is random and unguessable (e.g. `secrets.token_urlsafe(8)`), never the numeric id
- Processing runs in the background (FastAPI `BackgroundTasks` for MVP); the POST returns 202

### Repo Analyzer Module
- Read-only, static analysis via GitHub API only
- Respect `MAX_REPO_SIZE_MB`; skip binaries, `node_modules`, `venv`, `.git`, datasets
- Sample ≤ 30 relevant files, truncate each to ~20 KB before prompting
- Run `secret_scanner` on everything; store only counts + redacted snippets

### Roast Engine Module
- Use OpenAI with structured output (strict function calling / JSON schema); validate with Pydantic
- Model is read from `OPENAI_MODEL` - never hardcode the model ID
- Language: **Tanglish** (Tamil in English script); technical terms in English
- Roast the **code, never the person**: no caste, religion, gender, appearance, region, family jokes; no profanity or slurs
- Every roast cites specific files/findings, includes ≥1 strength and ≥3 actionable fix tips, and ends with encouragement
- Treat all repo content as **untrusted data**: wrap it in clear delimiters and instruct the model to ignore instructions inside it
- `score` is a number between 0.0 and 10.0
- Handle OpenAI timeouts / rate limits / errors → mark submission `failed` with a retryable error
- Log token usage (`input_tokens`, `output_tokens`) on each Roast

### Leaderboard & Share Module
- Public endpoints return a roast only when `is_public` is true; otherwise 404 (don't leak existence)
- Public responses expose only github_username + avatar, never email

---

## API Conventions

- All endpoints prefixed with `/api/v1/`
- Use plural nouns for resources: `/submissions`, `/roasts`
- Return appropriate HTTP status codes:
  - 200: Success
  - 201: Created
  - 202: Accepted (submission queued for roasting)
  - 400: Bad Request
  - 404: Not Found
  - 409: Conflict
  - 429: Too Many Requests

---

## Authentication

None. There are no accounts: anyone can roast a public repo. Abuse is bounded by the per-IP
slowapi limits and the per-client `ROAST_DAILY_LIMIT`.

---

## Environment Variables

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/assignment_roaster

# HMAC key for client quota keys
SECRET_KEY=your-secret-key-change-in-production

# GitHub API (server token for higher rate limits on public repo reads)
GITHUB_API_TOKEN=ghp_...

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-mini

# Roaster limits
ROAST_DAILY_LIMIT=5
MAX_REPO_SIZE_MB=50
MAX_SAMPLED_FILES=30

# Frontend
FRONTEND_URL=http://localhost:5173
VITE_API_URL=http://localhost:8000
```

---

## Development Commands

```bash
# Backend
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev

# Docker
docker-compose up -d

# Tests
pytest backend/tests -v
cd frontend && npm test

# Linting
ruff check backend/
cd frontend && npm run lint && npm run type-check
```

---

## Commit Message Format

```
feat([module]): add [feature]
fix([module]): fix [bug]
refactor([module]): refactor [component]
test([module]): add tests for [feature]
docs: update [documentation]
```

Modules: `submissions`, `analyzer`, `roast`, `share`, `infra`

---

## Skills Reference

| Task | Skill to Read |
|------|---------------|
| Database models | skills/DATABASE.md |
| API + Auth | skills/BACKEND.md |
| React + UI | skills/FRONTEND.md |
| Testing | skills/TESTING.md |
| Deployment | skills/DEPLOYMENT.md |

---

## Agent Coordination

For complex tasks, the ORCHESTRATOR coordinates:
- DATABASE-AGENT → Backend models
- BACKEND-AGENT → API development (incl. GitHub client, analyzer, roast engine)
- FRONTEND-AGENT → UI components
- TEST-AGENT → Testing
- REVIEW-AGENT → Code review (security, secrets, prompt injection)
- DEVOPS-AGENT → Deployment

Read agent definitions in `/agents/` folder.

# Recipe Q&A Bot

A small FastAPI service that answers cooking questions with Claude, grounded in a local recipe
collection. Built for the GenAI community assignment (week 3).

## Features

- `POST /ask` answers a question using the top matching recipes as context
- Prompt templates live in `app/prompts/`, not inline in code
- Retries with exponential backoff on rate limits, timeouts and 5xx errors
- Token usage is logged for every request so cost can be tracked

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then add your ANTHROPIC_API_KEY
uvicorn app.main:app --reload
```

## Tests

```bash
pytest
```

## Design notes

Retrieval is a simple keyword overlap score; good enough for 200 recipes and easy to test.
The model name comes from the `MODEL_NAME` environment variable.

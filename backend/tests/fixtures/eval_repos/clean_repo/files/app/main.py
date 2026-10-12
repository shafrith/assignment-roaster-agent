"""FastAPI entry point for the recipe Q&A bot."""

import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.llm import ask_model, build_prompt
from app.retrieval import load_recipes, top_k

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Recipe Q&A Bot")
RECIPES = load_recipes()


class Question(BaseModel):
    question: str


class Answer(BaseModel):
    answer: str
    sources: list[str]


@app.post("/ask", response_model=Answer)
def ask(body: Question) -> Answer:
    """Answer a cooking question grounded in the recipe collection."""
    context = top_k(body.question, RECIPES)
    try:
        answer = ask_model(build_prompt(body.question, context))
    except Exception as exc:
        logger.exception("Failed to answer question")
        raise HTTPException(status_code=502, detail="Model unavailable") from exc
    return Answer(answer=answer, sources=context)

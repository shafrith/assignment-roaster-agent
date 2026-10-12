"""Keyword-overlap retrieval over a small recipe collection."""

import json
from pathlib import Path

DATA_PATH = Path(__file__).parent / "recipes.json"


def load_recipes(path: Path = DATA_PATH) -> list[str]:
    """Load recipe texts from disk."""
    return [r["text"] for r in json.loads(path.read_text(encoding="utf-8"))]


def score(question: str, recipe: str) -> int:
    """Count shared lowercase words between the question and a recipe."""
    return len(set(question.lower().split()) & set(recipe.lower().split()))


def top_k(question: str, recipes: list[str], k: int = 3) -> list[str]:
    """Return the k recipes with the highest overlap score."""
    return sorted(recipes, key=lambda r: score(question, r), reverse=True)[:k]

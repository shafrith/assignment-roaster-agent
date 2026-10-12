from app.retrieval import score, top_k


def test_score_counts_shared_words() -> None:
    assert score("spicy chicken curry", "Chicken curry with rice") == 2


def test_top_k_orders_by_score() -> None:
    recipes = ["plain rice", "chicken curry", "spicy chicken curry"]
    assert top_k("spicy chicken curry", recipes, k=1) == ["spicy chicken curry"]

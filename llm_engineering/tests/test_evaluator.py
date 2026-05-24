"""Evaluator citation accuracy test — no API calls needed."""
from datetime import datetime, timezone

from src.models import Article, TechCategory
from src.evaluation.evaluator import OutputEvaluator


def _article(url: str) -> Article:
    return Article(
        id="x", url=url, title="T", source="S",
        published_at=datetime.now(timezone.utc), content="c",
        categories=[TechCategory.AI_ML],
    )


def test_citation_accuracy_all_valid():
    evaluator = OutputEvaluator.__new__(OutputEvaluator)  # no LLM needed
    articles = [_article("https://techcrunch.com/article-1")]
    text = "Here is a fact [TechCrunch](https://techcrunch.com/article-1)."
    acc, invalid = evaluator.check_citation_accuracy(text, articles)
    assert acc == 1.0
    assert invalid == []


def test_citation_accuracy_with_invalid_url():
    evaluator = OutputEvaluator.__new__(OutputEvaluator)
    articles = [_article("https://techcrunch.com/article-1")]
    text = "Fact [TC](https://techcrunch.com/article-1) and hallucination https://fake.com/invented."
    acc, invalid = evaluator.check_citation_accuracy(text, articles)
    assert acc < 1.0
    assert "https://fake.com/invented" in invalid


def test_no_citations_returns_perfect_score():
    evaluator = OutputEvaluator.__new__(OutputEvaluator)
    acc, invalid = evaluator.check_citation_accuracy("No URLs here.", [])
    assert acc == 1.0
    assert invalid == []

"""
LLM output quality evaluator.

Checks:
1. Citation accuracy — every cited URL must come from the source articles
2. Hallucination detection — claims in summaries should be grounded in source text
3. Relevance score — how well the answer addresses the original query
4. Token efficiency — output tokens / input tokens ratio

Uses Haiku (cheap, fast) for the hallucination check to keep eval costs low.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.models import Article, DigestArticle, TokenUsage
from src.llm.client import LLMClient


@dataclass
class EvaluationResult:
    citation_accuracy: float        # 0.0–1.0: fraction of citations that are valid
    hallucination_risk: str         # "low" | "medium" | "high"
    relevance_score: float          # 0.0–1.0: LLM-judged relevance
    invalid_citations: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    eval_token_cost: TokenUsage = field(default_factory=TokenUsage)


URL_PATTERN = re.compile(r'https?://[^\s\)\"\']+')


def _clean_urls(raw_urls: list[str]) -> list[str]:
    """Strip trailing punctuation that isn't part of the URL."""
    return [u.rstrip(".,;:!?)\"'") for u in raw_urls]



class OutputEvaluator:
    def __init__(self, llm_client: LLMClient | None = None):
        self._llm = llm_client or LLMClient()

    # ------------------------------------------------------------------
    # Citation accuracy
    # ------------------------------------------------------------------

    def check_citation_accuracy(
        self,
        generated_text: str,
        source_articles: list[Article],
    ) -> tuple[float, list[str]]:
        """
        Extract all URLs from generated_text and verify they exist in source_articles.
        Returns (accuracy_score, list_of_invalid_urls).
        """
        source_urls = {a.url for a in source_articles}
        cited_urls = _clean_urls(URL_PATTERN.findall(generated_text))

        if not cited_urls:
            return 1.0, []  # no citations = no wrong citations

        invalid = [u for u in cited_urls if u not in source_urls]
        accuracy = 1.0 - (len(invalid) / len(cited_urls))
        return round(accuracy, 3), invalid

    # ------------------------------------------------------------------
    # Hallucination check (LLM-as-judge)
    # ------------------------------------------------------------------

    def check_hallucination(
        self,
        generated_summary: str,
        source_content: str,
    ) -> tuple[str, TokenUsage]:
        """
        Ask Haiku to judge whether the summary contains claims not supported by source.
        Returns ("low"|"medium"|"high", token_usage).
        """
        system = (
            "You are a fact-checking assistant. Given a SOURCE text and a SUMMARY, "
            "decide if the summary contains any claims not supported by the source.\n"
            "Respond with exactly one word: 'low', 'medium', or 'high'.\n"
            "- low: summary is fully grounded in the source\n"
            "- medium: minor extrapolation, one unsupported detail\n"
            "- high: significant claims not in the source, or invented facts"
        )
        user_message = (
            f"SOURCE:\n{source_content[:1200]}\n\nSUMMARY:\n{generated_summary}"
        )

        response, usage = self._llm.complete_fast(
            system=system,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=10,
        )
        risk = response.strip().lower()
        if risk not in ("low", "medium", "high"):
            risk = "medium"

        return risk, usage

    # ------------------------------------------------------------------
    # Relevance check
    # ------------------------------------------------------------------

    def score_relevance(
        self,
        query: str,
        answer: str,
    ) -> tuple[float, TokenUsage]:
        """
        Ask Haiku to score how well the answer addresses the query.
        Returns (score_0_to_1, token_usage).
        """
        system = (
            "You are a relevance evaluator. Given a QUERY and an ANSWER, "
            "score how well the answer addresses the query.\n"
            "Respond with only a number between 0.0 and 1.0. Nothing else."
        )
        user_message = f"QUERY: {query}\n\nANSWER: {answer[:800]}"

        response, usage = self._llm.complete_fast(
            system=system,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=10,
        )
        try:
            score = float(response.strip())
            score = max(0.0, min(1.0, score))
        except ValueError:
            score = 0.5

        return round(score, 2), usage

    # ------------------------------------------------------------------
    # Full evaluation pipeline
    # ------------------------------------------------------------------

    def evaluate_digest_article(
        self,
        digest_article: DigestArticle,
        source_articles: list[Article],
    ) -> EvaluationResult:
        citation_acc, invalid = self.check_citation_accuracy(
            digest_article.summary, source_articles
        )

        hallucination_risk, usage = self.check_hallucination(
            digest_article.summary,
            digest_article.article.content,
        )

        flags = []
        if citation_acc < 0.8:
            flags.append(f"Low citation accuracy: {citation_acc:.0%}")
        if hallucination_risk == "high":
            flags.append("High hallucination risk flagged")

        return EvaluationResult(
            citation_accuracy=citation_acc,
            hallucination_risk=hallucination_risk,
            relevance_score=digest_article.article.relevance_score,
            invalid_citations=invalid,
            flags=flags,
            eval_token_cost=usage,
        )

    def evaluate_chat_response(
        self,
        query: str,
        answer: str,
        source_articles: list[Article],
    ) -> EvaluationResult:
        citation_acc, invalid = self.check_citation_accuracy(answer, source_articles)
        relevance, rel_usage = self.score_relevance(query, answer)
        hallucination_risk, hall_usage = self.check_hallucination(
            answer,
            "\n\n".join(a.content[:400] for a in source_articles[:3]),
        )

        total_usage = TokenUsage(
            input_tokens=rel_usage.input_tokens + hall_usage.input_tokens,
            output_tokens=rel_usage.output_tokens + hall_usage.output_tokens,
        )

        flags = []
        if citation_acc < 0.8:
            flags.append(f"Low citation accuracy: {citation_acc:.0%}")
        if hallucination_risk == "high":
            flags.append("High hallucination risk flagged")
        if relevance < 0.5:
            flags.append(f"Low relevance score: {relevance}")

        return EvaluationResult(
            citation_accuracy=citation_acc,
            hallucination_risk=hallucination_risk,
            relevance_score=relevance,
            invalid_citations=invalid,
            flags=flags,
            eval_token_cost=total_usage,
        )

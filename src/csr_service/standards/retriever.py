"""TF-IDF based standards rule retriever.

Builds a TF-IDF index over rule text (title + body + tags) at init time.
At query time, vectorizes the input content and returns the top-k most
relevant rules by cosine similarity. The value of k is determined by
the strictness level: low=6, medium=10, high=14.

Retrieval behavior is deterministic for a given sklearn version and
standards set. Vectorizer config is pinned (bigrams, L2 norm) to prevent
silent behavior shifts across library updates.
"""

from typing import Literal

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ..config import policy_config
from ..schemas.standards import StandardRule, StandardsSet


class StandardsRetriever:
    def __init__(self, standards_set: StandardsSet):
        self.rules = standards_set.rules
        corpus = [self._rule_text(r) for r in self.rules]
        self.vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            norm="l2",
        )
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)

    def _rule_text(self, rule: StandardRule) -> str:
        parts = [rule.title, rule.body]
        if rule.tags:
            parts.append(" ".join(rule.tags))
        return " ".join(parts)

    def retrieve(
        self, content: str, strictness: Literal["low", "medium", "high"] = "medium"
    ) -> list[StandardRule]:
        k = policy_config.retrieval.k_by_strictness.get(strictness, 10)
        k = min(k, len(self.rules))

        query_vec = self.vectorizer.transform([content])
        scores = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        top_indices = np.argsort(scores)[::-1][:k]

        return [self.rules[i] for i in top_indices]

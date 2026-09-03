"""Retrieval module for Hospital Protocol Authoritative-Version Resolver.

Includes:
1. CandidateRetriever: Vector / TF-IDF similarity matcher for candidate generation.
2. BaselineRetriever: Naive baseline that picks top-similarity document without authority resolution.
"""

from typing import List, Tuple, Optional
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from src.models import Document


class CandidateRetriever:
    """Retrieves top candidate documents matching a staff query."""

    def __init__(self, documents: List[Document]):
        self.documents = documents
        self.vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            lowercase=True,
        )
        self._build_index()

    def _build_index(self):
        """Builds TF-IDF index over document title, department, and content."""
        corpus = [
            f"{doc.title} {doc.department} {doc.document_type} {doc.content} {doc.version}"
            for doc in self.documents
        ]
        if corpus:
            self.tfidf_matrix = self.vectorizer.fit_transform(corpus)
        else:
            self.tfidf_matrix = None

    def update_documents(self, documents: List[Document]):
        """Updates internal document registry and re-indexes."""
        self.documents = documents
        self._build_index()

    def retrieve_candidates(
        self, query: str, top_k: int = 5
    ) -> List[Tuple[Document, float]]:
        """Returns top_k (Document, similarity_score) pairs."""
        if not self.documents or self.tfidf_matrix is None:
            return []

        query_vec = self.vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, self.tfidf_matrix)[0]

        # Get top_k indices sorted descending
        top_indices = np.argsort(similarities)[::-1][:top_k]

        candidates = []
        for idx in top_indices:
            score = float(similarities[idx])
            candidates.append((self.documents[idx], score))
        return candidates


class BaselineRetriever:
    """Baseline naive retrieval system:

    Selects top document purely by keyword/vector similarity without authority.
    Vulnerable to high-similarity drafts, outdated versions, and wrong owners.
    """

    def __init__(self, retriever: CandidateRetriever):
        self.retriever = retriever

    def search(self, query: str) -> Tuple[Optional[Document], float, List[Tuple[Document, float]]]:
        """Runs naive retrieval and picks highest similarity candidate."""
        candidates = self.retriever.retrieve_candidates(query, top_k=5)
        if not candidates:
            return None, 0.0, []

        top_doc, top_sim = candidates[0]
        return top_doc, top_sim, candidates

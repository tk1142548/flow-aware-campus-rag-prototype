"""DashScope embedding retrieval with deterministic cosine ranking."""
from __future__ import annotations

import math
import os
import time
from typing import Callable

import numpy as np
import requests

ENDPOINT = 'https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings'


def cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    return dot / (left_norm * right_norm)


def dashscope_embed(texts: list[str], api_key: str | None = None, model: str = 'text-embedding-v4') -> list[list[float]]:
    key = api_key or os.environ.get('DASHSCOPE_API_KEY')
    if not key:
        raise RuntimeError('DASHSCOPE_API_KEY is required for semantic retrieval')
    if not 1 <= len(texts) <= 10:
        raise ValueError('DashScope embedding batch size must be between 1 and 10')
    last_error = None
    for attempt in range(5):
        try:
            response = requests.post(ENDPOINT, headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
                                     json={'model': model, 'input': texts}, timeout=90)
            response.raise_for_status()
            return [row['embedding'] for row in sorted(response.json()['data'], key=lambda row: row['index'])]
        except requests.RequestException as error:
            last_error = error
            if attempt < 4:
                time.sleep(2 ** attempt)
    raise last_error


class SemanticRetriever:
    def __init__(self, evidence: list[dict], embedder: Callable[[list[str]], list[list[float]]]):
        self.rows = sorted(evidence, key=lambda row: row['evidence_id'])
        self.embedder = embedder
        texts = [self._text(row) for row in self.rows]
        self.vectors = self._embed_all(texts)
        matrix = np.asarray(self.vectors, dtype=float) if self.vectors else np.zeros((0, 0))
        norms = np.linalg.norm(matrix, axis=1, keepdims=True) if matrix.size else matrix
        self._unit = matrix / np.where(norms == 0, 1.0, norms) if matrix.size else matrix

    def _embed_all(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for start in range(0, len(texts), 10):
            vectors.extend(self.embedder(texts[start:start + 10]))
        return vectors

    @staticmethod
    def _text(row: dict) -> str:
        return ' '.join([row['normalized_claim'], row['verbatim_text'], *row.get('keywords', [])])

    def search(self, query: str, top_k: int = 5) -> list[tuple[dict, float]]:
        if not query.strip():
            raise ValueError('query must not be empty')
        if top_k < 1:
            raise ValueError('top_k must be positive')
        return self._rank(self.embedder([query])[0], top_k)

    def search_many(self, queries: list[str], top_k: int = 5) -> list[list[tuple[dict, float]]]:
        """Embed a query batch in groups of ten and rank without extra API calls."""
        if not queries or any(not query.strip() for query in queries):
            raise ValueError('queries must not be empty')
        if top_k < 1:
            raise ValueError('top_k must be positive')
        vectors = []
        for start in range(0, len(queries), 10):
            vectors.extend(self.embedder(queries[start:start + 10]))
        return [self._rank(vector, top_k) for vector in vectors]

    def _rank(self, query_vector: list[float], top_k: int) -> list[tuple[dict, float]]:
        if not self.rows:
            return []
        query = np.asarray(query_vector, dtype=float)
        norm = np.linalg.norm(query)
        scores = self._unit @ (query / norm if norm else query)
        ranked = [(row, float(score)) for row, score in zip(self.rows, scores)]
        return sorted(ranked, key=lambda hit: (-hit[1], hit[0]['evidence_id']))[:top_k]

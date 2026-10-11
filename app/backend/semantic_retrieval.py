"""DashScope embedding retrieval with deterministic cosine ranking."""
from __future__ import annotations

import math
import os
from typing import Callable

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
    response = requests.post(ENDPOINT, headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
                             json={'model': model, 'input': texts}, timeout=90)
    response.raise_for_status()
    return [row['embedding'] for row in sorted(response.json()['data'], key=lambda row: row['index'])]


class SemanticRetriever:
    def __init__(self, evidence: list[dict], embedder: Callable[[list[str]], list[list[float]]]):
        self.rows = sorted(evidence, key=lambda row: row['evidence_id'])
        self.embedder = embedder
        texts = [self._text(row) for row in self.rows]
        self.vectors = self._embed_all(texts)

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
        query_vector = self.embedder([query])[0]
        ranked = [(row, cosine(query_vector, vector)) for row, vector in zip(self.rows, self.vectors)]
        return sorted(ranked, key=lambda hit: (-hit[1], hit[0]['evidence_id']))[:top_k]
